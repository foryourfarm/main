"""장기 커리큘럼 서술 (app/services/long_term_advice_service.py, app/prompts/long_term_advice.py).

무엇을 지키려는 테스트인가:

- **규칙 문구가 품질 하한선**이다. LLM이 죽어도 이 문구만으로 화면이 완결돼야 하므로 분기
  네 개(위험 있음/없음/빈 창+다음작기/빈 창+다음작기 없음)를 전부 고정한다.
- **어미가 추정형이다.** 장기 점수는 예보가 아니라 최근 5년 관측 평균 + 3개월전망을 얹은
  이론 추정치다. "벗어납니다"로 단정하면 근사치를 확정 실측처럼 보여주는 것이라 §18-4를
  정면으로 어긴다. 규칙 문구 단계에서 못박은 것이므로 여기서 지킨다.
- **없는 기준을 지어내지 않는다**(§18-4). 허용 경계가 지침에 없으면 범위를 말하지 않아야 한다.
- **토양은 안 섞인다.** 단기와 같은 이유로 기상 지표만 서술한다.
- **캐시 지문이 낡음을 실제로 감지한다.** 이게 이 기능의 유일한 새 설계라 가장 촘촘히 본다.
  양방향으로 지킨다 — 문장이 달라지면 반드시 재생성되고(§18-4), 문장이 같으면 재생성하지
  않는다(§18-1). 단기와 같은 함수를 쓴다(`advice_cache.prompt_fingerprint`).
- **few-shot 작물 편중** — 챗봇 v5에서 실제로 터진 label bleed의 재발 방지(test_chat_service 선례).

DB는 타지 않는다(CI에 Postgres 없음). 캐시 경로는 upsert SQL이 아니라 해시·분기 판단을 본다.
"""

import re
import unittest
from collections import Counter
from datetime import datetime

from app.prompts import long_term_advice as prompt
from app.services import long_term_advice_service as svc
from app.services.advice_cache import prompt_fingerprint
from app.services.suitability_service import INDICATOR_NAMES, WEATHER_INDICATORS


def _month(
    year: int,
    month: int,
    *,
    stage: str | None = "growing",
    status: str = "ok",
    score: float | None = 80.0,
    grade: str | None = "A",
    flags: list[str] | None = None,
    breakdown: dict | None = None,
    published: datetime | None = None,
) -> dict:
    return {
        "year": year,
        "month": month,
        "growth_stage": stage,
        "status": status,
        "score": score,
        "grade": grade,
        "risk_flags": flags or [],
        "outlook_applied": published is not None,
        "outlook_published_at": published,
        "breakdown": breakdown or {},
    }


def _outlook(months: list[dict], *, next_season=None, crop_id: int = 1) -> dict:
    return {
        "farm_id": 1,
        "crop_id": crop_id,
        "region_id": 1,
        "label": "문헌 기반 예상 적합도",
        "months": months,
        "limitations": [],
        "next_season": next_season,
    }


NIGHT_COLD = _month(
    2026,
    9,
    flags=["temp_night_min:outside_allowed"],
    breakdown={"temp_night_min": {"value": 2.1, "allowed_min": 5.0, "allowed_max": 30.0}},
)


