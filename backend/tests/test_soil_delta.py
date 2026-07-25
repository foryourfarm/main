"""토양변화 경량 추론의 결정론·중앙값 대치·artifact 검증 확인."""
import unittest
from pathlib import Path

from pydantic import ValidationError

from app.infra.ml.soil_delta import (
    SoilDeltaArtifact,
    TargetCoef,
    load_artifact,
    run_inference,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_soil_delta_artifact.json"


def make_artifact() -> SoilDeltaArtifact:
    # interval_days 계수만 non-zero → point = intercept + 0.01*interval, 검증이 쉽다.
    return SoilDeltaArtifact(
        model_version="test",
        data_version="test",
        features=["ph_t0", "organic_matter_t0", "available_p_t0", "interval_days"],
        feature_medians={
            "ph_t0": 6.0,
            "organic_matter_t0": 25.0,
            "available_p_t0": 300.0,
            "interval_days": 333.0,
        },
        targets={
            "delta_ph": TargetCoef(coef=[0.0, 0.0, 0.0, 0.01], intercept=0.1, conformal_q=1.2),
            "delta_organic_matter": TargetCoef(
                coef=[0.0, 0.0, 0.0, 0.0], intercept=-2.0, conformal_q=30.0
            ),
        },
    )


class TestSoilDeltaInference(unittest.TestCase):
    def test_load_fixture_artifact_parses(self):
        artifact = load_artifact(str(FIXTURE))
        self.assertEqual(artifact.model_version, "soil_delta_ridge_conformal_test")
        self.assertEqual(tuple(artifact.features)[0], "ph_t0")
        self.assertIn("delta_ph", artifact.targets)
        self.assertIn("delta_organic_matter", artifact.targets)

    def test_inference_math_is_point_plus_minus_q(self):
        artifact = make_artifact()
        values = {
            "ph_t0": 6.5,
            "organic_matter_t0": 20.0,
            "available_p_t0": 250.0,
            "interval_days": 100.0,
        }
        out, imputed = run_inference(artifact, values)
        # point = 0.1 + 0.01 * 100 = 1.1
        self.assertAlmostEqual(out["delta_ph"]["point"], 1.1)
        self.assertAlmostEqual(out["delta_ph"]["lo"], 1.1 - 1.2)
        self.assertAlmostEqual(out["delta_ph"]["hi"], 1.1 + 1.2)
        self.assertEqual(imputed, [])

    def test_missing_feature_uses_training_median_and_is_flagged(self):
        artifact = make_artifact()
        values = {
            "ph_t0": None,  # 결측 → 중앙값 6.0 대치
            "organic_matter_t0": 20.0,
            "available_p_t0": 250.0,
            "interval_days": 100.0,
        }
        out, imputed = run_inference(artifact, values)
        self.assertIn("ph_t0", imputed)
        # ph_t0 계수가 0이라 point는 안 바뀌지만 대치 기록은 남아야 한다.
        self.assertAlmostEqual(out["delta_ph"]["point"], 1.1)

    def test_deterministic_same_input_same_output(self):
        artifact = make_artifact()
        values = {"ph_t0": 6.5, "organic_matter_t0": 20.0, "available_p_t0": 250.0, "interval_days": 100.0}
        self.assertEqual(run_inference(artifact, values), run_inference(artifact, values))

    def test_wrong_feature_order_rejected(self):
        with self.assertRaises(ValidationError):
            SoilDeltaArtifact(
                model_version="x",
                data_version="x",
                features=["interval_days", "ph_t0", "organic_matter_t0", "available_p_t0"],
                feature_medians={},
                targets={
                    "delta_ph": TargetCoef(coef=[0, 0, 0, 0], intercept=0, conformal_q=1),
                    "delta_organic_matter": TargetCoef(coef=[0, 0, 0, 0], intercept=0, conformal_q=1),
                },
            )


if __name__ == "__main__":
    unittest.main()
