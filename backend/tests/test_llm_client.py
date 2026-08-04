"""LLM 클라이언트 계약 검증 — 응답 파싱과 백엔드 선택. 네트워크 불필요(캔드 응답).

**왜 필요한가**: vLLM은 Ollama와 응답 형식이 다르다(SSE `data: {...}` vs JSON 줄).
파싱이 틀리면 **배포해도 예외가 안 나고** 챗봇이 빈 답변 → `LLM_ERROR_TEXT` 폴백으로만
보인다(§18-5의 폴백이 원인을 가린다 — nexttodo의 "방어가 원인을 감춘다" 패턴).
전환 전에 캔드 응답으로 고정한다. 상세는 docs/vllm.md §5-2.
"""

import ast
import json
import unittest
from pathlib import Path
from unittest import mock

import httpx

from app.infra import llm_client
from app.infra.llm_client import OllamaClient, VllmClient, make_llm_client


def _sse(chunks: list[str], *, done: bool = True) -> list[str]:
    """OpenAI 호환 스트리밍 프레임. 빈 줄(프레임 구분자)을 섞어 실제 응답을 흉내낸다."""
    lines: list[str] = []
    for c in chunks:
        payload = {"choices": [{"delta": {"content": c}}]}
        lines.append(f"data: {json.dumps(payload, ensure_ascii=False)}")
        lines.append("")  # SSE 프레임 구분자 — 파서가 이걸 건너뛰어야 한다
    if done:
        lines.append("data: [DONE]")
    return lines