class TestSummarizeWindow(unittest.TestCase):
    def test_picks_up_weather_risk_with_value_and_bounds(self):
        (line,) = svc.summarize_window([_month(2026, 8), NIGHT_COLD])
        self.assertEqual(line.indicator, "temp_night_min")
        self.assertEqual((line.year, line.month), (2026, 9))
        self.assertEqual(line.value, 2.1)
        self.assertEqual(line.allowed_min, 5.0)

    def test_ignores_soil_indicators(self):
        """토양은 월별로 변하지 않아 3개월 어느 칸에서도 같은 말이 나온다 — 단기 탭 몫이다."""
        soil = _month(
            2026,
            8,
            flags=["organic:outside_allowed"],
            breakdown={"organic": {"value": 8.0, "allowed_min": 20.0, "allowed_max": None}},
        )
        self.assertEqual(svc.summarize_window([soil]), [])

    def test_skips_flag_without_value(self):
        """값이 없으면 서술할 근거가 없다 — 지어내지 않는다(§18-4)."""
        empty = _month(
            2026,
            8,
            flags=["temp_day:outside_allowed"],
            breakdown={"temp_day": {"value": None, "allowed_min": 10.0}},
        )
        self.assertEqual(svc.summarize_window([empty]), [])

    def test_keeps_only_earliest_month_per_indicator(self):
        """같은 지표가 두 달 걸리면 이른 달만. 3개월을 다 나열하면 문구만 길어진다."""
        later = _month(
            2026,
            10,
            flags=["temp_night_min:outside_allowed"],
            breakdown={"temp_night_min": {"value": -1.0, "allowed_min": 5.0}},
        )
        (line,) = svc.summarize_window([NIGHT_COLD, later])
        self.assertEqual(line.month, 9)

    def test_sorted_by_month_regardless_of_input_order(self):
        early = _month(
            2026,
            8,
            flags=["temp_day:outside_allowed"],
            breakdown={"temp_day": {"value": 30.0, "allowed_max": 24.0}},
        )
        out = svc.summarize_window([NIGHT_COLD, early])
        self.assertEqual([r.month for r in out], [8, 9])


class TestRuleAdvice(unittest.TestCase):
    """규칙 문구 네 분기. LLM이 죽어도 이 문구가 그대로 유저에게 나간다."""

    def test_risk_below_lower_bound(self):
        months = [_month(2026, 8), NIGHT_COLD]
        text = svc.rule_advice(svc.summarize_window(months), months, "생육기", None)
        self.assertIn("9월", text)
        self.assertIn("야간 최저기온이", text)  # 받침 있으면 "이"
        self.assertIn("2.1℃", text)
        self.assertIn("허용 범위(5℃ 이상)", text)
        self.assertIn("못 미칠 것으로 보입니다", text)

    def test_risk_above_upper_bound(self):
        hot = _month(
            2026,
            8,
            flags=["temp_day:outside_allowed"],
            breakdown={"temp_day": {"value": 27.3, "allowed_min": None, "allowed_max": 24.0}},
        )
        text = svc.rule_advice(svc.summarize_window([hot]), [hot], None, None)
        self.assertIn("허용 범위(24℃ 이하)", text)
        self.assertIn("벗어날 것으로 보입니다", text)

    def test_no_risk_states_window_and_stage(self):
        months = [_month(2026, 8), _month(2026, 9), _month(2026, 10)]
        text = svc.rule_advice([], months, "과실비대기", None)
        self.assertIn("2026년 8~10월", text)
        self.assertIn("큰 기상 위험이 예상되지 않습니다", text)
        self.assertIn("과실비대기", text)

    def test_dormant_window_with_next_season(self):
        months = [_month(2027, 1, stage=None, status="dormant", score=None, grade=None)]
        text = svc.rule_advice([], months, None, (2027, 3))
        self.assertIn("생육기가 아닙니다", text)
        self.assertIn("2027년 3월부터", text)

    def test_dormant_window_without_next_season(self):
        """감자는 파종후경과일 기준이라 달력으로 다음 작기가 정해지지 않는다(5종 중 감자뿐).

        이 분기가 없으면 수확 끝난 감자밭에서 문장이 잘린다.
        """
        months = [_month(2026, 9, stage=None, status="out_of_season", score=None, grade=None)]
        text = svc.rule_advice([], months, None, None)
        self.assertIn("생육기가 아닙니다", text)
        self.assertIn("다시 파종하시면", text)
        # 없는 달을 지어내지 않는다.
        self.assertNotRegex(text, r"\d+월부터 다시 안내")

    def test_missing_bound_does_not_invent_range(self):
        """허용 경계가 지침에 없는데 위험 판정이 났다 — 값만 알리고 기준은 말하지 않는다."""
        no_bound = _month(
            2026,
            8,
            flags=["sunlight:outside_allowed"],
            breakdown={"sunlight": {"value": 4.1, "allowed_min": None, "allowed_max": None}},
        )
        text = svc.rule_advice(svc.summarize_window([no_bound]), [no_bound], None, None)
        self.assertIn("4.1시간", text)
        self.assertNotIn("허용 범위", text)
        self.assertIn("것으로 보입니다", text)

    def test_empty_window_does_not_claim_safety(self):
        """창을 계산 못 한 것과 위험이 없는 것을 구분한다(단기 `horizon_days == 0`과 같은 이유)."""
        text = svc.rule_advice([], [], None, None)
        self.assertNotIn("위험이 예상되지 않습니다", text)

    def test_every_weather_indicator_has_a_korean_name(self):
        """지표가 늘었는데 이름이 없으면 문구에 영문 코드가 그대로 나간다."""
        for indicator in WEATHER_INDICATORS:
            with self.subTest(indicator=indicator):
                self.assertIn(indicator, INDICATOR_NAMES)


