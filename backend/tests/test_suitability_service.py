"""적합도 룰 엔진의 경계값·결측 방어 검증."""
import unittest
from decimal import Decimal

from app.models import CropGrowthGuide
from app.services.suitability_service import (
    _pick_cultivation_type,
    boundary_score,
    calculate_suitability,
)


def guide(
    indicator: str,
    optimal_min: str | None,
    optimal_max: str | None,
    allowed_min: str | None = None,
    allowed_max: str | None = None,
    weight: str = "1",
    risk_width: str | None = None,
    allowed_min_kind: str | None = None,
    allowed_max_kind: str | None = None,
    cultivation_type: str | None = None,
) -> CropGrowthGuide:
    return CropGrowthGuide(
        crop_id=1,
        growth_stage="test",
        indicator=indicator,
        cultivation_type=cultivation_type,
        optimal_min=Decimal(optimal_min) if optimal_min else None,
        optimal_max=Decimal(optimal_max) if optimal_max else None,
        allowed_min=Decimal(allowed_min) if allowed_min else None,
        allowed_max=Decimal(allowed_max) if allowed_max else None,
        weight=Decimal(weight),
        risk_width=Decimal(risk_width) if risk_width else None,
        allowed_min_kind=allowed_min_kind,
        allowed_max_kind=allowed_max_kind,
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
    """허용경계 점수를 그 경계의 성격이 정한다(0032, FinalReport §1-9·§2-2)."""

    def test_literature_limit_boundary_is_zero(self):
        """생리적 절대한계(생장이 완전히 멈추는 점)는 60점이 아니라 0점이다.

        실제 사례는 상추 기온 2.5·36℃(발아 한계·복합장해)다 — 종전에는 생장이 멈추는
        온도가 B등급 하한을 받고 있었다.
        """
        lit = guide(
            "temp_day", "22", "24", "2.5", "36", weight="2",
            allowed_min_kind="literature_limit", allowed_max_kind="literature_limit",
        )
        self.assertEqual(calculate_suitability([lit], {"temp_day": 36})["score"], 0.0)
        self.assertEqual(calculate_suitability([lit], {"temp_day": 2.5})["score"], 0.0)
        # 경계 밖은 이미 0을 지났으므로 그대로 0이다(음수로 내려가지 않는다).
        self.assertEqual(calculate_suitability([lit], {"temp_day": 40})["score"], 0.0)
        # 최적구간 안은 그대로 100 — 성격은 경계에만 걸린다.
        self.assertEqual(calculate_suitability([lit], {"temp_day": 23})["score"], 100.0)

    def test_other_kinds_keep_sixty(self):
        """literature_limit 외의 성격은 전부 종전대로 60점이다(새 숫자를 만들지 않는다)."""
        for kind in ("heuristic", "cultivable_range", "literature_threshold",
                     "derived", "unverified", "not_applicable", None):
            with self.subTest(kind=kind):
                self.assertEqual(boundary_score(kind), 60.0)
                g = guide("temp_day", "22", "24", "2.5", "36",
                          allowed_min_kind=kind, allowed_max_kind=kind)
                self.assertEqual(calculate_suitability([g], {"temp_day": 36})["score"], 60.0)

    def test_kinds_are_read_per_direction(self):
        """한 지표 안에서 두 경계의 성격이 갈릴 수 있다 — 사과 기온이 실제 사례다.

        하한은 arccas 「가능지」 문헌값, 상한은 ±50% 휴리스틱이다. 한 컬럼으로 뭉치면
        둘 중 하나를 반드시 거짓 표기하게 된다.
        """
        g = guide(
            "temp_day", "18", "28", "13.5", "33",
            allowed_min_kind="literature_limit", allowed_max_kind="heuristic",
        )
        self.assertEqual(calculate_suitability([g], {"temp_day": 13.5})["score"], 0.0)
        self.assertEqual(calculate_suitability([g], {"temp_day": 33})["score"], 60.0)

    def test_allowed_range_stretches_when_boundary_is_zero(self):
        """경계가 0이면 허용구간이 0~95로 펴진다 — 감쇠 척도가 넓어지는 것이 §1-9의 목적이다."""
        lit = guide("temp_day", "22", "24", "2.5", "36",
                    allowed_min_kind="literature_limit", allowed_max_kind="literature_limit")
        old = guide("temp_day", "22", "24", "2.5", "36")
        for value in (26, 30, 34):
            with self.subTest(value=value):
                self.assertLess(
                    calculate_suitability([lit], {"temp_day": value})["score"],
                    calculate_suitability([old], {"temp_day": value})["score"],
                )


class TestCultivationTypePick(unittest.TestCase):
    """같은 지표에 노지·시설 두 행이 있으면 노지를 쓴다(0032·0033, FinalReport §1-1)."""

    def _pair(self):
        return [
            guide("ph", "5.5", "6.2", weight="1.5", cultivation_type="facility"),
            guide("ph", "5.5", "7.0", weight="1.5", cultivation_type="open_field"),
        ]

    def test_open_field_wins_regardless_of_order(self):
        for order in (self._pair(), list(reversed(self._pair()))):
            picked = _pick_cultivation_type(order)
            self.assertEqual(len(picked), 1, "지표가 두 번 채점되면 총점이 왜곡된다")
            self.assertEqual(picked[0].cultivation_type, "open_field")
            self.assertEqual(float(picked[0].optimal_max), 7.0)

    def test_facility_only_is_kept(self):
        """노지 행이 없으면 시설 행이 유일한 선택지라 그대로 쓴다(오이·상추 화학성)."""
        only = [guide("ec", "0", "2", cultivation_type="facility")]
        self.assertEqual(_pick_cultivation_type(only)[0].cultivation_type, "facility")

    def test_same_indicator_different_stage_is_not_deduped(self):
        """생육단계가 다르면 다른 지침이다 — 재배형 선택이 단계까지 뭉개면 안 된다."""
        a = guide("temp_day", "18", "24", cultivation_type="open_field")
        b = guide("temp_day", "12", "13", cultivation_type="open_field")
        b.growth_stage = "coloring"
        self.assertEqual(len(_pick_cultivation_type([a, b])), 2)


class TestMlcmTotal(unittest.TestCase):
    """총점이 가중평균이 아니라 최대저해인자법(구성 인자의 최솟값)이다(FinalReport §1-10 ⓐ)."""

    def _three(self):
        return [
            guide("temp_day", "14", "22", "11", "27", weight="2"),
            guide("ph", "5.5", "7.0", "4.75", "7.75", weight="1.5",
                  allowed_min_kind="heuristic", allowed_max_kind="heuristic"),
            guide("organic", "20", "30", "15", "35", allowed_max_kind="heuristic"),
        ]

    def test_score_is_the_minimum_not_the_mean(self):
        result = calculate_suitability(self._three(), {"temp_day": 18, "ph": 6.2, "organic": 34.0})
        scores = [entry["score"] for entry in result["breakdown"].values()]
        self.assertEqual(result["score"], min(scores))
        self.assertLess(result["score"], result["score_weighted_mean"])
        self.assertEqual(result["limiting_indicator"], "organic")

    def test_weighted_mean_is_still_reported(self):
        """종전 정의를 지우면 점수가 왜 달라졌는지 설명할 수 없다."""
        result = calculate_suitability(self._three(), {"temp_day": 18, "ph": 6.2, "organic": 34.0})
        self.assertIsNotNone(result["score_weighted_mean"])
        self.assertGreater(result["score_weighted_mean"], 0)

    def test_grade_follows_mlcm(self):
        """등급도 MLCM 점수로 판정한다 — 평균이 높아도 한 요인이 나쁘면 C가 나와야 한다."""
        guides = self._three()
        result = calculate_suitability(guides, {"temp_day": 18, "ph": 6.2, "organic": 60.0})
        self.assertEqual(result["score"], 0.0)
        self.assertEqual(result["grade"], "C")
        self.assertGreater(result["score_weighted_mean"], 60.0)

    def test_missing_indicators_are_excluded_from_the_minimum(self):
        """결측은 0점이 아니다 — min에 끌려들어가면 결측 하나가 총점을 0으로 만든다."""
        result = calculate_suitability(self._three(), {"temp_day": 18, "ph": 6.2})
        self.assertEqual(result["breakdown"]["organic"]["status"], "missing")
        self.assertEqual(result["score"], 100.0)
        self.assertEqual(result["limiting_indicator"], "temp_day")

    def test_no_scorable_indicator_returns_none(self):
        result = calculate_suitability(self._three(), {})
        self.assertIsNone(result["score"])
        self.assertIsNone(result["score_weighted_mean"])
        self.assertIsNone(result["limiting_indicator"])


if __name__ == "__main__":
    unittest.main()
