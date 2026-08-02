"""장기 탭 월별 전망(히트맵)의 순수 계산부 검증. DB 없이 build_monthly_rows만 본다."""
import unittest
from datetime import UTC, date, datetime
from decimal import Decimal

from app.models import CropGrowthGuide, CropGrowthStage, SoilState, WeatherClimatology
from app.services.suitability_service import (
    _guides_for_stage,
    build_monthly_rows,
    next_season_month,
    outlook_window,
)

YEAR = 2026
PLANTING = date(2026, 3, 20)
# 단계 판정·지침 적용은 12개월을 훑어야 검증이 되므로(착색기가 8~10월에만 있는 식) 창을
# 1년치로 명시해 넘긴다. 창 자체의 규칙(3개월·오늘 고정·연도 롤오버)은 TestOutlookWindow가 본다.
FULL_YEAR = [(YEAR, m) for m in range(1, 13)]

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
# 시드(0025) 상추 작기 — 봄 3/1~6/30, 가을 8/1~11/30(비윤년 DOY). 기상 지침은 두 작기에만,
# 토양은 전기간에 남는다 → 작기 밖은 기상 0건이라 dormant.
LETTUCE_STAGES = [
    CropGrowthStage(crop_id=5, growth_stage="spring", mode="day_of_year", range_start=60, range_end=181, priority=1),
    CropGrowthStage(crop_id=5, growth_stage="fall", mode="day_of_year", range_start=213, range_end=334, priority=2),
]
LETTUCE_GUIDES = [
    CropGrowthGuide(crop_id=5, growth_stage="spring", indicator="temp_day", optimal_min=22, optimal_max=24, allowed_min=2.5, allowed_max=36, weight=2.0),
    CropGrowthGuide(crop_id=5, growth_stage="fall", indicator="temp_day", optimal_min=22, optimal_max=24, allowed_min=2.5, allowed_max=36, weight=2.0),
    CropGrowthGuide(crop_id=5, growth_stage=None, indicator="ph", optimal_min=6.5, optimal_max=7.0, allowed_min=6.25, allowed_max=7.25, weight=1.5),
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
    def test_returns_exactly_the_requested_window(self):
        """창이 준 달만, 준 순서대로. 12개월 고정이던 시절의 전제를 여기서 끊는다."""
        rows = build_monthly_rows(APPLE_STAGES, APPLE_GUIDES, CLIM_ALL, SOIL, PLANTING, FULL_YEAR)
        self.assertEqual([r["month"] for r in rows], list(range(1, 13)))

        window = [(2026, 11), (2026, 12), (2027, 1)]
        rows = build_monthly_rows(APPLE_STAGES, APPLE_GUIDES, CLIM_ALL, SOIL, PLANTING, window)
        self.assertEqual([(r["year"], r["month"]) for r in rows], window)

    def test_is_deterministic(self):
        first = build_monthly_rows(APPLE_STAGES, APPLE_GUIDES, CLIM_ALL, SOIL, PLANTING, FULL_YEAR)
        second = build_monthly_rows(APPLE_STAGES, APPLE_GUIDES, CLIM_ALL, SOIL, PLANTING, FULL_YEAR)
        self.assertEqual(first, second)

    def test_stage_follows_calendar_for_orchard(self):
        rows = {r["month"]: r for r in
                build_monthly_rows(APPLE_STAGES, APPLE_GUIDES, CLIM_ALL, SOIL, PLANTING, FULL_YEAR)}
        self.assertIsNone(rows[1]["growth_stage"])  # 겨울 — 어느 단계도 안 걸침
        self.assertEqual(rows[6]["growth_stage"], "fruit_growth")  # 6월 전체가 생장비대
        self.assertEqual(rows[9]["growth_stage"], "coloring")  # 착색 30일 > 생장비대 20일
        self.assertEqual(rows[10]["growth_stage"], "coloring")  # 착색 20일 > 성숙 11일

    def test_short_stage_across_month_boundary_still_appears(self):
        """사과 성숙(10월하~11월상)은 어느 달의 15일에도 안 걸린다 — 대표일 방식이면 소실됐다."""
        rows = build_monthly_rows(APPLE_STAGES, APPLE_GUIDES, CLIM_ALL, SOIL, PLANTING, FULL_YEAR)
        appeared = {r["growth_stage"] for r in rows}
        self.assertIn("maturity", appeared)
        self.assertEqual(
            [r["month"] for r in rows if r["growth_stage"] == "maturity"], [11]
        )
        # 시드에 있는 세 단계가 12칸 안에 모두 드러나야 한다(시즌 커리큘럼 누락 방지).
        self.assertTrue({"fruit_growth", "coloring", "maturity"} <= appeared)

    def test_soil_only_winter_month_hides_score_as_dormant(self):
        """사과 겨울: 기상 지침이 안 걸려 토양만 채점됨 → 점수를 내보내지 않는다(§18-4)."""
        rows = {r["month"]: r for r in
                build_monthly_rows(APPLE_STAGES, APPLE_GUIDES, CLIM_ALL, SOIL, PLANTING, FULL_YEAR)}
        jan = rows[1]
        self.assertEqual(jan["status"], "dormant")
        self.assertIsNone(jan["score"])  # 100점이 그대로 나가면 "1월이 최적"으로 읽힌다
        self.assertIsNone(jan["grade"])
        # 생육기는 그대로 점수가 나온다
        self.assertEqual(rows[6]["status"], "ok")
        self.assertIsNotNone(rows[6]["score"])

    def test_winter_without_common_guides_is_out_of_season(self):
        rows = {r["month"]: r for r in
                build_monthly_rows(PEAR_STAGES, PEAR_GUIDES, CLIM_ALL, SOIL, PLANTING, FULL_YEAR)}
        self.assertEqual(rows[1]["status"], "out_of_season")  # 배 겨울 — 지침 자체가 없음
        self.assertIsNone(rows[1]["score"])
        self.assertEqual(rows[6]["status"], "ok")  # 생육기엔 채점됨

    def test_missing_climatology_month_does_not_crash(self):
        partial = {6: _clim(6, "22")}  # 6월만 평년치 있음
        rows = {r["month"]: r for r in
                build_monthly_rows(PEAR_STAGES, PEAR_GUIDES, partial, SOIL, PLANTING, FULL_YEAR)}
        # 평년치 없는 생육기 월은 지표 전부 결측 → 점수 없음이지만 예외로 죽지 않는다(§12).
        self.assertEqual(rows[7]["status"], "insufficient_data")
        self.assertIn("temp_day:missing", rows[7]["risk_flags"])
        self.assertEqual(rows[6]["status"], "ok")

    def test_no_stage_rows_falls_back_to_common_guides(self):
        # 오이처럼 단계 시드가 없는 작물 — 12개월 모두 전기간 공통 지침으로 채점.
        cucumber_guides = [
            CropGrowthGuide(crop_id=3, growth_stage=None, indicator="temp_day",
                            optimal_min=15, optimal_max=20, allowed_min=4, allowed_max=30, weight=2.0)
        ]
        rows = build_monthly_rows([], cucumber_guides, CLIM_ALL, SOIL, PLANTING, FULL_YEAR)
        self.assertTrue(all(r["growth_stage"] is None for r in rows))
        self.assertTrue(all(r["status"] == "ok" for r in rows))

    def test_lettuce_scores_only_inside_cropping_season(self):
        """0025: 상추 작기 밖(한여름·한겨울)은 dormant로 접힌다 — 사과 겨울과 같은 동작."""
        rows = {r["month"]: r for r in
                build_monthly_rows(LETTUCE_STAGES, LETTUCE_GUIDES, CLIM_ALL, SOIL, PLANTING, FULL_YEAR)}
        for month in (3, 4, 5, 6):
            self.assertEqual(rows[month]["growth_stage"], "spring", month)
        for month in (8, 9, 10, 11):
            self.assertEqual(rows[month]["growth_stage"], "fall", month)
        # 못 심는 달은 점수를 내보내지 않는다 — "1월 상추 40점"은 잘못된 신호다.
        for month in (1, 2, 7, 12):
            self.assertEqual(rows[month]["status"], "dormant", month)
            self.assertIsNone(rows[month]["score"], month)
        self.assertEqual(rows[5]["status"], "ok")
        self.assertIsNotNone(rows[5]["score"])


class TestOutlookWindow(unittest.TestCase):
    """창은 달력이 정하고 전망은 그 위에 얹는다(PRD §4.4)."""

    def test_starts_from_this_month(self):
        """이번 달이 빠지면 지금 농사 중인 달을 화면에서 잃는다 — 전망 창을 그대로 쓰던
        방식을 버린 이유가 이것이다."""
        self.assertEqual(outlook_window(date(2026, 8, 15)), [(2026, 8), (2026, 9), (2026, 10)])

    def test_does_not_jump_on_forecast_publication_day(self):
        """3개월전망은 매월 23일경 발표되고 발표월 다음 1~3개월을 준다. 창이 거기 묶여
        있으면 23일에 한 칸 점프해 이번 달이 사라진다. 달력 고정이라 그 일이 없다."""
        before = outlook_window(date(2026, 8, 22))
        after = outlook_window(date(2026, 8, 24))
        self.assertEqual(before, after)
        self.assertIn((2026, 8), after)

    def test_rolls_over_the_year(self):
        self.assertEqual(outlook_window(date(2026, 11, 1)), [(2026, 11), (2026, 12), (2027, 1)])
        self.assertEqual(outlook_window(date(2026, 12, 31)), [(2026, 12), (2027, 1), (2027, 2)])


class TestYearAwareCorrections(unittest.TestCase):
    """연도를 키에 넣지 않으면 다른 해의 같은 달 보정치가 **예외 없이 조용히** 붙는다."""

    WINDOW = [(2026, 12), (2027, 1)]

    def test_correction_does_not_leak_across_years(self):
        # 2026-01용 보정치만 있는 상태 — 창의 2027-01에 붙으면 안 된다.
        rows = build_monthly_rows(
            APPLE_STAGES, APPLE_GUIDES, CLIM_ALL, SOIL, PLANTING, self.WINDOW,
            corrections={(2026, 1, "temp_day"): Decimal("3.0")},
        )
        self.assertFalse(any(r["outlook_applied"] for r in rows))

    def test_correction_lands_on_the_right_year(self):
        rows = {(r["year"], r["month"]): r for r in build_monthly_rows(
            APPLE_STAGES, APPLE_GUIDES, CLIM_ALL, SOIL, PLANTING, self.WINDOW,
            corrections={(2027, 1, "temp_day"): Decimal("3.0")},
        )}
        self.assertTrue(rows[(2027, 1)]["outlook_applied"])
        self.assertFalse(rows[(2026, 12)]["outlook_applied"])


class TestOutlookPublishedAt(unittest.TestCase):
    """칸마다 다른 발표분에서 올 수 있어 발표일도 칸이 갖는다."""

    PUBLISHED = datetime(2026, 7, 23, 15, 0, tzinfo=UTC)

    def test_carries_publication_only_where_correction_applied(self):
        window = [(2026, 8), (2026, 9)]
        rows = {r["month"]: r for r in build_monthly_rows(
            APPLE_STAGES, APPLE_GUIDES, CLIM_ALL, SOIL, PLANTING, window,
            corrections={(2026, 8, "temp_day"): Decimal("1.0")},
            published_by_month={(2026, 8): self.PUBLISHED},
        )}
        self.assertEqual(rows[8]["outlook_published_at"], self.PUBLISHED)
        # 보정이 안 붙은 칸은 발표일도 없다 — 없는 근거를 있는 것처럼 두지 않는다(§18-4).
        self.assertIsNone(rows[9]["outlook_published_at"])


class TestNextSeasonMonth(unittest.TestCase):
    """창이 전부 휴면기면 다음 생육기를 알려준다. 창을 늘려 채우지는 않는다(PRD §4.4)."""

    def test_finds_first_month_with_a_stage(self):
        # 배는 DOY 121~293(5~10월)만 생육기 — 겨울 창 다음의 첫 생육 달은 5월이다.
        self.assertEqual(
            next_season_month(PEAR_STAGES, PLANTING, after=(2027, 1)), (2027, 5)
        )

    def test_rolls_over_the_year(self):
        self.assertEqual(
            next_season_month(PEAR_STAGES, PLANTING, after=(2026, 12)), (2027, 5)
        )

    def test_returns_none_when_crop_never_has_a_stage(self):
        """단계 시드가 없는 작물에 없는 시기를 지어내지 않는다."""
        self.assertIsNone(next_season_month([], PLANTING, after=(2026, 12)))


if __name__ == "__main__":
    unittest.main()
