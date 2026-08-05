"""FarmML 이관 계약(`outcomes/`) 대비 백엔드 채점 계약 회귀 검증.

왜 이 파일이 있는가 (2026-08-05):
    종전에는 FarmML이 150지역 점수 CSV(`RegionalScore.csv`)를 산출해 그 분포로 채점
    회귀를 감시했다. 그런데 그 CSV는 **런타임에 읽히지 않는다** — 백엔드는 흙토람·기상청
    API 데이터와 DB `crop_growth_guide`로 자기 채점을 한다. 같은 밭에 두 점수가 나는
    구조였고, 이관되는 쪽이 서빙되지 않는 쪽이었다. 그래서 FarmML의 지역 점수 트랙을
    폐기하고(`outcomes/README.md` §이관 패키지 구성) **채점 회귀 검증을 이쪽으로 옮겼다.**

이 파일이 지키는 것:
    1. 곡선 상수가 이관된 `scoring.py`와 같다 — 한쪽만 바뀌면 같은 밭에 두 점수가 부활한다.
    2. 이관된 밴드가 백엔드 채점기가 가정하는 형태를 지킨다(단측 밴드 방향 일치 등).
    3. 감쇠폭 artifact가 존재하고 지표를 갖는다 — 없으면 위험구간 척도가 완충폭으로 조용히
       폴백한다(마이그레이션 0020이 이 값을 DB에 넣는다).
    4. FYF가 들고 있는 `outcomes/` 파일이 `VERSIONS.json` 대장과 일치한다 — 폐기된 버전의
       숫자를 서빙하던 사고(2026-08-05 감사 §P0-2)의 재발 방지 장치다.
    5. 아직 이관되지 않은 계약 2건(성격별 경계 점수·범주형 배점표)의 상태를 고정한다.

의도적으로 하지 않는 것:
    이관된 `scripts/ml/scoring.py`를 임포트해 값을 직접 대조하지 않는다 — 그 모듈은
    pandas·numpy를 요구하고 백엔드 `requirements.txt`에는 둘 다 없다. 테스트를 위해
    런타임 의존성을 늘리는 대신 상수는 텍스트로 읽어 대조한다(§14 불필요한 의존성 금지).
"""
import hashlib
import json
import re
import unittest
from pathlib import Path

from app.models import CropGrowthGuide
from app.services import suitability_service as svc

OUTCOMES = Path(__file__).resolve().parents[2] / "outcomes"
SHIPPED_SCORING = OUTCOMES / "scripts" / "ml" / "scoring.py"
CROP_RULES = OUTCOMES / "memory" / "crop_rules"
DISPERSION = OUTCOMES / "memory" / "indicator_dispersion.json"
VERSIONS = OUTCOMES / "VERSIONS.json"

# 백엔드 상수 ↔ 이관된 scoring.py 상수. 이름이 양쪽에서 같아 텍스트 대조가 가능하다.
CURVE_CONSTANTS = ("ALLOWED_BOUNDARY_SCORE", "OPTIMAL_EXIT_SCORE", "DECAY_CURVATURE")


def _shipped_constants() -> dict[str, float]:
    text = SHIPPED_SCORING.read_text(encoding="utf-8")
    found = {}
    for name in CURVE_CONSTANTS:
        match = re.search(rf"^{name}\s*=\s*([0-9.]+)", text, re.MULTILINE)
        if match:
            found[name] = float(match.group(1))
    return found


def _crop_rules() -> dict[str, dict]:
    return {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(CROP_RULES.glob("*.json"))
        if path.stem != "_shared"
    }


def _all_bands(crop: dict):
    """작물 규칙 안의 채점 밴드를 (지표명, 규칙) 쌍으로 훑는다."""
    for key in ("soil_overrides", "physical_overrides"):
        for indicator, rule in (crop.get(key) or {}).items():
            yield indicator, rule
    for group in ("temperature_guides", "precipitation_guides"):
        for rule in crop.get(group) or []:
            yield group, rule


