"""적합도 룰 엔진의 경계값·결측 방어 검증."""
import unittest
from decimal import Decimal

from app.models import CropGrowthGuide
from app.services.suitability_service import calculate_suitability, pick_cultivation_type


def guide(
    indicator: str,
    optimal_min: str | None,
    optimal_max: str | None,
    allowed_min: str | None = None,
    allowed_max: str | None = None,
    weight: str = "1",
    risk_width: str | None = None,
    min_kind: str | None = None,
    max_kind: str | None = None,
    cultivation_type: str = "open_field",
) -> CropGrowthGuide:
    return CropGrowthGuide(
        crop_id=1,
        growth_stage="test",
        indicator=indicator,
        optimal_min=Decimal(optimal_min) if optimal_min else None,
        optimal_max=Decimal(optimal_max) if optimal_max else None,
        allowed_min=Decimal(allowed_min) if allowed_min else None,
        allowed_max=Decimal(allowed_max) if allowed_max else None,
        weight=Decimal(weight),
        risk_width=Decimal(risk_width) if risk_width else None,
        allowed_min_kind=min_kind,
        allowed_max_kind=max_kind,
        cultivation_type=cultivation_type,
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

    def test_one_sided_band_scores_full_above_open_optimal_max(self):
        """단측 밴드(사과 치환성 Ca "5~6cmol/kg 이상" 등, 2026-08-03): optimal_max가 없으면
        그 방향은 상한이 없다는 뜻이라 값이 아무리 커도 100점이어야 한다 — 예전엔
        optimal_max=None을 "지침 없음"으로 오인해 invalid_guide로 스킵시켰다."""
        result = calculate_suitability([guide("ca", "5", None, "4.5", None)], {"ca": 14.42})
        self.assertEqual(result["score"], 100.0)
        self.assertEqual(result["risk_flags"], [])

    def test_one_sided_band_still_scores_the_open_side(self):
        """상한이 없어도 하한 방향은 정상적으로 채점돼야 한다."""
        result = calculate_suitability([guide("ca", "5", None, "4.5", None)], {"ca": 4.0})
        self.assertEqual(result["risk_flags"], ["ca:outside_allowed"])
        self.assertLess(result["score"], 100.0)


class TestBoundaryKind(unittest.TestCase):
    """허용경계 점수가 성격별로 갈린다(0036). `literature_limit`만 0점."""

    def test_literature_limit_boundary_scores_zero(self):
        """문헌이 준 생리적 절대한계 = 생장이 멈추는 점. 60점(B등급 하한)이면 안 된다."""
        g = guide("temp_day", "15", "20", "2.5", "36", max_kind="literature_limit")
        self.assertEqual(calculate_suitability([g], {"temp_day": 36})["score"], 0.0)

    def test_other_kinds_keep_sixty(self):
        """±50% 휴리스틱·재배가능범위 경계는 종전 60점 그대로다."""
        for kind in (None, "heuristic", "cultivable_range", "literature_threshold"):
            with self.subTest(kind=kind):
                g = guide("temp_day", "15", "20", "2.5", "36", max_kind=kind)
                self.assertEqual(calculate_suitability([g], {"temp_day": 36})["score"], 60.0)

    def test_literature_limit_curve_still_falls_smoothly(self):
        """끝점만 0으로 내리고 곡선 모양은 그대로다 — 절벽이 되면 안 된다."""
        g = guide("temp_day", "15", "20", "2.5", "36", max_kind="literature_limit")
        scores = [calculate_suitability([g], {"temp_day": v})["score"] for v in (21, 26, 31, 36)]
        self.assertEqual(scores[-1], 0.0)
        for lower, higher in zip(scores[1:], scores):
            self.assertLess(lower, higher)

    def test_beyond_literature_limit_is_zero_not_decayed(self):
        """붕괴점을 넘었으면 더 깎을 것이 없다 — 위험구간 감쇠를 타지 않는다."""
        g = guide("temp_day", "15", "20", "2.5", "36", max_kind="literature_limit")
        self.assertEqual(calculate_suitability([g], {"temp_day": 36.5})["score"], 0.0)

    def test_min_and_max_kinds_are_independent(self):
        """방향별 2컬럼인 이유 — 사과 기온처럼 한쪽만 문헌값인 행이 실제로 있다."""
        g = guide("temp_day", "15", "20", "10", "25", min_kind="literature_limit")
        self.assertEqual(calculate_suitability([g], {"temp_day": 10})["score"], 0.0)
        self.assertEqual(calculate_suitability([g], {"temp_day": 25})["score"], 60.0)


class TestNationalTotal(unittest.TestCase):
    """국가 3단 구조 총점 — min(토양 가중평균, 기후 최대저해인자)."""

    def test_climate_limits_the_total(self):
        """토양이 아무리 좋아도 기후 한 지표가 나쁘면 총점이 거기 묶인다."""
        result = calculate_suitability(
            [
                guide("ph", "6", "7"),
                guide("p2o5", "300", "550"),
                guide("temp_day", "20", "22", "15", "30"),
            ],
            {"ph": 6.5, "p2o5": 400, "temp_day": 30},
        )
        self.assertEqual(result["score"], 60.0)  # min(토양 100, 기후 60)
        # 종전 총점은 병기된다 — 왜 내려갔는지 응답 안에서 답할 수 있어야 한다.
        self.assertAlmostEqual(result["score_weighted_mean"], 86.7, places=1)

    def test_soil_indicators_average_instead_of_min(self):
        """🔴 토양 안에서는 min이 아니라 합산이다. 평탄 min이면 여기서 60이 나온다."""
        result = calculate_suitability(
            [guide("ph", "6", "7"), guide("p2o5", "300", "550"), guide("organic", "20", "30")],
            {"ph": 6.5, "p2o5": 400, "organic": 15},  # organic만 나쁨
        )
        self.assertGreater(result["score"], 60.0)
        self.assertEqual(result["score"], result["score_weighted_mean"])

    def test_climate_layer_takes_the_worst_of_several(self):
        result = calculate_suitability(
            [guide("temp_day", "20", "22", "15", "30"), guide("temp_night_min", "10", "15")],
            {"temp_day": 21, "temp_night_min": 12},
        )
        self.assertEqual(result["score"], 100.0)
        result = calculate_suitability(
            [guide("temp_day", "20", "22", "15", "30"), guide("temp_night_min", "10", "15")],
            {"temp_day": 21, "temp_night_min": 30},  # 야간만 붕괴
        )
        self.assertEqual(result["score"], 0.0)

    def test_missing_layer_does_not_zero_the_total(self):
        """토양이 통째로 결측이어도 기후만으로 판정한다 — 데이터 부족이 부적합이 되면 안 된다."""
        result = calculate_suitability(
            [guide("ph", "6", "7"), guide("temp_day", "20", "22")],
            {"ph": None, "temp_day": 21},
        )
        self.assertEqual(result["score"], 100.0)
        self.assertIn("ph:missing", result["risk_flags"])

    def test_missing_indicator_is_excluded_not_filled(self):
        """결측을 50점 같은 중간값으로 메우지 않는다 — 남은 지표로만 계산한다."""
        both = calculate_suitability(
            [guide("ph", "6", "7"), guide("organic", "20", "30")],
            {"ph": 6.5, "organic": 25},
        )
        one_missing = calculate_suitability(
            [guide("ph", "6", "7"), guide("organic", "20", "30")],
            {"ph": 6.5, "organic": None},
        )
        self.assertEqual(both["score"], one_missing["score"])


class TestCultivationType(unittest.TestCase):
    def test_open_field_wins_when_both_rows_exist(self):
        rows = [
            guide("ph", "5.5", "6.2", cultivation_type="facility"),
            guide("ph", "5.5", "7.0", cultivation_type="open_field"),
        ]
        picked = pick_cultivation_type(rows)
        self.assertEqual(len(picked), 1)
        self.assertEqual(picked[0].cultivation_type, "open_field")
        # 순서가 반대여도 같아야 한다 — DB가 순서를 보장하지 않는다.
        self.assertEqual(pick_cultivation_type(rows[::-1])[0].cultivation_type, "open_field")

    def test_facility_only_falls_back(self):
        rows = [guide("ph", "5.5", "6.2", cultivation_type="facility")]
        self.assertEqual(pick_cultivation_type(rows)[0].cultivation_type, "facility")

    def test_different_stages_are_not_collapsed(self):
        """상추처럼 spring/fall 2행인 지표를 재배형 선택이 하나로 뭉개면 안 된다."""
        spring = guide("temp_night_min", "10", "15")
        spring.growth_stage = "spring"
        fall = guide("temp_night_min", "10", "15")
        fall.growth_stage = "fall"
        self.assertEqual(len(pick_cultivation_type([spring, fall])), 2)


if __name__ == "__main__":
    unittest.main()
