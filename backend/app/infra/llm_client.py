"""로컬 LLM 호출 (Ollama). docs/llm-integration.md §4 계약.

모델/런타임 교체가 가능하도록 Protocol로 추상화(CLAUDE.md §13). 개발은 Ollama,
서빙은 vLLM(OpenAI 호환)으로 바꿔 끼울 수 있게 generate/generate_stream만 노출한다.

keep_alive=-1: 모델을 VRAM에 계속 상주시킨다. 재로딩 비용(exaone +6~7초)이 10초 응답
예산을 넘기므로 OS 환경변수(OLLAMA_KEEP_ALIVE)에 의존하지 않고 호출마다 코드에서 명시한다
(Ollama 재시작 시 환경변수는 초기화될 수 있음, nexttodo.md).
"""

import json
import logging
from collections.abc import Iterator
from typing import Protocol

import httpx

from app.core.config import settings

_log = logging.getLogger(__name__)


class LlmClient(Protocol):
    def generate(self, prompt: str) -> str:
        """프롬프트 -> 한국어 텍스트(비스트리밍). 실패 시 예외(폴백은 호출부 책임)."""
        ...

    def generate_stream(self, prompt: str) -> Iterator[str]:
        """프롬프트 -> 토큰 조각 스트림. 실패 시 예외."""
        ...