class TestFarmMLCurveContract(unittest.TestCase):
    def test_outcomes_package_is_present(self):
        """이관물이 없으면 나머지 검증이 조용히 통과하는 것을 막는다."""
        self.assertTrue(SHIPPED_SCORING.is_file(), f"이관된 scoring.py 없음: {SHIPPED_SCORING}")
        self.assertTrue(DISPERSION.is_file(), f"감쇠폭 artifact 없음: {DISPERSION}")
        self.assertEqual(len(_crop_rules()), 5, "5작물 규칙 파일이어야 한다")

    def test_curve_constants_match_shipped_reference(self):
        """곡선 상수가 한쪽만 바뀌면 같은 밭에 두 점수가 부활한다."""
        shipped = _shipped_constants()
        self.assertEqual(
            set(shipped), set(CURVE_CONSTANTS),
            f"이관된 scoring.py에서 상수를 못 찾았다(찾은 것: {sorted(shipped)}). "
            "이름이 바뀌었으면 이 테스트의 CURVE_CONSTANTS도 같이 고쳐야 한다.",
        )
        for name, value in shipped.items():
            self.assertEqual(
                getattr(svc, name), value,
                f"{name}: 백엔드 {getattr(svc, name)} vs 이관 계약 {value} — 곡선이 갈렸다",
            )

    def test_allowed_boundary_is_b_grade_floor(self):
        """허용경계 점수(60)가 B등급 하한과 같아야 한다 — 등급 라벨과 점수가 어긋나면 안 된다."""
        self.assertEqual(svc._grade(svc.ALLOWED_BOUNDARY_SCORE), "B")
        self.assertEqual(svc._grade(svc.ALLOWED_BOUNDARY_SCORE - 0.1), "C")

    def test_optimal_exit_score_is_below_optimal_full_score(self):
        """최적 이탈 즉시 100에서 95로 떨어진다 — 이탈에 대가가 없으면 밴드가 무의미하다."""
        self.assertLess(svc.OPTIMAL_EXIT_SCORE, 100.0)
        self.assertGreater(svc.OPTIMAL_EXIT_SCORE, svc.ALLOWED_BOUNDARY_SCORE)


class TestShippedBandsAreScorable(unittest.TestCase):
    """이관된 밴드가 백엔드 채점기가 가정하는 형태를 지키는지."""

    def test_one_sided_bands_null_the_same_direction(self):
        """optimal이 없는 방향의 allowed도 비어야 한다 — 남으면 영원히 안 쓰이는 죽은 값이다."""
        for crop, rules in _crop_rules().items():
            for indicator, rule in _all_bands(rules):
                if "code_scores" in rule:
                    continue  # 범주형은 밴드가 아니다
                lo, hi = rule.get("optimal_min"), rule.get("optimal_max")
                alo, ahi = rule.get("allowed_min"), rule.get("allowed_max")
                self.assertFalse(
                    lo is None and hi is None,
                    f"{crop}.{indicator}: optimal 양쪽이 비었다 — 채점 불가",
                )
                self.assertFalse(
                    lo is None and alo is not None,
                    f"{crop}.{indicator}: optimal_min 없는데 allowed_min이 남았다",
                )
                self.assertFalse(
                    hi is None and ahi is not None,
                    f"{crop}.{indicator}: optimal_max 없는데 allowed_max가 남았다",
                )

    def test_two_sided_bands_do_not_have_half_allowed(self):
        """양측 밴드인데 allowed가 한쪽만 있으면 그 방향이 조용히 절벽(0점)이 된다."""
        for crop, rules in _crop_rules().items():
            for indicator, rule in _all_bands(rules):
                if "code_scores" in rule:
                    continue
                lo, hi = rule.get("optimal_min"), rule.get("optimal_max")
                if lo is None or hi is None:
                    continue
                alo, ahi = rule.get("allowed_min"), rule.get("allowed_max")
                self.assertEqual(
                    alo is None, ahi is None,
                    f"{crop}.{indicator}: 양측 밴드인데 allowed가 한쪽만 있다 "
                    f"(allowed_min={alo}, allowed_max={ahi}) — 반대쪽이 절벽이 된다",
                )

    def test_backend_scores_shipped_bands_without_crashing(self):
        """이관된 밴드 전부를 백엔드 채점기에 태워 예외·범위 밖 점수가 없음을 확인한다."""
        checked = 0
        for crop, rules in _crop_rules().items():
            for indicator, rule in _all_bands(rules):
                if "code_scores" in rule:
                    continue
                lo, hi = rule.get("optimal_min"), rule.get("optimal_max")
                guide = CropGrowthGuide(
                    indicator="ph",  # 범위 검증만 타는 값이라 지표명은 무관하다
                    optimal_min=lo,
                    optimal_max=hi,
                    allowed_min=rule.get("allowed_min"),
                    allowed_max=rule.get("allowed_max"),
                )
                center = lo if hi is None else (hi if lo is None else (float(lo) + float(hi)) / 2)
                for value in (float(center), float(center) * 0.5, float(center) * 2 + 1):
                    score, status = svc._indicator_score(value, guide)
                    self.assertTrue(
                        0.0 <= score <= 100.0,
                        f"{crop}.{indicator} value={value}: 점수 {score}가 0~100 밖이다",
                    )
                    self.assertIn(status, {"optimal", "allowed", "risk"})
                checked += 1
        self.assertGreater(checked, 20, f"밴드를 {checked}개만 검사했다 — 이관물이 비었는지 확인")

    def test_dispersion_artifact_carries_risk_widths(self):
        """감쇠폭이 없으면 위험구간이 완충폭으로 조용히 폴백한다(마이그레이션 0020의 입력)."""
        dispersion = json.loads(DISPERSION.read_text(encoding="utf-8"))
        widths = [
            (f"{section}.{name}", entry["risk_width"])
            for section in ("soil", "physical", "temp_by_crop")
            for name, entry in (dispersion.get(section) or {}).items()
            if isinstance(entry, dict) and "risk_width" in entry
        ]
        self.assertGreater(len(widths), 5, f"감쇠폭 항목이 {len(widths)}개뿐이다")
        for name, width in widths:
            self.assertGreaterEqual(width, 0.0, f"{name}: 음수 감쇠폭")