class TestEstimateTone(unittest.TestCase):
    """장기 문구는 전부 추정형이어야 한다 — 예보가 아니라 이론 추정치다(§18-4).

    프롬프트 규칙만으로 맡기지 않고 규칙 문구 단계에서 못박은 것이므로 여기서 지킨다.
    """

    def test_no_assertive_endings_in_risk_text(self):
        months = [NIGHT_COLD]
        text = svc.rule_advice(svc.summarize_window(months), months, None, None)
        # 단기가 쓰는 확정 어미가 장기로 새면 안 된다.
        self.assertNotIn("벗어납니다", text)
        self.assertNotIn("못 미칩니다", text)
        self.assertIn("것으로 보입니다", text)

    def test_prompt_keeps_tone_and_relative_month_rules(self):
        """두 규칙 다 §18-3/§18-4에 직접 걸린다 — "짧게 다듬는다"고 빠지면 안 된다."""
        built = prompt.build_prompt("사과", "8월 일 평균기온이 27.3℃로 …")
        self.assertIn(prompt.ESTIMATE_TONE_RULE, built)
        self.assertIn(prompt.RELATIVE_MONTH_RULE, built)


class TestWindowLabel(unittest.TestCase):
    def test_same_year(self):
        months = [_month(2026, 8), _month(2026, 10)]
        self.assertEqual(svc.window_label(months), "2026년 8~10월")

    def test_crosses_year(self):
        """창이 해를 넘기면 양쪽 연도를 적는다 — "11~1월"은 순서가 거꾸로 읽힌다."""
        months = [_month(2026, 11), _month(2027, 1)]
        self.assertEqual(svc.window_label(months), "2026년 11월 ~ 2027년 1월")


