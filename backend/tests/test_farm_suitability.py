"""밭 적합도 오케스트레이션의 값수집·상태판정 검증(DB 없는 순수 부분)."""
import unittest
from decimal import Decimal

from app.models import SoilState, WeatherClimatology
from app.services.suitability_service import (
    derive_status,
    gather_indicator_values,
)


class TestGatherValues(unittest.TestCase):
    def test_temp_day_uses_monthly_normal_proxy(self):
        clim = WeatherClimatology(
            region_id=1, month=7, temp_avg_normal=Decimal("24.5"),
            temp_night_min_normal=Decimal("18"), rainfall_normal=Decimal("300"),
            sunlight_normal=Decimal("180"), source="test",
        )
        soil = SoilState(
            user_farm_id=1, ph=Decimal("6.3"), ec=Decimal("1.2"),
            p2o5=Decimal("400"), organic_matter=Decimal("25"), base_source="test",
        )
        values = gather_indicator_values(soil, clim)
        self.assertEqual(values["temp_day"], Decimal("24.5"))  # 월평년 근사
        self.assertEqual(values["ph"], Decimal("6.3"))
        self.assertEqual(values["organic"], Decimal("25"))

    def test_missing_sources_yield_none_not_crash(self):
        values = gather_indicator_values(None, None)
        self.assertTrue(all(v is None for v in values.values()))


class TestDeriveStatus(unittest.TestCase):
    def test_no_guides_is_out_of_season(self):
        self.assertEqual(derive_status(has_guides=False, score=None), "out_of_season")

    def test_guides_but_no_score_is_insufficient(self):
        self.assertEqual(derive_status(has_guides=True, score=None), "insufficient_data")

    def test_scored_is_ok(self):
        self.assertEqual(derive_status(has_guides=True, score=88.0), "ok")

    def test_weather_scored_is_ok(self):
        breakdown = {
            "temp_day": {"score": 86.0, "status": "allowed"},
            "organic": {"score": 100.0, "status": "optimal"},
        }
        self.assertEqual(derive_status(True, 90.0, breakdown), "ok")

    def test_soil_only_month_is_dormant(self):
        """사과 1월: 기상 지침이 안 걸려 토양 2개만 채점 → 100점이 나오지만 계절 판정이 아니다.

        이 상태로 점수를 노출하면 "1월이 사과에 최적(S)"으로 읽힌다(§18-4).
        """
        breakdown = {
            "organic": {"score": 100.0, "status": "optimal"},
            "p2o5": {"score": 100.0, "status": "optimal"},
        }
        self.assertEqual(derive_status(True, 100.0, breakdown), "dormant")

    def test_weather_present_but_all_missing_is_dormant(self):
        # 기상 지표가 지침엔 있으나 값이 결측이면 채점되지 않았으므로 판정 근거가 없다.
        breakdown = {
            "temp_day": {"status": "missing"},
            "organic": {"score": 100.0, "status": "optimal"},
        }
        self.assertEqual(derive_status(True, 100.0, breakdown), "dormant")


if __name__ == "__main__":
    unittest.main()