class TestOutcomesLedger(unittest.TestCase):
    """`VERSIONS.json` 대장 대조 — 폐기된 버전의 숫자를 서빙하던 사고의 재발 방지."""

    def test_every_file_matches_its_recorded_hash(self):
        ledger = json.loads(VERSIONS.read_text(encoding="utf-8"))
        mismatched, missing = [], []
        for rel, meta in ledger["files"].items():
            path = OUTCOMES / rel
            if not path.is_file():
                missing.append(rel)
                continue
            if hashlib.sha256(path.read_bytes()).hexdigest() != meta["sha256"]:
                mismatched.append(rel)
        self.assertEqual(missing, [], "대장에 있는데 실물이 없다 — 미러가 덜 돌았다")
        self.assertEqual(
            mismatched, [],
            "해시 불일치 — 이 파일들은 대장이 말하는 버전이 아니다. "
            "FarmML에서 `python scripts/export_outcomes.py` 후 미러를 다시 돌려야 한다.",
        )

    def test_ledger_declares_a_version(self):
        ledger = json.loads(VERSIONS.read_text(encoding="utf-8"))
        for key in ("knowledge_version", "scoring_version"):
            self.assertRegex(ledger[key], r"^\d{4}-\d{2}-\d{2}-v\d+$", f"{key} 형식이 다르다")


class TestUntransferredContractItems(unittest.TestCase):
    """계약에는 있고 백엔드에는 아직 없는 2건의 상태를 고정한다.

    이 테스트가 **실패하면** 백엔드가 해당 스키마를 갖게 된 것이다 — 그때는 채점 분기를
    구현하고 이 테스트를 계약 검증(값 대조)으로 바꿔야 한다. 지금 상태를 방치가 아니라
    기록으로 남기는 것이 목적이다. 근거: `outcomes/README.md` §아직 이관되지 않은 백엔드 짝 작업.
    """

    def test_boundary_kind_is_in_contract_but_not_in_schema(self):
        kinds = {
            rule.get("allowed_min_kind")
            for rules in _crop_rules().values()
            for _, rule in _all_bands(rules)
        } | {
            rule.get("allowed_max_kind")
            for rules in _crop_rules().values()
            for _, rule in _all_bands(rules)
        }
        self.assertIn(
            "literature_limit", kinds,
            "계약에서 literature_limit 성격이 사라졌다 — 그렇다면 이 테스트도 필요 없다",
        )
        self.assertFalse(
            hasattr(CropGrowthGuide, "allowed_min_kind"),
            "백엔드가 경계 성격 컬럼을 갖게 됐다 — scoring.boundary_score(kind) 분기를 "
            "구현하고(literature_limit이면 허용경계에서 60이 아니라 0점) 이 테스트를 값 대조로 바꿔라",
        )

    def test_category_scoring_is_in_contract_but_not_in_schema(self):
        categorical = [
            (crop, indicator)
            for crop, rules in _crop_rules().items()
            for indicator, rule in _all_bands(rules)
            if "code_scores" in rule
        ]
        self.assertTrue(categorical, "계약에서 범주형 배점표가 사라졌다 — 이 테스트도 불필요")
        self.assertFalse(
            hasattr(CropGrowthGuide, "code_scores"),
            f"백엔드가 범주형 배점표 컬럼을 갖게 됐다({categorical}) — "
            "scoring.category_score 분기를 구현하고(등급코드는 band_score에 넘기면 없는 "
            "순위를 가정한다) 이 테스트를 값 대조로 바꿔라",
        )


if __name__ == "__main__":
    unittest.main()
