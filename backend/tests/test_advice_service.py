"""단기 행동추천 (app/services/advice_service.py, app/prompts/daily_advice.py).

무엇을 지키려는 테스트인가:

- **규칙 문구가 품질 하한선**이다. LLM이 죽어도 이 문구만으로 화면이 완결돼야 하므로,
  위험 유형별 문구가 실제로 나오는지 고정한다.
- **없는 기준을 지어내지 않는다**(§18-4). 허용 경계가 지침에 없으면 범위를 말하지 않아야 한다.
- **위험 없음과 예보 없음을 구분**한다. 예보를 못 받은 것을 "위험 없음"이라 하면 확보하지
  못한 정보를 안전하다고 말하는 셈이다.
- **토양은 안 섞인다.** persistent_risks가 같은 이유로 기상만 거르는 것과 일관돼야 한다.
- **few-shot 작물 편중** — 챗봇 v5에서 실제로 터진 label bleed의 재발 방지(test_chat_service 선례).

DB는 타지 않는다(CI에 Postgres 없음). 캐시 경로는 upsert SQL이 아니라 분기 판단을 본다.
"""

import re
import unittest
from collections import Counter
from datetime import date

from app.prompts import daily_advice
from app.services import advice_service as svc
from app.services.suitability_service import INDICATOR_NAMES, WEATHER_INDICATORS


def _day(target: date, flags: list[str], breakdown: dict) -> dict:
    return {"target_date": target, "risk_flags": flags, "breakdown": breakdown}


D1 = date(2026, 8, 2)
D2 = date(2026, 8, 3)


class TestSummarizeRisks(unittest.TestCase):
    def test_picks_up_weather_risk_with_value_and_bounds(self):
        days = [
            _day(
                D1,
                ["temp_night_min:outside_allowed"],
                {"temp_night_min": {"value": 3.2, "allowed_min": 5.0, "allowed_max": 30.0}},
            )
        ]
        (line,) = svc.summarize_risks(days, [])
        self.assertEqual(line.indicator, "temp_night_min")
        self.assertEqual(line.value, 3.2)
        self.assertEqual(line.allowed_min, 5.0)
        self.assertEqual(line.streak_days, 1)

    def test_soil_risk_is_excluded(self):
        # 토양은 며칠 안에 변하지 않아 매일 같은 말이 반복된다 — persistent_risks와 같은 규칙.
        days = [_day(D1, ["ph:outside_allowed"], {"ph": {"value": 4.1, "allowed_min": 5.5}})]
        self.assertEqual(svc.summarize_risks(days, []), [])

    def test_missing_flag_is_not_a_risk(self):
        days = [_day(D1, ["organic:missing"], {})]
        self.assertEqual(svc.summarize_risks(days, []), [])

    def test_keeps_only_earliest_date_per_indicator(self):
        bd = {"temp_night_min": {"value": 3.2, "allowed_min": 5.0}}
        days = [
            _day(D2, ["temp_night_min:outside_allowed"], bd),
            _day(D1, ["temp_night_min:outside_allowed"], bd),
        ]
        (line,) = svc.summarize_risks(days, [])
        self.assertEqual(line.target_date, D1, "가장 이른 날을 남겨야 '언제부터'가 맞는다")

    def test_streak_days_come_from_persistent_risks(self):
        bd = {"temp_night_min": {"value": 3.2, "allowed_min": 5.0}}
        days = [_day(D1, ["temp_night_min:outside_allowed"], bd)]
        persistent = [{"flag": "temp_night_min:outside_allowed", "days": 3, "dates": []}]
        (line,) = svc.summarize_risks(days, persistent)
        self.assertEqual(line.streak_days, 3)

    def test_value_none_is_skipped(self):
        # 값이 없으면 서술할 근거가 없다 — 지어내느니 빠지는 게 맞다.
        days = [_day(D1, ["temp_day:outside_allowed"], {"temp_day": {"value": None}})]
        self.assertEqual(svc.summarize_risks(days, []), [])


