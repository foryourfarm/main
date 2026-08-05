"""적합도 룰 엔진의 경계값·결측 방어 검증."""
import unittest
from decimal import Decimal

from app.models import CropGrowthGuide
from app.services.suitability_service import (
    ALLOWED_BOUNDARY_SCORE,
    ALLOWED_KINDS,
    LITERATURE_LIMIT_KIND,
    boundary_score,
    calculate_suitability,
    category_score,
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
    code_scores: dict[str, float | None] | None = None,
    cultivation_type: str | None = None,
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
        allowed_min_kind=allowed_min_kind,
        allowed_max_kind=allowed_max_kind,
        code_scores=code_scores,
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


class TestBoundaryScore(unittest.TestCase):
    """계약(outcomes/scripts/ml/scoring.py:61-85) `boundary_score`와의 값 대조 — 7개 경우 전부.

    🔴 NULL kind가 조용히 0점을 받는 것이 이번 작업의 최대 위험이다 — NULL=60(종전 동작)을
    명시적으로 못박는다.
    """

    def test_null_kind_keeps_previous_behavior_at_60(self):
        self.assertEqual(boundary_score(None), ALLOWED_BOUNDARY_SCORE)
        self.assertEqual(boundary_score(None), 60.0)

    def test_literature_limit_is_zero(self):
        self.assertEqual(boundary_score(LITERATURE_LIMIT_KIND), 0.0)
        self.assertEqual(boundary_score("literature_limit"), 0.0)

    def test_other_five_kinds_stay_at_60(self):
        for kind in ALLOWED_KINDS - {LITERATURE_LIMIT_KIND}:
            with self.subTest(kind=kind):
                self.assertEqual(boundary_score(kind), 60.0)

    def test_unknown_kind_raises(self):
        with self.assertRaises(ValueError):
            boundary_score("literture_limit")  # 오타

    def test_all_six_known_kinds_and_none_covered(self):
        """계약이 정의한 6개 kind + None 전부를 한 번에 대조한다."""
        expected = {
            None: 60.0,
            "literature_limit": 0.0,
            "cultivable_range": 60.0,
            "literature_threshold": 60.0,
            "derived": 60.0,
            "heuristic": 60.0,
            "not_applicable": 60.0,
        }
        self.assertEqual(set(expected) - {None}, ALLOWED_KINDS)
        for kind, score in expected.items():
            with self.subTest(kind=kind):
                self.assertEqual(boundary_score(kind), score)


class TestIndicatorScoreBoundaryKind(unittest.TestCase):
    """`_indicator_score`가 방향별 kind에 따라 허용경계 점수를 다르게 주는지(작업 2)."""

    def test_literature_limit_lower_boundary_scores_zero(self):
        g = guide("temp_day", "20", "22", "15", "30", allowed_min_kind="literature_limit")
        result = calculate_suitability([g], {"temp_day": 15})
        self.assertEqual(result["score"], 0.0)

    def test_literature_limit_upper_boundary_scores_zero(self):
        g = guide("temp_day", "20", "22", "15", "30", allowed_max_kind="literature_limit")
        result = calculate_suitability([g], {"temp_day": 30})
        self.assertEqual(result["score"], 0.0)

    def test_non_literature_limit_boundary_still_scores_60(self):
        g = guide("temp_day", "20", "22", "15", "30", allowed_min_kind="heuristic")
        result = calculate_suitability([g], {"temp_day": 15})
        self.assertEqual(result["score"], 60.0)

    def test_null_kind_boundary_still_scores_60(self):
        """kind 표기가 없는 밴드는 종전 동작(60)을 유지해야 한다 — 회귀 가드."""
        g = guide("temp_day", "20", "22", "15", "30")
        result = calculate_suitability([g], {"temp_day": 15})
        self.assertEqual(result["score"], 60.0)

    def test_literature_limit_risk_zone_stays_zero_throughout(self):
        """boundary=0이면 위험구간 전체가 0이다 — 감쇠할 여지가 없다(작업 2)."""
        g = guide("temp_day", "20", "22", "15", "30", allowed_max_kind="literature_limit")
        for value in (31, 33, 35):
            with self.subTest(value=value):
                self.assertEqual(calculate_suitability([g], {"temp_day": value})["score"], 0.0)


class TestCategoryScore(unittest.TestCase):
    """계약(outcomes/scripts/ml/scoring.py:162-181) `category_score`와의 계약 대조(작업 3)."""

    def test_known_code_returns_table_value(self):
        self.assertEqual(category_score(1, {"1": 100.0, "2": 75.0}), 100.0)

    def test_unknown_code_returns_none_not_zero(self):
        """표에 없는 코드(예: 99)는 채점 제외 — 0점이 아니다."""
        self.assertIsNone(category_score(99, {"1": 100.0, "2": 75.0}))

    def test_missing_code_returns_none(self):
        self.assertIsNone(category_score(None, {"1": 100.0}))

    def test_missing_code_scores_returns_none(self):
        self.assertIsNone(category_score(1, None))

    def test_calculate_suitability_routes_code_scores_guides_to_category_path(self):
        """code_scores가 있는 지침은 밴드 경로(_indicator_score)로 보내지 않는다(작업 3).

        지표명은 실제 대상(subsoil_texture, 심토토성)을 쓴다 — "ph"는 `_is_valid`가
        0~14로 검증해 등급코드(1~6, 99)를 그대로 넣으면 값 자체가 무효 처리된다.
        """
        g = guide("subsoil_texture", None, None, code_scores={"1": 100.0, "2": 75.0, "3": 50.0})
        result = calculate_suitability([g], {"subsoil_texture": 2})
        self.assertEqual(result["score"], 75.0)
        self.assertEqual(result["breakdown"]["subsoil_texture"]["status"], "category")

    def test_unscored_code_is_excluded_not_zeroed(self):
        """표에 없는 코드는 총점에서 제외된다 — 0점으로 채점되면 "판정 불가"가 "부적합"이 된다."""
        g = guide("subsoil_texture", None, None, code_scores={"1": 100.0})
        result = calculate_suitability([g], {"subsoil_texture": 99})
        self.assertIsNone(result["score"])
        self.assertEqual(result["risk_flags"], ["subsoil_texture:unscored_code"])


class TestRefutedRainfallMonthlyNeverBackfilled(unittest.TestCase):
    """`rainfall_monthly` 지침은 0013이 삭제했고 계약도 refuted 확정이다(작업 4).

    0013 이후 어떤 마이그레이션도 이 지표를 다시 INSERT하면 실패한다 — 근거:
    outcomes/README.md ForYourFarm 적용 체크리스트 10번.
    """

    def test_no_migration_after_0013_reinserts_rainfall_monthly(self):
        import re
        from pathlib import Path

        versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
        offenders = []
        for path in sorted(versions_dir.glob("*.py")):
            match = re.match(r"(\d{4})_", path.name)
            if not match or int(match.group(1)) <= 13:
                continue  # 0013 자체(그 downgrade가 되돌리는 용도)와 그 이전은 대상 밖.
            text = path.read_text(encoding="utf-8")
            upgrade_src = text.split("def downgrade")[0]  # downgrade()는 되돌리기용, 제외.
            if "rainfall_monthly" in upgrade_src and "insert" in upgrade_src.lower():
                offenders.append(path.name)
        self.assertEqual(
            offenders, [],
            f"rainfall_monthly가 0013 이후 다시 INSERT됐다: {offenders} — "
            "이 지표는 refuted 확정(outcomes/README.md 체크리스트 10번)이라 채점 대상이 아니다.",
        )


class TestBreakdownEvidenceFields(unittest.TestCase):
    """`IndicatorBreakdown`의 P6 근거 3필드(cultivation_type/boundary_kind/score_tier).

    finalplan.md P6: FE가 "이 기준은 시설재배 기준입니다"·"이 점수는 역산치를 넘은
    참고 점수입니다" 등을 표기하려면 breakdown 항목별로 근거가 실려야 한다.
    """

    def test_cultivation_type_is_passed_through_from_guide(self):
        g = guide("ph", "6.0", "7.0", cultivation_type="facility")
        result = calculate_suitability([g], {"ph": 6.5})
        self.assertEqual(result["breakdown"]["ph"]["cultivation_type"], "facility")

    def test_cultivation_type_none_when_guide_has_none(self):
        g = guide("ph", "6.0", "7.0")
        result = calculate_suitability([g], {"ph": 6.5})
        self.assertIsNone(result["breakdown"]["ph"]["cultivation_type"])

    def test_boundary_kind_is_none_for_optimal(self):
        g = guide("ph", "6.0", "7.0", "5.0", "8.0", allowed_min_kind="heuristic")
        result = calculate_suitability([g], {"ph": 6.5})
        self.assertEqual(result["breakdown"]["ph"]["status"], "optimal")
        self.assertIsNone(result["breakdown"]["ph"]["boundary_kind"])

    def test_boundary_kind_binds_to_lower_direction(self):
        """하한 이탈이면 allowed_min_kind가 나온다 — allowed_max_kind가 달라도 상관없다."""
        g = guide(
            "ph", "6.0", "7.0", "5.0", "8.0",
            allowed_min_kind="cultivable_range", allowed_max_kind="heuristic",
        )
        result = calculate_suitability([g], {"ph": 5.5})  # allowed구간, 하한 쪽
        self.assertEqual(result["breakdown"]["ph"]["status"], "allowed")
        self.assertEqual(result["breakdown"]["ph"]["boundary_kind"], "cultivable_range")

    def test_boundary_kind_binds_to_upper_direction(self):
        """상한 이탈이면 allowed_max_kind가 나온다 — 두 방향을 합치지 않는다."""
        g = guide(
            "ph", "6.0", "7.0", "5.0", "8.0",
            allowed_min_kind="cultivable_range", allowed_max_kind="heuristic",
        )
        result = calculate_suitability([g], {"ph": 7.5})  # allowed구간, 상한 쪽
        self.assertEqual(result["breakdown"]["ph"]["status"], "allowed")
        self.assertEqual(result["breakdown"]["ph"]["boundary_kind"], "heuristic")

    def test_boundary_kind_is_none_for_category(self):
        g = guide("subsoil_texture", None, None, code_scores={"1": 100.0, "2": 75.0})
        result = calculate_suitability([g], {"subsoil_texture": 2})
        self.assertEqual(result["breakdown"]["subsoil_texture"]["status"], "category")
        self.assertIsNone(result["breakdown"]["subsoil_texture"]["boundary_kind"])

    def test_score_tier_absent_for_unscored_statuses(self):
        """missing/invalid/invalid_guide/unscored_code는 3필드 전부 실리지 않는다(=None)."""
        missing_g = guide("ph", "6.0", "7.0")
        invalid_g = guide("ph", "6.0", "7.0")
        invalid_guide_g = guide("temp_day", None, None)
        unscored_g = guide("subsoil_texture", None, None, code_scores={"1": 100.0})
        result = calculate_suitability(
            [missing_g], {},
        )
        self.assertNotIn("score_tier", result["breakdown"]["ph"])
        result = calculate_suitability([invalid_g], {"ph": 20})
        self.assertNotIn("score_tier", result["breakdown"]["ph"])
        result = calculate_suitability([invalid_guide_g], {"temp_day": 20})
        self.assertNotIn("score_tier", result["breakdown"]["temp_day"])
        result = calculate_suitability([unscored_g], {"subsoil_texture": 99})
        self.assertNotIn("score_tier", result["breakdown"]["subsoil_texture"])

    def test_score_tier_reference_only_for_risk_beyond_derived_boundary(self):
        """사과 ca 상한(derived, 실제 DB값 5.0/6.0/4.5/6.5) 밖 위험 점수만 reference — 체크리스트 12번."""
        g = guide("ca", "5.0", "6.0", "4.5", "6.5", allowed_max_kind="derived")
        result = calculate_suitability([g], {"ca": 7.23})  # 전국 중앙값, 상한(6.5) 밖
        self.assertEqual(result["breakdown"]["ca"]["status"], "risk")
        self.assertEqual(result["breakdown"]["ca"]["score_tier"], "reference")

    def test_score_tier_literature_when_within_derived_allowed_band(self):
        """같은 derived 경계라도 허용구간 안(status=allowed)이면 literature다."""
        g = guide("ca", "5.0", "6.0", "4.5", "6.5", allowed_max_kind="derived")
        result = calculate_suitability([g], {"ca": 6.2})  # optimal_max(6.0)~allowed_max(6.5) 사이
        self.assertEqual(result["breakdown"]["ca"]["status"], "allowed")
        self.assertEqual(result["breakdown"]["ca"]["score_tier"], "literature")

    def test_score_tier_literature_when_risk_beyond_heuristic_boundary(self):
        """derived가 아닌 성격(예: heuristic)의 위험구간은 literature다."""
        g = guide("ph", "6.0", "7.0", "5.0", "8.0", allowed_max_kind="heuristic")
        result = calculate_suitability([g], {"ph": 8.5})  # 허용경계(8.0) 밖
        self.assertEqual(result["breakdown"]["ph"]["status"], "risk")
        self.assertEqual(result["breakdown"]["ph"]["score_tier"], "literature")

    def test_score_tier_literature_for_optimal_and_category(self):
        g1 = guide("ph", "6.0", "7.0")
        g2 = guide("subsoil_texture", None, None, code_scores={"1": 100.0})
        result = calculate_suitability([g1, g2], {"ph": 6.5, "subsoil_texture": 1})
        self.assertEqual(result["breakdown"]["ph"]["score_tier"], "literature")
        self.assertEqual(result["breakdown"]["subsoil_texture"]["score_tier"], "literature")


if __name__ == "__main__":
    unittest.main()