class OllamaClient:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout_s: float | None = None,
        num_predict: int | None = None,
        temperature: float | None = None,
        num_ctx: int | None = None,
    ) -> None:
        self.base_url = base_url or settings.llm_base_url
        self.model = model or settings.llm_model
        self.timeout_s = timeout_s if timeout_s is not None else settings.llm_timeout_s
        self.num_predict = num_predict if num_predict is not None else settings.llm_num_predict
        self.temperature = temperature if temperature is not None else settings.llm_temperature
        self.num_ctx = num_ctx if num_ctx is not None else settings.llm_num_ctx

    def _payload(self, prompt: str, *, stream: bool) -> dict:
        return {
            "model": self.model,
            "prompt": prompt,
            "stream": stream,
            "keep_alive": -1,  # 모델 상주(위 모듈 docstring 참고). 절대 빼지 말 것.
            # num_ctx를 반드시 실어야 한다 — 빼면 Ollama가 모델 능력(32k)과 무관하게 4096으로
            # 로드해 RAG 프롬프트가 창을 넘고 앞쪽(#보안 규칙)이 잘린다(config.llm_num_ctx 주석).
            "options": {
                "num_predict": self.num_predict,
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,
            },
        }

    def generate(self, prompt: str) -> str:
        resp = httpx.post(
            f"{self.base_url}/api/generate",
            json=self._payload(prompt, stream=False),
            timeout=self.timeout_s,
        )
        resp.raise_for_status()
        return resp.json().get("response", "")

    def generate_stream(self, prompt: str) -> Iterator[str]:
        with httpx.stream(
            "POST",
            f"{self.base_url}/api/generate",
            json=self._payload(prompt, stream=True),
            timeout=self.timeout_s,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                token = chunk.get("response")
                if token:
                    yield token
                if chunk.get("done"):
                    break


class VllmClient:
    """vLLM(OpenAI 호환) 구현. 다중 사용자 서빙용 — continuous batching이 목적이다.

    **왜 필요한가**: Ollama는 `OLLAMA_NUM_PARALLEL` 미설정 시 사실상 순차 처리다. 실측
    (2026-08-04, 로컬): 동시 6건에서 첫 토큰이 4.5s → 40.2s로 약 7초씩 계단식으로 늘었고
    전체 47초가 걸렸다(단독 9.7초의 5배). 평가에 6명이 동시에 쓰면 마지막 사람은 40초간 빈
    화면을 본다. 상세·전환 절차는 `docs/vllm.md`.

    **`/v1/chat/completions`에 단일 user 메시지로 보낸다.** `/v1/completions`(raw)가 아니다 —
    Ollama `/api/generate`는 `raw:false`가 기본이라 **모델 채팅 템플릿을 적용**하고, 우리
    프롬프트는 그 전제로 만들어져 있다(`build_chat_prompt`가 `#출력\\n`으로 끝나는 단일 문자열).
    raw로 보내면 템플릿이 빠져 같은 프롬프트에 다른 응답이 나온다.

    **`num_ctx`를 보내지 않는다.** Ollama는 요청마다 줄 수 있지만 vLLM은 **서버 기동 플래그
    `--max-model-len`으로 고정**이다(docs/vllm.md §5-2). 즉 PR #97에서 고친 `llm_num_ctx`는
    vLLM 경로에서 **VM 기동 설정과 맞춰야** 하고 클라이언트가 강제할 수 없다 — 그래서 값을
    들고만 있고(`self.num_ctx`) 검증·문서화 용도로 쓴다.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout_s: float | None = None,
        num_predict: int | None = None,
        temperature: float | None = None,
        num_ctx: int | None = None,
        disable_thinking: bool | None = None,
    ) -> None:
        self.base_url = base_url or settings.llm_base_url
        self.model = model or settings.llm_model
        self.timeout_s = timeout_s if timeout_s is not None else settings.llm_timeout_s
        self.num_predict = num_predict if num_predict is not None else settings.llm_num_predict
        self.temperature = temperature if temperature is not None else settings.llm_temperature
        # 요청에 싣지 않는다(위 docstring) — 기동 플래그와의 정합 확인용으로만 보관한다.
        self.num_ctx = num_ctx if num_ctx is not None else settings.llm_num_ctx
        self.disable_thinking = (
            disable_thinking if disable_thinking is not None else settings.llm_disable_thinking
        )

    def _payload(self, prompt: str, *, stream: bool) -> dict:
        payload: dict = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": stream,
            "max_tokens": self.num_predict,  # Ollama의 num_predict에 대응
            "temperature": self.temperature,
        }
        if self.disable_thinking:
            # **이걸 빼면 Qwen3가 답변을 아예 안 준다**(config.llm_disable_thinking 주석의 실측).
            # chat template 인자로 전달되며, 그 인자를 모르는 모델(EXAONE 등)은 무시한다.
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        return payload

    def generate(self, prompt: str) -> str:
        resp = httpx.post(
            f"{self.base_url}/v1/chat/completions",
            json=self._payload(prompt, stream=False),
            timeout=self.timeout_s,
        )
        resp.raise_for_status()
        choices = resp.json().get("choices") or []
        if not choices:
            return ""
        return (choices[0].get("message") or {}).get("content") or ""

    def generate_stream(self, prompt: str) -> Iterator[str]:
        with httpx.stream(
            "POST",
            f"{self.base_url}/v1/chat/completions",
            json=self._payload(prompt, stream=True),
            timeout=self.timeout_s,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                # SSE: `data: {json}` 여러 줄 + 마지막 `data: [DONE]`. 빈 줄은 프레임 구분자다.
                if not line or not line.startswith("data:"):
                    continue
                payload = line[len("data:") :].strip()
                if payload == "[DONE]":
                    break
                chunk = json.loads(payload)
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                token = (choices[0].get("delta") or {}).get("content")
                if token:
                    yield token


def make_llm_client(**overrides: object) -> LlmClient:
    """설정에 따라 구현체를 고른다 — 호출부가 어느 런타임인지 몰라도 되게 한다(§13).

    전환은 `LLM_BACKEND` + `LLM_BASE_URL` 두 env로 하고 재배포가 필요 없다
    (`gcloud run services update --update-env-vars`, docs/vllm.md §5-4).

    `overrides`는 두 구현이 같은 생성자 시그니처를 갖기 때문에 그대로 통과시킨다 —
    행동추천은 유저가 기다리는 경로라 짧은 타임아웃을 따로 준다
    (`timeout_s=advice_llm_timeout_s`, farms.py). 인자 이름이 갈리면 여기서 터지므로
    두 구현의 시그니처를 함께 유지할 것.
    """
    # 모르는 값(오타 등)은 **의도적으로** Ollama로 떨어뜨린다 — `LLM_BACKEND=vllllm` 하나로
    # 챗봇이 죽는 것보다 기존 런타임으로 도는 편이 낫다(§18-5 fail soft). 대신 조용히 넘기지
    # 않고 경고를 남긴다("방어가 원인을 감춘다"를 피한다 — nexttodo §인프라 반복 패턴).
    if settings.llm_backend not in ("ollama", "vllm"):
        _log.warning(
            "LLM_BACKEND=%r 는 모르는 값이다 — ollama로 진행한다(허용: ollama, vllm)",
            settings.llm_backend,
        )
    cls = VllmClient if settings.llm_backend == "vllm" else OllamaClient
    return cls(**overrides)  # type: ignore[arg-type]
