"""장기 탭 월별 전망(히트맵)의 순수 계산부 검증. DB 없이 build_monthly_rows만 본다."""
import unittest
from datetime import date
from decimal import Decimal

from app.models import CropGrowthGuide, CropGrowthStage, SoilState, WeatherClimatology
from app.services.suitability_service import _guides_for_stage, build_monthly_rows

YEAR = 2026
PLANTING = date(2026, 3, 20)

# 시드(0007) 사과 단계와 동일한 DOY 범위 — 착색 8월하~10월중.
APPLE_STAGES = [
    CropGrowthStage(crop_id=1, growth_stage="fruit_growth", mode="day_of_year", range_start=111, range_end=263, priority=1),
    CropGrowthStage(crop_id=1, growth_stage="coloring", mode="day_of_year", range_start=233, range_end=293, priority=2),
    CropGrowthStage(crop_id=1, growth_stage="maturity", mode="day_of_year", range_start=294, range_end=314, priority=3),
]
# 시드(0004) 사과 지침 일부 — 단계 지침 + 전기간 공통(NULL) 지침.
APPLE_GUIDES = [
    CropGrowthGuide(crop_id=1, growth_stage="fruit_growth", indicator="temp_day", optimal_min=18, optimal_max=24, allowed_max=30, weight=2.0),
    CropGrowthGuide(crop_id=1, growth_stage="coloring", indicator="temp_day", optimal_min=12, optimal_max=13, weight=1.0),
    CropGrowthGuide(crop_id=1, growth_stage=None, indicator="organic", optimal_min=20, optimal_max=30, weight=1.0),
]
# 배(2)는 'growing' 단계 지침만 있고 전기간 공통 지침이 없다 → 겨울엔 지침 0건.
PEAR_STAGES = [
    CropGrowthStage(crop_id=2, growth_stage="growing", mode="day_of_year", range_start=121, range_end=293, priority=1),
]
PEAR_GUIDES = [
    CropGrowthGuide(crop_id=2, growth_stage="growing", indicator="temp_day", optimal_min=18.5, optimal_max=21.5, allowed_min=17, allowed_max=23, weight=2.0),
]

SOIL = SoilState(user_farm_id=1, ph=Decimal("6.3"), organic_matter=Decimal("25"), base_source="test")


def _clim(month: int, temp: str) -> WeatherClimatology:
    return WeatherClimatology(
        region_id=1, month=month, temp_avg_normal=Decimal(temp), source="test"
    )


# 월평년 기온을 12개월 모두 채운 케이스(값 자체는 검증용 임의치).
CLIM_ALL = {m: _clim(m, t) for m, t in enumerate(
    ["0", "2", "7", "13", "18", "22", "25", "26", "21", "15", "8", "2"], start=1
)}


class TestGuidesForStage(unittest.TestCase):
    def test_includes_stage_and_common_guides(self):
        picked = _guides_for_stage(APPLE_GUIDES, "coloring")
        indicators = {g.indicator for g in picked}
        self.assertEqual(indicators, {"temp_day", "organic"})  # coloring + 전기간 공통

    def test_none_stage_keeps_only_common(self):
        picked = _guides_for_stage(APPLE_GUIDES, None)
        self.assertEqual([g.indicator for g in picked], ["organic"])


class TestBuildMonthlyRows(unittest.TestCase):
    def test_returns_twelve_months_in_order(self):
        rows = build_monthly_rows(APPLE_STAGES, APPLE_GUIDES, CLIM_ALL, SOIL, PLANTING, YEAR)
        self.assertEqual([r["month"] for r in rows], list(range(1, 13)))

    def test_is_deterministic(self):
        first = build_monthly_rows(APPLE_STAGES, APPLE_GUIDES, CLIM_ALL, SOIL, PLANTING, YEAR)
        second = build_monthly_rows(APPLE_STAGES, APPLE_GUIDES, CLIM_ALL, SOIL, PLANTING, YEAR)
        self.assertEqual(first, second)

    def test_stage_follows_calendar_for_orchard(self):
        rows = {r["month"]: r for r in
                build_monthly_rows(APPLE_STAGES, APPLE_GUIDES, CLIM_ALL, SOIL, PLANTING, YEAR)}
        self.assertIsNone(rows[1]["growth_stage"])  # 겨울 — 어느 단계도 안 걸침
        self.assertEqual(rows[6]["growth_stage"], "fruit_growth")  # 6월 전체가 생장비대
        self.assertEqual(rows[9]["growth_stage"], "coloring")  # 착색 30일 > 생장비대 20일
        self.assertEqual(rows[10]["growth_stage"], "coloring")  # 착색 20일 > 성숙 11일

    def test_short_stage_across_month_boundary_still_appears(self):
        """사과 성숙(10월하~11월상)은 어느 달의 15일에도 안 걸린다 — 대표일 방식이면 소실됐다."""
        rows = build_monthly_rows(APPLE_STAGES, APPLE_GUIDES, CLIM_ALL, SOIL, PLANTING, YEAR)
        appeared = {r["growth_stage"] for r in rows}
        self.assertIn("maturity", appeared)
        self.assertEqual(
            [r["month"] for r in rows if r["growth_stage"] == "maturity"], [11]
        )
        # 시드에 있는 세 단계가 12칸 안에 모두 드러나야 한다(시즌 커리큘럼 누락 방지).
        self.assertTrue({"fruit_growth", "coloring", "maturity"} <= appeared)

    def test_winter_without_common_guides_is_out_of_season(self):
        rows = {r["month"]: r for r in
                build_monthly_rows(PEAR_STAGES, PEAR_GUIDES, CLIM_ALL, SOIL, PLANTING, YEAR)}
        self.assertEqual(rows[1]["status"], "out_of_season")  # 배 겨울 — 지침 자체가 없음
        self.assertIsNone(rows[1]["score"])
        self.assertEqual(rows[6]["status"], "ok")  # 생육기엔 채점됨

    def test_missing_climatology_month_does_not_crash(self):
        partial = {6: _clim(6, "22")}  # 6월만 평년치 있음
        rows = {r["month"]: r for r in
                build_monthly_rows(PEAR_STAGES, PEAR_GUIDES, partial, SOIL, PLANTING, YEAR)}
        # 평년치 없는 생육기 월은 지표 전부 결측 → 점수 없음이지만 예외로 죽지 않는다(§12).
        self.assertEqual(rows[7]["status"], "insufficient_data")
        self.assertIn("temp_day:missing", rows[7]["risk_flags"])
        self.assertEqual(rows[6]["status"], "ok")

    def test_no_stage_rows_falls_back_to_common_guides(self):
        # 오이·상추처럼 단계 시드가 없는 작물 — 12개월 모두 전기간 공통 지침으로 채점.
        lettuce_guides = [
            CropGrowthGuide(crop_id=5, growth_stage=None, indicator="temp_day",
                            optimal_min=15, optimal_max=20, allowed_min=4, allowed_max=30, weight=2.0)
        ]
        rows = build_monthly_rows([], lettuce_guides, CLIM_ALL, SOIL, PLANTING, YEAR)
        self.assertTrue(all(r["growth_stage"] is None for r in rows))
        self.assertTrue(all(r["status"] == "ok" for r in rows))


if __name__ == "__main__":
    unittest.main()
