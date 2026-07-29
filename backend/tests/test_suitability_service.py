"""적합도 룰 엔진의 경계값·결측 방어 검증."""
import importlib.util
import unittest
from decimal import Decimal
from pathlib import Path
from types import ModuleType

from app.models import CropGrowthGuide
from app.services.suitability_service import INDICATOR_SOURCE_FIELDS, calculate_suitability

_VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def load_migration(name: str) -> ModuleType:
    """마이그레이션 모듈을 파일 경로로 불러온다 — 파일명이 숫자로 시작해 일반 import가 안 된다."""
    spec = importlib.util.spec_from_file_location(name, _VERSIONS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def guide(
    indicator: str,
    optimal_min: str,
    optimal_max: str,
    allowed_min: str | None = None,
    allowed_max: str | None = None,
    weight: str = "1",
    risk_width: str | None = None,
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
        risk_width=Decimal(risk_width) if risk_width else None,
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

    def test_allowed_range_is_log_discounted(self):
        # 완충폭 8(=30-22)의 절반 지점. 최적 이탈 시작점 95에서 로그로 내려와 85.9.
        result = calculate_suitability(
            [guide("temp_day", "20", "22", "15", "30")],
            {"temp_day": 26},
        )
        self.assertEqual(result["score"], 85.9)
        self.assertEqual(result["grade"], "A")

    def test_allowed_range_starts_below_optimal_and_ends_at_boundary(self):
        """최적 이탈 순간 95에서 시작(100에서 이어지지 않음), 허용경계에서 정확히 60."""
        g = [guide("temp_day", "20", "22", "15", "30")]
        # 최적경계 안쪽은 100, 바깥은 95 미만 — 이탈 자체에 고정 감점이 붙는다.
        self.assertEqual(calculate_suitability(g, {"temp_day": 22})["score"], 100.0)
        self.assertEqual(calculate_suitability(g, {"temp_day": 22.01})["score"], 95.0)
        self.assertLess(calculate_suitability(g, {"temp_day": 22.5})["score"], 95.0)
        # 허용경계 양쪽 끝은 60.0 — 등급 B 하한과 일치.
        self.assertEqual(calculate_suitability(g, {"temp_day": 30})["score"], 60.0)
        self.assertEqual(calculate_suitability(g, {"temp_day": 15})["score"], 60.0)
        # 최적에 가까울수록 완만, 허용경계에 가까울수록 가파르다.
        near = 95.0 - calculate_suitability(g, {"temp_day": 24})["score"]
        far = calculate_suitability(g, {"temp_day": 28})["score"] - 60.0
        self.assertLess(near, far)

    def test_risk_and_missing_are_reported_without_crash(self):
        # 허용상한(30) 초과 1도. 완충폭 8(=30-22)의 t=0.125 → 로그 감쇠로 60점 미만이지만 0은 아니다.
        result = calculate_suitability(
            [guide("temp_day", "20", "22", "15", "30"), guide("p2o5", "300", "550")],
            {"temp_day": 31},
        )
        self.assertEqual(result["score"], 40.4)
        self.assertEqual(result["grade"], "C")
        self.assertIn("temp_day:outside_allowed", result["risk_flags"])
        self.assertIn("p2o5:missing", result["risk_flags"])

    def test_risk_decays_monotonically_to_zero(self):
        """위험구간은 절벽이 아니라 완충폭 1배에 걸쳐 60→0으로 단조 감소한다."""
        g = [guide("temp_day", "20", "22", "15", "30")]  # 상단 완충폭 8 → 38도에서 0점
        scores = [calculate_suitability(g, {"temp_day": v})["score"] for v in (31, 33, 35, 37)]
        self.assertTrue(all(a > b for a, b in zip(scores, scores[1:])), scores)
        self.assertTrue(all(0 < s < 60 for s in scores), scores)
        for v in (38, 50):
            self.assertEqual(calculate_suitability(g, {"temp_day": v})["score"], 0.0)
        # 하한 쪽도 대칭: 완충폭 5(=20-15) → 10도에서 0점.
        self.assertEqual(calculate_suitability(g, {"temp_day": 10})["score"], 0.0)
        below = calculate_suitability(g, {"temp_day": 14})["score"]
        self.assertTrue(0 < below < 60, below)

    def test_risk_width_widens_decay_and_removes_cliff(self):
        """지침에 risk_width가 있으면 감쇠 거리가 완충폭이 아니라 그 값이 된다.

        완충폭이 좁아 이진적으로 채점되던 지표(예: 상추 pH optimal 6.5~7.0, 완충폭 0.25)를
        전국 실측 산포도(0.4641)로 넓히면 종전 0점이던 값에 점수가 매겨진다.
        """
        narrow = guide("ph", "6.5", "7.0", "6.25", "7.25")
        wide = guide("ph", "6.5", "7.0", "6.25", "7.25", risk_width="0.4641")
        # 전국 pH 중위 5.91 — 종전 완충폭(0.25)이면 0점 경계 6.0 밖이라 0점.
        self.assertEqual(calculate_suitability([narrow], {"ph": 5.91})["score"], 0.0)
        widened = calculate_suitability([wide], {"ph": 5.91})["score"]
        self.assertTrue(0 < widened < 60, widened)
        # 넓어져도 0점은 여전히 존재한다 — 감쇠폭 밖은 0(사용자 결정: 훨씬 먼 곳에서 도달).
        self.assertEqual(calculate_suitability([wide], {"ph": 5.5})["score"], 0.0)
        # 같은 값에서 넓은 감쇠폭이 항상 더 후하다(단조성).
        for v in (6.2, 6.1, 6.0, 5.95):
            self.assertGreaterEqual(
                calculate_suitability([wide], {"ph": v})["score"],
                calculate_suitability([narrow], {"ph": v})["score"],
            )

    def test_risk_width_absent_falls_back_to_buffer(self):
        """risk_width가 NULL인 지표(temp_night_min 등)는 종전 완충폭 기준을 그대로 쓴다."""
        g = [guide("temp_night_min", "20", "22", "15", "30")]  # 상단 완충폭 8 → 38도에서 0점
        self.assertEqual(calculate_suitability(g, {"temp_night_min": 38})["score"], 0.0)
        mid = calculate_suitability(g, {"temp_night_min": 33})["score"]
        self.assertTrue(0 < mid < 60, mid)

    def test_risk_without_allowed_band_stays_zero(self):
        """완충폭이 없으면 감쇠 척도를 못 정하므로 종전대로 0점."""
        result = calculate_suitability([guide("ph", "6", "7")], {"ph": 8})
        self.assertEqual(result["score"], 0.0)
        self.assertEqual(result["risk_flags"], ["ph:outside_allowed"])

    def test_all_invalid_returns_unscored_result(self):
        result = calculate_suitability([guide("ph", "6", "7")], {"ph": 15})
        self.assertIsNone(result["score"])
        self.assertIsNone(result["grade"])
        self.assertEqual(result["risk_flags"], ["ph:invalid"])


class TestSoilCationIndicators(unittest.TestCase):
    """0023이 배선한 치환성 K/Ca/Mg 채점(P3) 검증."""

    def test_cations_are_mapped_to_soil_state_columns(self):
        """매핑이 없으면 지침 행을 넣어도 값이 영원히 결측이다(P3의 근본 원인)."""
        for indicator in ("k", "ca", "mg"):
            self.assertEqual(INDICATOR_SOURCE_FIELDS[indicator], indicator)

    def test_lettuce_cation_guide_is_scored(self):
        """상추 K 지침(0.40~0.60, allowed 0.30~0.70, risk_width 0.5041)이 실제로 채점된다."""
        g = [guide("k", "0.40", "0.60", "0.30", "0.70", risk_width="0.5041")]
        self.assertEqual(calculate_suitability(g, {"k": 0.5})["score"], 100.0)
        self.assertEqual(calculate_suitability(g, {"k": 0.30})["score"], 60.0)
        risk = calculate_suitability(g, {"k": 0.2})["score"]
        self.assertTrue(0 < risk < 60, risk)
        # 값이 없는 밭(컬럼 신설 직후)은 0점이 아니라 결측으로 빠진다.
        missing = calculate_suitability(g, {"k": None})
        self.assertIsNone(missing["score"])
        self.assertEqual(missing["risk_flags"], ["k:missing"])

    def test_negative_cation_is_rejected_as_invalid(self):
        result = calculate_suitability([guide("ca", "6", "7", "5.5", "7.5")], {"ca": -1})
        self.assertEqual(result["risk_flags"], ["ca:invalid"])


class TestPotatoTuberAllowedBounds(unittest.TestCase):
    """0022가 채운 감자 tuber 허용하한(P2) 검증 — docs/guide-seed-known-issues.md."""

    # 0004 시드의 optimal. 여기 값이 바뀌면 0022의 하한도 함께 바뀌어야 한다.
    OPTIMAL = {"temp_day": (23.0, 24.0), "temp_night_min": (10.0, 14.0)}

    def test_allowed_min_follows_0019_heuristic(self):
        """`allowed_min = optimal_min - optimal 폭 x 0.5` — 0019·0021과 같은 산출식."""
        migration = load_migration("0022_potato_tuber_allowed_bounds")
        self.assertEqual(len(migration.TUBER_ALLOWED_MIN), 2)
        for indicator, allowed_min in migration.TUBER_ALLOWED_MIN:
            lo, hi = self.OPTIMAL[indicator]
            self.assertAlmostEqual(allowed_min, lo - (hi - lo) * 0.5, msg=indicator)

    def test_lower_bound_replaces_cliff_with_decay(self):
        """하한이 생기면 optimal 미만이 즉시 0점이 아니라 감쇠 점수를 받는다."""
        # temp_day: risk_width는 0020의 전국 실측 산포도(2.2408).
        before = guide("temp_day", "23", "24", None, "27", weight="2.5", risk_width="2.2408")
        after = guide("temp_day", "23", "24", "22.5", "27", weight="2.5", risk_width="2.2408")
        self.assertEqual(calculate_suitability([before], {"temp_day": 22.5})["score"], 0.0)
        self.assertEqual(calculate_suitability([after], {"temp_day": 22.5})["score"], 60.0)
        risk = calculate_suitability([after], {"temp_day": 22})["score"]
        self.assertTrue(0 < risk < 60, risk)
        # 최적구간은 불변 — 회귀 없음.
        self.assertEqual(calculate_suitability([after], {"temp_day": 23.5})["score"], 100.0)
        # 남은 한계(문서화됨): 감쇠폭 밖(약 20.26도 미만)은 여전히 0점이다.
        self.assertEqual(calculate_suitability([after], {"temp_day": 20})["score"], 0.0)

    def test_night_temp_falls_back_to_buffer_width(self):
        """temp_night_min은 risk_width가 NULL(P4) — 하한이 생기며 완충폭 폴백이 발동한다."""
        # 완충폭 2(=10-8) → 8도에서 60점, 6도에서 0점, 그 사이는 감쇠.
        g = [guide("temp_night_min", "10", "14", "8", "28", weight="2")]
        self.assertEqual(calculate_suitability(g, {"temp_night_min": 8})["score"], 60.0)
        mid = calculate_suitability(g, {"temp_night_min": 7.5})["score"]
        self.assertTrue(0 < mid < 60, mid)
        self.assertEqual(calculate_suitability(g, {"temp_night_min": 6})["score"], 0.0)


if __name__ == "__main__":
    unittest.main()