class TestInputFingerprint(unittest.TestCase):
    """캐시 무효화 판정. `get_or_create`가 실제로 밟는 경로 그대로 지문을 만들어 본다.

    지문 재료는 **LLM 프롬프트를 결정하는 전부**다(프롬프트 버전 + 작물명 + 규칙 문구).
    그래서 두 방향을 함께 지킨다:

    - 문장이 달라지면 **반드시** 지문이 바뀐다(낡은 문구가 남지 않는다, §18-4).
    - 문장이 같으면 지문도 같다(LLM을 헛되이 다시 부르지 않는다, §18-1).
    """

    def _fp(self, outlook: dict, crop_name: str = "사과") -> str:
        """서비스가 하는 것과 같은 순서 — 규칙 문구를 만들고 그것을 지문으로 삼는다."""
        months = outlook["months"]
        base = svc.rule_advice(
            svc.summarize_window(months), months, "생육기", outlook.get("next_season")
        )
        return prompt_fingerprint(prompt.PROMPT_VERSION, crop_name, base)

    def _plain(self) -> dict:
        return _outlook([_month(2026, 8), _month(2026, 9), _month(2026, 10)])

    def _risky(self) -> dict:
        return _outlook([_month(2026, 8), NIGHT_COLD, _month(2026, 10)])

    def test_deterministic(self):
        """같은 입력이면 항상 같은 지문 — 결정론(§2). 아니면 매 요청이 LLM을 다시 부른다."""
        self.assertEqual(self._fp(self._plain()), self._fp(self._plain()))

    def test_new_risk_invalidates(self):
        """위험이 새로 잡히면 문장이 달라진다 — 반드시 다시 만들어야 한다."""
        self.assertNotEqual(self._fp(self._plain()), self._fp(self._risky()))

    def test_changed_value_invalidates(self):
        """같은 위험이라도 값이 바뀌면 문장에 그 숫자가 들어가므로 지문이 바뀐다.

        3개월전망이 새로 발표돼 보정 기온이 달라지는 경로가 여기로 들어온다.
        """
        colder = _outlook(
            [
                _month(2026, 8),
                _month(
                    2026,
                    9,
                    flags=["temp_night_min:outside_allowed"],
                    breakdown={"temp_night_min": {"value": -3.0, "allowed_min": 5.0}},
                ),
                _month(2026, 10),
            ]
        )
        self.assertNotEqual(self._fp(self._risky()), self._fp(colder))

    def test_window_shift_invalidates(self):
        """창이 한 칸 밀리면 문구의 기간 표기가 달라진다."""
        later = _outlook([_month(2026, 9), _month(2026, 10), _month(2026, 11)])
        self.assertNotEqual(self._fp(self._plain()), self._fp(later))

    def test_crop_invalidates(self):
        """작물명이 프롬프트에 들어간다 — 밭 작물을 바꾸면 문구도 바뀌어야 한다."""
        self.assertNotEqual(self._fp(self._plain(), "사과"), self._fp(self._plain(), "배"))

    def test_prompt_version_invalidates(self):
        """프롬프트를 고쳤는데 캐시 때문에 반영이 안 되는 함정을 막는다."""
        before = self._fp(self._plain())
        original = prompt.PROMPT_VERSION
        try:
            prompt.PROMPT_VERSION = "longterm-test"
            after = self._fp(self._plain())
        finally:
            prompt.PROMPT_VERSION = original
        self.assertNotEqual(before, after)

    def test_score_change_alone_does_not_invalidate(self):
        """**점수·등급은 문구에 한 글자도 안 들어간다** — 바뀌어도 다시 만들 이유가 없다.

        히트맵은 새 점수를 보여주고 카드 문장은 그대로다. 종전 설계(월별 구조를 통째로
        해시)는 80.0 → 79.9에도 LLM을 다시 불렀다.
        """
        rescored = self._plain()
        rescored["months"][0]["score"] = 51.2
        rescored["months"][0]["grade"] = "C"
        self.assertEqual(self._fp(self._plain()), self._fp(rescored))

    def test_risk_flag_order_does_not_invalidate(self):
        """같은 위험이면 순서가 흔들려도 같은 지문 — `summarize_window`가 정렬한다."""
        one, two = self._risky(), self._risky()
        one["months"][1]["risk_flags"] = ["temp_night_min:outside_allowed", "x:missing"]
        two["months"][1]["risk_flags"] = ["x:missing", "temp_night_min:outside_allowed"]
        self.assertEqual(self._fp(one), self._fp(two))

    def test_is_sha256_hex(self):
        # 컬럼이 VARCHAR(64)다 — 길이가 벌어지면 마이그레이션이 아니라 INSERT가 죽는다
        # (`0023`의 source_ref 폭 초과 전례).
        self.assertRegex(self._fp(self._plain()), r"^[0-9a-f]{64}$")


class TestFewshotCropBalance(unittest.TestCase):
    """few-shot 작물 편중은 실제로 답변을 오염시킨 적이 있다(챗봇 v5 → "상추밭과 마찬가지로")."""

    def _crops(self) -> list[str]:
        return re.findall(r"\[작물\] (\S+)", prompt._SYSTEM)

    def test_no_single_crop_is_majority(self):
        crops = self._crops()
        self.assertGreaterEqual(len(crops), 3)
        top, count = Counter(crops).most_common(1)[0]
        self.assertLessEqual(
            count, len(crops) // 2, f"'{top}'이 예시 {len(crops)}개 중 {count}개다 — label bleed 위험"
        )

    def test_does_not_reuse_daily_advice_crops(self):
        """두 프롬프트를 합쳐 5작물이 고르게 나오도록 골랐다 — 겹치면 그 의도가 깨진다."""
        from app.prompts import daily_advice

        daily = set(re.findall(r"\[작물\] (\S+)", daily_advice._SYSTEM))
        overlap = set(self._crops()) & daily
        self.assertLessEqual(len(overlap), 1, f"단기 프롬프트와 {overlap}가 겹친다")

    def test_forbids_other_crops(self):
        self.assertIn("작물만 언급하라", prompt._SYSTEM)


if __name__ == "__main__":
    unittest.main()
