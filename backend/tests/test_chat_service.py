"""챗봇 프롬프트 조립 + 스트리밍 폴백의 결정론 경계 검증. 네트워크/DB 불필요(가짜 LLM만).

실행: backend/.venv/Scripts/python.exe -m unittest tests.test_chat_service   (backend/ 에서)
"""

import re
import unittest
from collections import Counter
from collections.abc import Iterator
from decimal import Decimal

from app.prompts.chatbot import (
    ASK_CROP_TEXT,
    REFERRAL_TEXT,
    SECURITY_REDIRECT,
    FarmContext,
    _FEWSHOT,
    _SYSTEM,
    build_chat_prompt,
    format_context,
    format_crop,
    format_farm_context,
    format_history,
)
from app.services import chat_service
from app.services.chat_service import LLM_ERROR_TEXT, SSE_DONE, stream_from_chunks
from app.services.short_term_service import SOIL_LIMITATION


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


class TestFewshotCropBalance(unittest.TestCase):
    """few-shot 작물 편중 회귀 방지.

    프로덕션에서 사과밭 질문에 답이 "상추밭과 마찬가지로"로 시작했다. RAG는 정상이었고
    (사과로 필터됨, 사과 조각에 상추 언급 0건) 원인은 few-shot 4개 중 3개가 `[작물] 상추`인
    것이었다 — 모델이 시연의 작물명을 옮긴 label bleed. 예시를 늘리거나 고칠 때 한 작물이
    다시 과반이 되는 것을 막는다.
    """

    def _labels(self) -> list[str]:
        return re.findall(r"\[작물\] (.+)", _FEWSHOT)

    def test_no_single_crop_is_majority(self):
        labels = self._labels()
        self.assertGreaterEqual(len(labels), 3, "few-shot 예시가 너무 적다")
        crops = [x for x in labels if x != "(지정 안 됨)"]
        top = Counter(crops).most_common(1)[0]
        self.assertLessEqual(
            top[1],
            len(crops) // 2,
            f"'{top[0]}' 예시가 {top[1]}/{len(crops)}로 과반이다 — label bleed가 재발한다",
        )

    def test_forbids_mentioning_other_crops(self):
        # 규칙 문구가 사라지면 모델이 다시 다른 작물을 끌어온다.
        self.assertIn("다른 작물을 언급하거나 비교하지 마라", _SYSTEM)


class TestSoilLimitationHonesty(unittest.TestCase):
    """토양 한계 문구가 없는 기능을 있다고 말하지 않는지.

    §18-4는 보통 "한계를 숨기지 마라"인데, 이 문구는 거꾸로 위반했다 — "행위 영향을 반영한
    추정치"라고 했지만 반영하는 코드가 없다(soil_delta는 shadow 전용이라 유저 경로에서
    호출되지 않고, soil_change_rule은 읽는 코드가 0건). 초보자가 "내 작업이 반영된 내 땅
    수치"로 믿게 되므로 과소 표기보다 나쁘다.
    """

    def test_does_not_claim_action_effects(self):
        self.assertNotIn("행위 영향", SOIL_LIMITATION)

    def test_says_not_measured_on_this_farm(self):
        # 지역 표본 평균임을 밝혀야 한다 — "내 밭 실측"으로 읽히면 안 된다.
        self.assertIn("직접 측정한 값이", SOIL_LIMITATION)

    def test_does_not_hardcode_eupmyeondong_unit(self):
        # 등록 단위가 법정동 말단이라 리로 등록된 밭도 있다. 단위를 하나로 못 박으면 거짓이 된다.
        self.assertNotIn("읍면동", SOIL_LIMITATION)


if __name__ == "__main__":
    unittest.main()


class TestStripMarkdownStream(unittest.TestCase):
    """마크다운 제거는 결정론적 후처리다 — 프롬프트로는 6회 실측 전부 실패했다.

    프론트가 마크다운을 렌더하지 않고 `white-space: pre-wrap`으로 평문 출력하므로
    `**노균병**`이 별표까지 화면에 보인다.
    """

    def _run(self, tokens: list[str]) -> str:
        return "".join(chat_service.strip_markdown_stream(iter(tokens)))

    def test_removes_bold_within_one_token(self):
        self.assertEqual(self._run(["- **노균병**: 잎을 보세요"]), "- 노균병: 잎을 보세요")

    def test_removes_bold_split_across_tokens(self):
        """스트리밍이라 `**`가 쪼개져 온다 — 홀드백 없이는 이 케이스가 통과 못 한다."""
        self.assertEqual(self._run(["**", "노균병", "**", ": 확인"]), "노균병: 확인")

    def test_removes_bold_split_one_star_at_a_time(self):
        self.assertEqual(self._run(["*", "*", "가", "*", "*", "나"]), "가나")

    def test_keeps_numbered_and_bullet_lists(self):
        """유저 요청은 '**1.** 대신 그냥 1.' — 목록 자체는 남긴다."""
        self.assertEqual(self._run(["1. 관찰\n2. 방제"]), "1. 관찰\n2. 방제")
        self.assertEqual(self._run(["- 관찰\n- 방제"]), "- 관찰\n- 방제")

    def test_lone_trailing_star_is_not_swallowed(self):
        """보류한 `*`를 버리면 데이터 손실이다 — 스트림 끝에 흘려보낸다."""
        self.assertEqual(self._run(["끝*"]), "끝*")

    def test_single_star_emphasis_is_left_alone(self):
        """`*` 하나는 곱셈·각주 등 정상 용례가 있어 건드리지 않는다(`**`만 노린다)."""
        self.assertEqual(self._run(["5*3=15"]), "5*3=15")

    def test_empty_stream_is_safe(self):
        self.assertEqual(self._run([]), "")
