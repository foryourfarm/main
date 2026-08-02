"""대시보드 단계 라벨 + 당일 값 선택 검증(순수 부분)."""
import unittest
from datetime import date

from app.services.dashboard_service import NO_FORECAST_LIMITATION, stage_label, today_values

TODAY = date(2026, 8, 1)


def _day(target: date, score: float | None, grade: str | None, stage: str = "tuber") -> dict:
    return {
        "target_date": target,
        "growth_stage": stage,
        "status": "ok",
        "score": score,
        "grade": grade,
        "risk_flags": [],
    }


class TestStageLabel(unittest.TestCase):
    def test_known_stage_maps_to_korean(self):
        self.assertEqual(stage_label("tuber", "ok"), "괴경비대기")
        self.assertEqual(stage_label("coloring", "ok"), "착색기")

    def test_none_stage_ok_is_all_period(self):
        self.assertEqual(stage_label(None, "insufficient_data"), "전기간")

    def test_none_stage_out_of_season(self):
        self.assertEqual(stage_label(None, "out_of_season"), "제철 아님")

    def test_unknown_code_passes_through(self):
        self.assertEqual(stage_label("weird", "ok"), "weird")


class TestTodayValues(unittest.TestCase):
    """카드 점수는 오늘 예보분이다 — 아무 날이나 집어오면 안 된다(PRD.md §4.3)."""

    LIMITS = ["예보는 발표마다 바뀝니다."]

    def test_picks_today_not_the_first_row(self):
        """발표시각에 따라 첫 행이 내일일 수 있다 — 그걸 오늘로 보여주면 조용한 거짓말이다."""
        st = {
            "days": [_day(date(2026, 8, 2), 40.0, "C"), _day(TODAY, 88.0, "A")],
            "limitations": self.LIMITS,
        }
        out = today_values(st, TODAY)
        self.assertEqual(out["score"], 88.0)
        self.assertEqual(out["grade"], "A")

    def test_missing_today_says_so_instead_of_going_blank(self):
        """빈 카드는 '위험 없음'으로 읽힌다 — 사유를 남겨야 한다(§12·§18-4)."""
        st = {"days": [_day(date(2026, 8, 3), 90.0, "S")], "limitations": self.LIMITS}
        out = today_values(st, TODAY)
        self.assertIsNone(out["score"])
        self.assertEqual(out["status"], "insufficient_data")
        self.assertIn(NO_FORECAST_LIMITATION, out["limitations"])

    def test_no_forecast_at_all_is_survivable(self):
        """외부 API 장애로 예보가 통째로 없어도 대시보드가 죽으면 안 된다(§12)."""
        out = today_values({"days": [], "limitations": []}, TODAY)
        self.assertIsNone(out["score"])
        self.assertEqual(out["status"], "insufficient_data")

    def test_never_falls_back_to_a_long_term_score(self):
        """장기 점수로 메우면 유저는 오늘 값인 줄 안다 — 폴백이 없음을 고정한다."""
        out = today_values({"days": [], "limitations": []}, TODAY)
        self.assertIsNone(out["grade"])
        self.assertIsNone(out["growth_stage"])

    def test_carries_the_days_own_stage_and_status(self):
        """단계는 날짜별로 다시 판정된다 — 오늘 행의 판정을 그대로 실어야 한다."""
        st = {"days": [_day(TODAY, 70.0, "B", stage="coloring")], "limitations": self.LIMITS}
        out = today_values(st, TODAY)
        self.assertEqual(out["growth_stage"], "coloring")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["limitations"], self.LIMITS)


if __name__ == "__main__":
    unittest.main()
