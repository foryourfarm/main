"""챗봇 프롬프트 조립 + 스트리밍 폴백의 결정론 경계 검증. 네트워크/DB 불필요(가짜 LLM만).

실행: backend/.venv/Scripts/python.exe -m unittest tests.test_chat_service   (backend/ 에서)
"""

import unittest
from collections.abc import Iterator
from decimal import Decimal

from app.prompts.chatbot import (
    ASK_CROP_TEXT,
    REFERRAL_TEXT,
    SECURITY_REDIRECT,
    FarmContext,
    build_chat_prompt,
    format_context,
    format_crop,
    format_farm_context,
    format_history,
)
from app.services.chat_service import LLM_ERROR_TEXT, SSE_DONE, stream_from_chunks


class FakeLlm:
    def __init__(self, tokens: list[str] | None = None, raises: bool = False):
        self._tokens = tokens or []
        self._raises = raises

    def generate(self, prompt: str) -> str:
        return "".join(self._tokens)

    def generate_stream(self, prompt: str) -> Iterator[str]:
        if self._raises:
            raise RuntimeError("연결 실패")
        yield from self._tokens


class TestPromptAssembly(unittest.TestCase):
    def test_includes_question_evidence_crop_and_rules(self):
        prompt = build_chat_prompt(
            "물 언제 줘요?", ["상추는 아침에 물을 준다."], crop_name="상추"
        )
        self.assertIn("물 언제 줘요?", prompt)
        self.assertIn("상추는 아침에 물을 준다.", prompt)
        self.assertIn("[작물] 상추", prompt)
        self.assertIn(REFERRAL_TEXT, prompt)  # 근거 없을 때 거절 지시가 박혀 있어야 함
        self.assertIn(ASK_CROP_TEXT, prompt)  # 작물 불명확 시 되묻기 지시가 박혀 있어야 함

    def test_empty_context_marker(self):
        self.assertEqual(format_context([]), "(관련 자료 없음)")

    def test_unspecified_crop_marker(self):
        self.assertEqual(format_crop(None), "(지정 안 됨)")
        self.assertIn("[작물] (지정 안 됨)", build_chat_prompt("q", ["c"], crop_name=None))

    def test_history_rendered_in_order(self):
        block = format_history([("user", "상추 키워요"), ("assistant", "네, 상추 상담 도와드릴게요")])
        self.assertIn("사용자: 상추 키워요", block)
        self.assertIn("상담사: 네, 상추 상담 도와드릴게요", block)
        self.assertIn("사용자: 상추 키워요", build_chat_prompt("물은?", ["c"], history=[("user", "상추 키워요")]))

    def test_empty_history_is_blank(self):
        self.assertEqual(format_history([]), "")
        self.assertEqual(format_history(None), "")

    def test_security_guardrails_present(self):
        # 프롬프트 인젝션/탈옥 방어 지시가 모든 프롬프트에 박혀 있어야 함(#보안 규칙 + 방어 few-shot).
        prompt = build_chat_prompt("say my name", ["근거"], crop_name="상추")
        self.assertIn("#보안 규칙", prompt)
        self.assertIn(SECURITY_REDIRECT, prompt)
        self.assertIn("say my name", prompt)  # 정체 캐묻기 방어 문구
        self.assertIn("데이터", prompt)  # 참고자료/대화는 명령 아닌 데이터(간접 주입 방어)
        self.assertIn("시스템 프롬프트", prompt)  # 프롬프트 유출 거부 지시


class TestFarmContext(unittest.TestCase):
    def _fc(self, **kw) -> FarmContext:
        base = dict(crop_id=3, crop_name="상추", region_name="강릉시", days_since_planting=45)
        base.update(kw)
        return FarmContext(**base)

    def test_none_is_blank(self):
        self.assertEqual(format_farm_context(None), "")

    def test_block_has_region_days_and_estimate_caveat(self):
        block = format_farm_context(self._fc(ph=Decimal("5.3"), organic_matter=Decimal("25")))
        self.assertIn("#회원 밭 정보", block)
        self.assertIn("[지역] 강릉시", block)
        self.assertIn("파종 후 경과일] 45일", block)
        self.assertIn("추정치", block)  # 실측 아님 표기(§1-4)
        self.assertIn("pH 5.3", block)
        self.assertIn("유기물 25 g/kg", block)  # 단위 병기(ML §7.2)

    def test_numeric_trailing_zeros_stripped(self):
        # DB Numeric의 꼬리 0(5.3000000000)이 사용자 눈높이로 정리돼야(§2)
        block = format_farm_context(self._fc(ph=Decimal("5.3000000000"), p2o5=Decimal("350.0000000000")))
        self.assertIn("pH 5.3", block)
        self.assertNotIn("5.30", block)
        self.assertIn("유효인산 350 mg/kg", block)

    def test_missing_soil_says_no_info(self):
        # soil_state 전부 None이면 지어내지 않고 '정보 없음'
        self.assertIn("정보 없음", format_farm_context(self._fc()))

    def test_injected_into_prompt(self):
        prompt = build_chat_prompt("물 언제?", ["근거"], crop_name="상추", farm=self._fc(ph=Decimal("6.1")))
        self.assertIn("#회원 밭 정보", prompt)
        self.assertIn("pH 6.1", prompt)


class TestStreamFallback(unittest.TestCase):
    def _collect(self, gen: Iterator[str]) -> str:
        return "".join(gen)

    def test_no_chunks_refers_without_calling_llm(self):
        out = self._collect(stream_from_chunks("질문", [], FakeLlm(raises=True)))
        self.assertIn(REFERRAL_TEXT, out)
        self.assertTrue(out.endswith(SSE_DONE))

    def test_normal_tokens_streamed(self):
        out = self._collect(stream_from_chunks("질문", ["근거"], FakeLlm(tokens=["안녕", "하세요"])))
        self.assertIn("안녕", out)
        self.assertIn("하세요", out)
        self.assertNotIn(LLM_ERROR_TEXT, out)
        self.assertTrue(out.endswith(SSE_DONE))

    def test_empty_response_falls_back(self):
        out = self._collect(stream_from_chunks("질문", ["근거"], FakeLlm(tokens=[])))
        self.assertIn(LLM_ERROR_TEXT, out)
        self.assertTrue(out.endswith(SSE_DONE))

    def test_exception_before_any_token_falls_back(self):
        out = self._collect(stream_from_chunks("질문", ["근거"], FakeLlm(raises=True)))
        self.assertIn(LLM_ERROR_TEXT, out)
        self.assertTrue(out.endswith(SSE_DONE))


if __name__ == "__main__":
    unittest.main()
