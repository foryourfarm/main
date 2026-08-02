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


class _FakeDb:
    """soil_advice가 쓰는 두 조회만 흉내낸다 — 실제 DB 없이 문구 규칙을 고정한다."""

    def __init__(self, bjd_code="4182031022", district_name="설악면 선촌리"):
        self._bjd, self._name = bjd_code, district_name

    def get(self, _model, _pk):
        return type("F", (), {"bjd_code": self._bjd})()

    def query(self, *_a):
        return self

    def filter(self, *_a):
        return self

    def scalar(self):
        return self._name


SOIL_DAY = {
    "target_date": D1,
    "risk_flags": ["p2o5:outside_allowed", "temp_day:outside_allowed"],
    "breakdown": {
        "p2o5": {"value": 118.0, "allowed_min": 200.0, "allowed_max": 300.0},
        "temp_day": {"value": 28.0, "allowed_min": 10.0, "allowed_max": 27.0},
    },
}


class TestSoilAdvice(unittest.TestCase):
    def test_states_district_not_the_farm(self):
        """값이 동·리 표본 평균이라 밭을 단정하면 §18-4 위반이다(SOIL_LIMITATION 전례)."""
        text = svc.soil_advice(_FakeDb(), 1, [SOIL_DAY], "사과")
        self.assertIn("설악면 선촌리", text)
        self.assertNotIn("회원님 밭은", text)
        self.assertNotIn("이 밭은 ", text)

    def test_includes_value_and_recommended_bound(self):
        text = svc.soil_advice(_FakeDb(), 1, [SOIL_DAY], "사과")
        self.assertIn("유효인산", text)
        self.assertIn("118", text)
        self.assertIn("200", text)
        self.assertIn("못 미칩니다", text)

    def test_excludes_weather_indicators(self):
        # 기상은 기상 문단이 다룬다 — 두 문단이 같은 말을 반복하면 안 된다.
        text = svc.soil_advice(_FakeDb(), 1, [SOIL_DAY], "사과")
        self.assertNotIn("낮 기온", text)

    def test_defers_dosage_to_agricultural_center_not_chatbot(self):
        # 비료 표준사용량 API 미연동 + 시비 시드 없음 → 수치를 지어내면 §18-3·§18-4 위반.
        # 챗봇으로도 보내지 않는다 — 실측(2026-08-02)으로 RAG가 무관한 조각을 주고도
        # 모델이 시비량을 지어내는 것을 확인했다(코사인 거리로 근거 유무가 안 갈린다).
        text = svc.soil_advice(_FakeDb(), 1, [SOIL_DAY], "사과")
        self.assertIn("농사로", text)
        self.assertIn("농업기술센터", text)
        self.assertNotIn("상담에서", text)  # 챗봇 유도 문구가 되돌아오면 안 된다
        self.assertNotIn("kg", text)
        self.assertNotIn("10a", text)

    def test_none_when_no_soil_risk(self):
        day = {
            "target_date": D1,
            "risk_flags": ["temp_day:outside_allowed"],
            "breakdown": {"temp_day": {"value": 28.0, "allowed_max": 27.0}},
        }
        self.assertIsNone(svc.soil_advice(_FakeDb(), 1, [day], "감자"))

    def test_none_when_no_days(self):
        self.assertIsNone(svc.soil_advice(_FakeDb(), 1, [], "감자"))

    def test_falls_back_when_district_unknown(self):
        # 구버전 등록 밭은 bjd_code가 없다 — 이름을 지어내지 말고 뭉뚱그린다.
        text = svc.soil_advice(_FakeDb(bjd_code=None), 1, [SOIL_DAY], "사과")
        self.assertIn("이 밭이 속한 지역의", text)

    def test_particle_follows_name_not_parenthesis(self):
        """"토양 산도(pH)이"가 아니라 "토양 산도가" — 괄호 병기 뒤에 조사를 붙이지 않는다."""
        self.assertEqual(svc._subject_josa("토양 산도(pH)"), "가")
        day = {
            "target_date": D1,
            "risk_flags": ["ph:outside_allowed"],
            "breakdown": {"ph": {"value": 4.9, "allowed_min": 5.5, "allowed_max": 7.0}},
        }
        text = svc.soil_advice(_FakeDb(), 1, [day], "상추")
        self.assertIn("토양 산도(pH)가", text)
        self.assertIn("못 미칩니다", text)

    def test_low_and_high_together_says_adjust(self):
        day = {
            "target_date": D1,
            "risk_flags": ["ph:outside_allowed", "p2o5:outside_allowed"],
            "breakdown": {
                "ph": {"value": 4.9, "allowed_min": 5.5, "allowed_max": 7.0},
                "p2o5": {"value": 438.4, "allowed_min": 200.0, "allowed_max": 350.0},
            },
        }
        text = svc.soil_advice(_FakeDb(), 1, [day], "사과")
        self.assertIn("못 미칩니다", text)
        self.assertIn("넘습니다", text)
        self.assertIn("조정", text)  # 한쪽만이면 보충/조절, 둘 다면 조정


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
