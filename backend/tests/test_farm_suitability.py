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


if __name__ == "__main__":
    unittest.main()
