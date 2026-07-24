"""토양변화 서비스의 입력검증·유효인산 미채택·폴백·pH 구간 처리 확인."""
import unittest
from datetime import date, datetime
from decimal import Decimal

from app.core.errors import AppError
from app.models import SoilStateSnapshot
from app.schemas.soil_delta import SoilDeltaPrediction
from app.services import soil_delta_service as svc
from tests.test_soil_delta import make_artifact


def snapshot(ph="6.5", om="20.0", ap="250.0", measured=datetime(2025, 1, 1)) -> SoilStateSnapshot:
    return SoilStateSnapshot(
        user_farm_id=1,
        measured_at=measured,
        ph=Decimal(ph) if ph is not None else None,
        organic_matter=Decimal(om) if om is not None else None,
        available_p=Decimal(ap) if ap is not None else None,
        source="test",
    )


TARGET = date(2025, 7, 1)  # measured 2025-01-01 → 181일(학습 구간 내)


class TestSoilDeltaService(unittest.TestCase):
    def test_predicts_ph_and_organic_with_artifact(self):
        pred = svc.predict_soil_delta(snapshot(), TARGET, artifact=make_artifact())
        self.assertIsInstance(pred, SoilDeltaPrediction)
        ph = pred.predictions["ph"]
        self.assertTrue(ph.available)
        self.assertEqual(ph.prediction_type, "delta_regression")
        # point = 0.1 + 0.01*181 = 1.91; projected = 6.5 + 1.91
        self.assertAlmostEqual(ph.delta, 1.91)
        self.assertAlmostEqual(ph.projected_value, 6.5 + 1.91)
        self.assertIsNotNone(ph.lo)  # 내부 DTO엔 구간 존재(노출 단계에서 숨김)
        self.assertIn(svc.LIMITATION_PH_INTERVAL_HIDDEN, pred.limitations)

    def test_available_p_is_always_unavailable(self):
        pred = svc.predict_soil_delta(snapshot(), TARGET, artifact=make_artifact())
        ap = pred.predictions["available_p"]
        self.assertFalse(ap.available)
        self.assertEqual(ap.delta, 0.0)
        self.assertIsNone(ap.lo)
        self.assertIsNone(ap.hi)
        self.assertTrue(ap.fallback_used)
        self.assertEqual(ap.projected_value, 250.0)  # t0 carry-forward

    def test_invalid_horizon_is_blocked_before_model(self):
        with self.assertRaises(AppError) as ctx:
            svc.predict_soil_delta(snapshot(), date(2024, 12, 1), artifact=make_artifact())
        self.assertEqual(ctx.exception.code, "INVALID_HORIZON")

    def test_fallback_when_artifact_missing(self):
        pred = svc.predict_soil_delta(snapshot(), TARGET, artifact=None)
        self.assertEqual(pred.model_version, svc.FALLBACK_VERSION)
        for key in ("ph", "organic_matter"):
            p = pred.predictions[key]
            self.assertEqual(p.delta, 0.0)
            self.assertFalse(p.available)
            self.assertTrue(p.fallback_used)
        self.assertIn(svc.LIMITATION_MODEL_UNAVAILABLE, pred.limitations)

    def test_missing_t0_is_imputed_and_flagged(self):
        pred = svc.predict_soil_delta(snapshot(ph=None), TARGET, artifact=make_artifact())
        self.assertIn("ph_t0", pred.imputed_features)

    def test_horizon_out_of_range_flags_limitation(self):
        # measured 2025-01-01 → target 2030-01-01 ≈ 1826일 > max 1278
        pred = svc.predict_soil_delta(snapshot(), date(2030, 1, 1), artifact=make_artifact())
        self.assertIn(svc.LIMITATION_HORIZON_OOR, pred.limitations)

    def test_deterministic(self):
        a = svc.predict_soil_delta(snapshot(), TARGET, artifact=make_artifact())
        b = svc.predict_soil_delta(snapshot(), TARGET, artifact=make_artifact())
        self.assertEqual(a.model_dump(), b.model_dump())


if __name__ == "__main__":
    unittest.main()