class TestRuleAdvice(unittest.TestCase):
    def _line(self, **kw):
        base = dict(
            indicator="temp_night_min",
            target_date=D1,
            value=3.2,
            allowed_min=5.0,
            allowed_max=30.0,
            streak_days=1,
        )
        base.update(kw)
        return svc.RiskLine(**base)

    def test_below_minimum_says_lower_bound(self):
        text = svc.rule_advice([self._line()], "괴경비대기", 3)
        self.assertIn("8월 2일", text)
        self.assertIn("야간 최저기온", text)
        self.assertIn("3.2℃", text)
        self.assertIn("5℃ 이상", text)

    def test_above_maximum_says_upper_bound(self):
        line = self._line(indicator="rainfall_daily", value=62.0, allowed_min=0.0, allowed_max=30.0)
        text = svc.rule_advice([line], None, 3)
        self.assertIn("62mm", text)
        self.assertIn("30mm 이하", text)

    def test_no_bound_in_guide_states_value_only(self):
        # 허용 경계가 지침에 없는데 위험 판정이 났다 — 범위를 지어내면 안 된다(§18-4).
        line = self._line(allowed_min=None, allowed_max=None)
        text = svc.rule_advice([line], None, 3)
        self.assertIn("3.2℃", text)
        self.assertNotIn("허용 범위", text)

    def test_subject_particle_matches_final_consonant(self):
        """규칙 문구는 LLM 실패 시 그대로 유저에게 나간다 — "이(가)"로 뭉개지 않는다."""
        self.assertEqual(svc._subject_josa("야간 최저기온"), "이")  # 온: 받침 ㄴ
        self.assertEqual(svc._subject_josa("일조"), "가")  # 조: 받침 없음
        self.assertEqual(svc._subject_josa("일 강수량"), "이")  # 량: 받침 ㅇ
        text = svc.rule_advice([self._line()], None, 3)
        self.assertNotIn("이(가)", text)
        self.assertIn("야간 최저기온이", text)

    def test_streak_is_mentioned(self):
        text = svc.rule_advice([self._line(streak_days=2)], None, 3)
        self.assertIn("2일 연속", text)

    def test_single_day_risk_has_no_streak_sentence(self):
        self.assertNotIn("연속", svc.rule_advice([self._line()], None, 3))

    def test_no_risk_mentions_stage(self):
        text = svc.rule_advice([], "과실비대기", 3)
        self.assertIn("위험 신호가 없습니다", text)
        self.assertIn("과실비대기", text)

    def test_no_forecast_is_not_reported_as_safe(self):
        text = svc.rule_advice([], None, 0)
        self.assertNotIn("위험 신호가 없습니다", text)
        self.assertIn("확보하지 못해", text)

    def test_every_weather_indicator_can_be_phrased(self):
        """지표가 늘었는데 이름·단위가 없으면 문구가 조용히 깨진다 — 그걸 여기서 막는다."""
        for indicator in sorted(WEATHER_INDICATORS):
            with self.subTest(indicator=indicator):
                self.assertIn(indicator, INDICATOR_NAMES, "한글명이 없다")
                self.assertIn(indicator, svc.UNITS, "단위가 없다")
                text = svc.rule_advice([self._line(indicator=indicator)], None, 3)
                self.assertIn(INDICATOR_NAMES[indicator], text)
                self.assertNotIn(indicator, text, "지표 코드가 그대로 노출됐다")


class _Llm:
    def __init__(self, out=None, boom=False):
        self.out, self.boom, self.prompts = out, boom, []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.boom:
            raise RuntimeError("LLM down")
        return self.out

    def generate_stream(self, prompt: str):  # pragma: no cover - 이 경로는 안 쓴다
        raise NotImplementedError


class TestPolish(unittest.TestCase):
    def test_success_returns_polished_text(self):
        self.assertEqual(svc.polish("기본", "감자", _Llm("다듬은 문구")), "다듬은 문구")

    def test_llm_failure_returns_none(self):
        # None이어야 호출부가 is_llm=false를 정확히 기록한다(base_text를 돌려주면 구분 불가).
        self.assertIsNone(svc.polish("기본", "감자", _Llm(boom=True)))

    def test_blank_response_returns_none(self):
        self.assertIsNone(svc.polish("기본", "감자", _Llm("   ")))

    def test_prompt_carries_base_text_and_crop(self):
        llm = _Llm("ok")
        svc.polish("야간 최저기온이 3.2℃입니다.", "오이", llm)
        prompt = llm.prompts[0]
        self.assertIn("야간 최저기온이 3.2℃입니다.", prompt)
        self.assertIn("[작물] 오이", prompt)


class TestPromptGuardrails(unittest.TestCase):
    """프롬프트에서 사라지면 안 되는 규칙들. 지워지면 LLM이 수치를 지어내기 시작한다."""

    def test_forbids_inventing_numbers(self):
        self.assertIn("지어내지 마라", daily_advice._SYSTEM)

    def test_forbids_other_crops(self):
        self.assertIn("다른 작물", daily_advice._SYSTEM)

    def test_forbids_changing_facts(self):
        self.assertIn("바꾸거나 빼지 마라", daily_advice._SYSTEM)

    def test_forbids_relative_dates(self):
        # 실측: 규칙 문구 "8월 2일"을 모델이 "모레까지"로 바꿔 하루가 어긋났다. 오늘이
        # 며칠인지 모르는 모델이 날짜를 계산한 것이라 §18-3(계산 위임 금지)에 걸린다.
        self.assertIn(daily_advice.RELATIVE_DATE_RULE, daily_advice._SYSTEM)

    def test_fewshot_outputs_keep_absolute_dates(self):
        # 예시가 상대 날짜를 시연하면 규칙을 적어둬도 모델이 예시를 따라간다(실제 원인).
        outputs = re.findall(r"\[출력\] (.+)", daily_advice._SYSTEM)
        self.assertGreaterEqual(len(outputs), 3)
        for out in outputs:
            with self.subTest(out=out[:30]):
                for word in ("오늘", "내일", "모레"):
                    self.assertNotIn(word, out, f"few-shot 출력에 상대 날짜 '{word}'가 있다")

    def test_no_single_crop_is_majority_in_fewshot(self):
        labels = re.findall(r"\[작물\] (.+)", daily_advice._SYSTEM)
        self.assertGreaterEqual(len(labels), 3, "few-shot 예시가 너무 적다")
        top, count = Counter(labels).most_common(1)[0]
        self.assertLessEqual(
            count,
            len(labels) // 2,
            f"'{top}' 예시가 {count}/{len(labels)}로 과반이다 — 챗봇 v5 label bleed 재발 경로",
        )

    def test_version_is_pinned(self):
        self.assertTrue(daily_advice.PROMPT_VERSION.startswith("advice-"))


if __name__ == "__main__":
    unittest.main()
