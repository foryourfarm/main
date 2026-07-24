"""적합도 룰 엔진의 경계값·결측 방어 검증."""
import unittest
from decimal import Decimal

from app.models import CropGrowthGuide
from app.services.suitability_service import calculate_suitability


def guide(
    indicator: str,
    optimal_min: str,
    optimal_max: str,
    allowed_min: str | None = None,
    allowed_max: str | None = None,
    weight: str = "1",
) -> CropGrowthGuide:
    return CropGrowthGuide(
        crop_id=1,
        growth_stage="test",
        indicator=indicator,
        optimal_min=Decimal(optimal_min),
        optimal_max=Decimal(optimal_max),
        allowed_min=Decimal(allowed_min) if allowed_min else None,
        allowed_max=Decimal(allowed_max) if allowed_max else None,
        weight=Decimal(weight),
    )


class TestSuitabilityService(unittest.TestCase):
    def test_optimal_values_score_s(self):
        result = calculate_suitability(
            [guide("temp_day", "18", "24", weight="2"), guide("p2o5", "300", "550")],
            {"temp_day": 20, "p2o5": 400},
        )
        self.assertEqual(result["score"], 100.0)
        self.assertEqual(result["grade"], "S")
        self.assertEqual(result["risk_flags"], [])

    def test_allowed_range_is_linearly_discounted(self):
        result = calculate_suitability(
            [guide("temp_day", "20", "22", "15", "30")],
            {"temp_day": 26},
        )
        self.assertEqual(result["score"], 80.0)
        self.assertEqual(result["grade"], "A")

    def test_risk_and_missing_are_reported_without_crash(self):
        result = calculate_suitability(
            [guide("temp_day", "20", "22", "15", "30"), guide("p2o5", "300", "550")],
            {"temp_day": 31},
        )
        self.assertEqual(result["score"], 0.0)
        self.assertEqual(result["grade"], "C")
        self.assertIn("temp_day:outside_allowed", result["risk_flags"])
        self.assertIn("p2o5:missing", result["risk_flags"])

    def test_all_invalid_returns_unscored_result(self):
        result = calculate_suitability([guide("ph", "6", "7")], {"ph": 15})
        self.assertIsNone(result["score"])
        self.assertIsNone(result["grade"])
        self.assertEqual(result["risk_flags"], ["ph:invalid"])


if __name__ == "__main__":
    unittest.main()