class _FakeStream:
    """`httpx.stream()`의 컨텍스트 매니저를 대신한다."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    def __enter__(self) -> "_FakeStream":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_lines(self):
        yield from self._lines


class TestVllmStreamParsing(unittest.TestCase):
    def _collect(self, lines: list[str]) -> str:
        with mock.patch.object(llm_client.httpx, "stream", return_value=_FakeStream(lines)):
            return "".join(VllmClient().generate_stream("프롬프트"))

    def test_parses_delta_content(self):
        self.assertEqual(self._collect(_sse(["오이", " 노균병", "입니다"])), "오이 노균병입니다")

    def test_skips_blank_frame_separators(self):
        """SSE는 프레임 사이에 빈 줄이 온다 — 그걸 JSON으로 파싱하려 들면 터진다."""
        self.assertEqual(self._collect(["", "", *_sse(["가"]), ""]), "가")

    def test_stops_at_done_sentinel(self):
        """`[DONE]` 뒤 데이터는 무시해야 한다 — JSON이 아니라 파싱하면 예외다."""
        lines = [*_sse(["앞"], done=True), 'data: {"choices":[{"delta":{"content":"뒤"}}]}']
        self.assertEqual(self._collect(lines), "앞")

    def test_ignores_chunk_without_content(self):
        """마지막 청크는 `delta`가 비고 `finish_reason`만 오는 경우가 있다."""
        lines = [
            'data: {"choices":[{"delta":{"role":"assistant"}}]}',
            'data: {"choices":[{"delta":{"content":"본문"}}]}',
            'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}',
            "data: [DONE]",
        ]
        self.assertEqual(self._collect(lines), "본문")

    def test_empty_choices_is_safe(self):
        self.assertEqual(self._collect(['data: {"choices":[]}', "data: [DONE]"]), "")


class TestVllmNonStreaming(unittest.TestCase):
    def _post(self, payload: dict) -> str:
        resp = httpx.Response(200, json=payload, request=httpx.Request("POST", "http://x/"))
        with mock.patch.object(llm_client.httpx, "post", return_value=resp):
            return VllmClient().generate("프롬프트")

    def test_reads_message_content(self):
        self.assertEqual(
            self._post({"choices": [{"message": {"content": "답변"}}]}), "답변"
        )

    def test_empty_choices_returns_empty_string(self):
        """빈 문자열이면 호출부가 폴백을 태운다(§18-5) — 예외로 죽지 않는 게 계약이다."""
        self.assertEqual(self._post({"choices": []}), "")


class TestVllmPayload(unittest.TestCase):
    def test_sends_chat_messages_not_raw_prompt(self):
        """`/v1/completions`(raw)가 아니라 chat 형식이어야 한다.

        Ollama `/api/generate`는 `raw:false`가 기본이라 모델 채팅 템플릿을 적용하고, 우리
        프롬프트는 그 전제로 만들어져 있다. raw로 보내면 같은 프롬프트에 다른 응답이 나온다.
        """
        payload = VllmClient()._payload("프롬프트", stream=False)
        self.assertEqual(payload["messages"], [{"role": "user", "content": "프롬프트"}])
        self.assertNotIn("prompt", payload)

    def test_maps_num_predict_to_max_tokens(self):
        self.assertEqual(VllmClient(num_predict=123)._payload("p", stream=False)["max_tokens"], 123)

    def test_sends_disable_thinking_by_default(self):
        """**이 항목이 빠지면 Qwen3가 답변을 아예 안 준다.**

        L4 vLLM 0.26 실측(2026-08-04): 미지정 시 `content`가 `<think>\\nOkay, the user is
        asking...`로 시작해 max_tokens 200을 전부 내부 사고(영어)에 쓰고 `finish_reason=length`로
        끝났다 — 유저는 사고 과정만 보고 답변은 0자다. 껐을 때는 `completion_tokens=28`,
        `finish_reason=stop`, 정상 한국어 답변. 기본값을 켜 둔 이유가 이것이다.
        """
        payload = VllmClient()._payload("p", stream=False)
        self.assertEqual(payload["chat_template_kwargs"], {"enable_thinking": False})

    def test_can_opt_out_of_disable_thinking(self):
        """생각 모드를 쓰는 모델로 바꿀 여지를 남긴다 — 하드코딩하면 그때 걸린다."""
        payload = VllmClient(disable_thinking=False)._payload("p", stream=False)
        self.assertNotIn("chat_template_kwargs", payload)

    def test_ollama_does_not_get_chat_template_kwargs(self):
        """Ollama는 `think` 필드가 별도라 이 항목이 가면 안 된다(모르는 키)."""
        self.assertNotIn("chat_template_kwargs", OllamaClient()._payload("p", stream=False))

    def test_does_not_send_num_ctx(self):
        """vLLM은 컨텍스트 창을 `--max-model-len` 기동 플래그로 고정한다 — 요청 항목이 아니다.

        값은 보관하되(정합 확인용) 페이로드에 실으면 vLLM이 모르는 키를 받는다.
        """
        client = VllmClient(num_ctx=8192)
        self.assertEqual(client.num_ctx, 8192)
        self.assertNotIn("num_ctx", client._payload("p", stream=False))
        self.assertNotIn("options", client._payload("p", stream=False))


class TestOllamaStillSendsNumCtx(unittest.TestCase):
    def test_ollama_payload_keeps_num_ctx(self):
        """Ollama 경로는 반대다 — 빼면 4096으로 로드돼 프롬프트 앞쪽이 잘린다(PR #97)."""
        options = OllamaClient(num_ctx=8192)._payload("p", stream=False)["options"]
        self.assertEqual(options["num_ctx"], 8192)


class TestMakeLlmClient(unittest.TestCase):
    def test_defaults_to_ollama(self):
        with mock.patch.object(llm_client.settings, "llm_backend", "ollama"):
            self.assertIsInstance(make_llm_client(), OllamaClient)

    def test_selects_vllm_by_setting(self):
        with mock.patch.object(llm_client.settings, "llm_backend", "vllm"):
            self.assertIsInstance(make_llm_client(), VllmClient)

    def test_unknown_backend_falls_back_to_ollama(self):
        """오타로 챗봇이 죽는 것보다 기존 런타임으로 도는 게 낫다(§18-5)."""
        with mock.patch.object(llm_client.settings, "llm_backend", "vllllm"):
            self.assertIsInstance(make_llm_client(), OllamaClient)

    def test_overrides_pass_through_to_both(self):
        """행동추천은 짧은 타임아웃을 따로 준다 — 두 구현의 시그니처가 갈리면 여기서 잡힌다."""
        for backend, expected in (("ollama", OllamaClient), ("vllm", VllmClient)):
            with self.subTest(backend=backend):
                with mock.patch.object(llm_client.settings, "llm_backend", backend):
                    client = make_llm_client(timeout_s=8.0)
                    self.assertIsInstance(client, expected)
                    self.assertEqual(client.timeout_s, 8.0)


class TestNoHardcodedClient(unittest.TestCase):
    """호출부가 구체 클라이언트를 직접 생성하면 `LLM_BACKEND` 전환이 그 경로만 비껀다.

    실제로 그랬다(docs/vllm.md 회귀 절): `farms.py`의 장기 추천이 팩토리 대신
    `OllamaClient`를 하드코딩한 채 머지돼, vLLM 전환 직후 이 엔드포인트만 500이 났다.
    import도 없어 `NameError`였는데 **테스트 470개가 전부 통과했다** — 라우터 배선을
    아무도 안 보기 때문이다. 값 하나가 아니라 패턴을 막는다.
    """

    def test_only_factory_constructs_concrete_clients(self):
        root = Path(llm_client.__file__).resolve().parents[1]  # app/
        offenders: list[str] = []
        for path in sorted(root.rglob("*.py")):
            if path.samefile(llm_client.__file__):
                continue  # 팩토리 자신은 당연히 생성한다
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id in {"OllamaClient", "VllmClient"}:
                        offenders.append(f"{path.relative_to(root)}:{node.lineno}")
        self.assertEqual(
            offenders,
            [],
            f"구체 LLM 클라이언트를 직접 생성한다: {offenders} — make_llm_client()를 쓸 것",
        )

    def test_walk_actually_sees_app_modules(self):
        # rglob이 빈 결과를 돌면 위 검사가 공허하게 통과한다.
        root = Path(llm_client.__file__).resolve().parents[1]
        self.assertGreater(len(list(root.rglob("*.py"))), 20)


if __name__ == "__main__":
    unittest.main()
