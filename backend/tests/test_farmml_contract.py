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
    5. 성격별 경계 점수(`boundary_score`)·범주형 배점표(`category_score`)가 백엔드
       구현에서 계약과 같은 값을 내는지 대조한다(finalplan.md P5). 종전에는 이 두 계약이
       "백엔드에 아직 없다"는 상태를 고정하는 자리였으나, P1(성격 메타 컬럼)·P2(채점 분기)·
       P4(사과·배 배점표 시드)로 백엔드가 두 계약을 실제로 구현했으므로 값 대조로 바꿨다.
    6. 배포 코드가 기록한 계약 버전(`app/core/contract_version.py`)이 `VERSIONS.json`
       대장과 같다 — 어긋나면 배포 코드가 다른 계약 버전을 서빙한다는 뜻이다.

의도적으로 하지 않는 것:
    이관된 `scripts/ml/scoring.py`를 임포트해 값을 직접 대조하지 않는다 — 그 모듈은
    pandas·numpy를 요구하고 백엔드 `requirements.txt`에는 둘 다 없다. 테스트를 위해
    런타임 의존성을 늘리는 대신 상수는 텍스트로 읽어 대조한다(§14 불필요한 의존성 금지).
"""
import hashlib
import importlib.util
import json
import re
import unittest
from pathlib import Path

from app.core.contract_version import KNOWLEDGE_VERSION, SCORING_VERSION
from app.models import CropGrowthGuide
from app.services import suitability_service as svc

OUTCOMES = Path(__file__).resolve().parents[2] / "outcomes"
SHIPPED_SCORING = OUTCOMES / "scripts" / "ml" / "scoring.py"
CROP_RULES = OUTCOMES / "memory" / "crop_rules"
DISPERSION = OUTCOMES / "memory" / "indicator_dispersion.json"
VERSIONS = OUTCOMES / "VERSIONS.json"
MIGRATIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"
KIND_BACKFILL_MIGRATION = MIGRATIONS / "0039_guide_boundary_kind_backfill.py"

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


def _shipped_literature_limit_kind() -> str:
    text = SHIPPED_SCORING.read_text(encoding="utf-8")
    match = re.search(r'^LITERATURE_LIMIT_KIND\s*=\s*"([a-z_]+)"', text, re.MULTILINE)
    assert match, "scoring.py에서 LITERATURE_LIMIT_KIND를 못 찾았다"
    return match.group(1)


def _shipped_allowed_kinds() -> frozenset[str]:
    """scoring.py의 `ALLOWED_KINDS`를 텍스트로 파싱한다(pandas·numpy 의존 회피, 위 docstring §14)."""
    text = SHIPPED_SCORING.read_text(encoding="utf-8")
    match = re.search(r"ALLOWED_KINDS\s*=\s*frozenset\(\{(.*?)\}\)", text, re.DOTALL)
    assert match, "scoring.py에서 ALLOWED_KINDS를 못 찾았다"
    return frozenset(re.findall(r'"([a-z_]+)"', match.group(1)))


def _shared_allowed_kind_enum() -> list[str]:
    """`_shared.json`의 `allowed_kind_enum` — 뜻·경계점수의 문서 쪽 단일 소스."""
    shared = json.loads((CROP_RULES / "_shared.json").read_text(encoding="utf-8"))
    return shared["allowed_kind_enum"]


def _load_kind_backfill_migration():
    spec = importlib.util.spec_from_file_location(
        "m0039_farmml_contract", KIND_BACKFILL_MIGRATION
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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

    def test_deployed_contract_version_matches_ledger(self):
        """배포 코드(`app/core/contract_version.py`)가 기록한 계약 버전이 대장과 같은지.

        어긋나면 "배포 코드가 다른 계약 버전을 서빙한다"는 뜻이다 — 그 상수는 런타임에
        `outcomes/`를 읽지 않고 문자열 리터럴로 박혀 있어(파일이 바뀌어도 조용히 안 따라가는
        것이 존재 이유) 사람이 갱신을 잊으면 이 테스트만이 잡는다(outcomes/README.md
        적용 체크리스트 8번)."""
        ledger = json.loads(VERSIONS.read_text(encoding="utf-8"))
        self.assertEqual(KNOWLEDGE_VERSION, ledger["knowledge_version"])
        self.assertEqual(SCORING_VERSION, ledger["scoring_version"])


class TestBoundaryScoreKindContract(unittest.TestCase):
    """`TestUntransferredContractItems.test_boundary_kind_is_in_contract_but_not_in_schema`를
    교체한다(finalplan.md P5). 그 테스트는 백엔드가 성격 메타 컬럼을 갖기 전 "아직 없다"는
    상태를 고정하는 자리였다 — P1(0038/0039가 컬럼+시드 백필)·P2(`suitability_service.
    boundary_score` 분기)로 백엔드가 계약을 구현했으므로 이제 값 대조로 바꾼다.
    """

    def test_backend_kind_constants_match_shipped_scoring(self):
        self.assertEqual(svc.LITERATURE_LIMIT_KIND, _shipped_literature_limit_kind())
        self.assertEqual(svc.ALLOWED_KINDS, _shipped_allowed_kinds())

    def test_backend_kind_constants_match_shared_enum(self):
        """`_shared.json.allowed_kind_enum`(문서 쪽 단일 소스)과 집합이 같은지 — 6개."""
        enum = _shared_allowed_kind_enum()
        self.assertEqual(len(enum), 6)
        self.assertEqual(set(enum), svc.ALLOWED_KINDS)

    def test_boundary_score_matches_contract_for_every_kind(self):
        """6개 kind + None 전부를 백엔드 `boundary_score()`에 태워 계약이 규정한 값과 대조.

        `literature_limit` → 0, 나머지 5개(`cultivable_range`·`literature_threshold`·
        `derived`·`heuristic`·`not_applicable`) → 60, `None` → 60(2026-08-04 사용자 결정).
        """
        shipped_kinds = _shipped_allowed_kinds()
        limit_kind = _shipped_literature_limit_kind()
        self.assertEqual(len(shipped_kinds), 6)
        for kind in shipped_kinds:
            expected = 0.0 if kind == limit_kind else 60.0
            with self.subTest(kind=kind):
                self.assertEqual(svc.boundary_score(kind), expected)
        self.assertEqual(svc.boundary_score(None), 60.0)

    def test_unknown_kind_raises_value_error(self):
        """오타 방어 — 계약과 백엔드 둘 다 모르는 kind에 조용히 60점을 주면 안 된다."""
        with self.assertRaises(ValueError):
            svc.boundary_score("typo_kind")

    def test_literature_limit_targets_match_migration_0039_seed(self):
        """계약이 지목하는 대상(오이 기온 하/상, 상추 spring·fall 기온 하/상, 감자 early·tuber
        기온 상한만 — 총 8건)이 실제 DB 시드(0039)와 일치하는지 대조한다. 🔴 사과 기온 3행은
        이 집합에 없어야 한다 — 있으면 사과 적지등급 0점 지역이 93 → 121로 늘어난다
        (outcomes/README.md §2026-08-04 채점 구조 변경 §1, 실측 기록)."""
        backfill = _load_kind_backfill_migration()
        limit_locations = set()
        for crop_id, indicator, _cultivation_type, amink, amaxk, _method in backfill.SOIL_ROWS:
            if amink == "literature_limit":
                limit_locations.add((crop_id, indicator, "min"))
            if amaxk == "literature_limit":
                limit_locations.add((crop_id, indicator, "max"))
        for crop_id, stage, _cultivation_type, amink, amaxk in backfill.TEMP_ROWS:
            if amink == "literature_limit":
                limit_locations.add((crop_id, stage, "min"))
            if amaxk == "literature_limit":
                limit_locations.add((crop_id, stage, "max"))
        expected = {
            (3, "growing", "min"), (3, "growing", "max"),  # 오이 기온 하한·상한
            (5, "spring", "min"), (5, "spring", "max"),  # 상추 spring 기온 하한·상한
            (5, "fall", "min"), (5, "fall", "max"),  # 상추 fall 기온 하한·상한
            (4, "early", "max"),  # 감자 early 기온 상한
            (4, "tuber", "max"),  # 감자 tuber 기온 상한
        }
        self.assertEqual(limit_locations, expected)
        self.assertEqual(len(limit_locations), 8)
        self.assertEqual(
            {loc for loc in limit_locations if loc[0] == 1}, set(),
            "사과(crop_id=1) 행이 literature_limit을 가지면 안 된다",
        )


class TestCategoryScoreFunctionContract(unittest.TestCase):
    """`TestUntransferredContractItems.test_category_scoring_is_in_contract_but_not_in_schema`를
    교체한다(finalplan.md P5) — P4가 사과·배 `subsoil_texture` 배점표 시드(0041)를 넣었으므로
    이제 값 대조로 바꾼다.

    중복 분리: `tests/test_guide_outcomes_contract.py::TestSubsoilTextureCategoryScoreContract`가
    이미 "마이그레이션 0041 상수 == 계약 JSON"을 키·값 전수로 검증한다(대조 대상이 다르다).
    여기서는 그 비교를 반복하지 않고 "백엔드 `category_score()` 함수가 계약 JSON을 받았을 때
    계약이 말하는 값을 그대로 내는가"만 담당한다 — 두 테스트를 합치면
    `category_score(migration_상수) == 계약`과 `category_score(계약) == 계약`이 이행적으로
    `migration_상수 == 계약`도 함께 보장한다.
    """

    def _code_scores(self, filename: str) -> dict[str, float | None]:
        rules = _crop_rules()[Path(filename).stem]
        return rules["physical_overrides"]["subsoil_texture"]["code_scores"]

    def test_apple_and_pear_every_code_is_scored_by_backend_function(self):
        checked = 0
        for filename in ("apple.json", "pear.json"):
            code_scores = self._code_scores(filename)
            for code, expected in code_scores.items():
                with self.subTest(crop=filename, code=code):
                    got = svc.category_score(int(code), code_scores)
                    if expected is None:
                        self.assertIsNone(got)
                    else:
                        self.assertEqual(got, float(expected))
                checked += 1
        self.assertEqual(checked, 14, "사과·배 7키씩 총 14건을 기대했다")

    def test_apple_and_pear_ranks_are_pinned_and_inverted(self):
        """사과 코드2(사양질)=100/배=75, 사과 코드5(미사식양질)=50/배=100 — 국가 배점표의
        작물별 순위 역전을 값으로 못박는다."""
        apple = self._code_scores("apple.json")
        pear = self._code_scores("pear.json")
        self.assertEqual(svc.category_score(2, apple), 100.0)
        self.assertEqual(svc.category_score(2, pear), 75.0)
        self.assertEqual(svc.category_score(5, apple), 50.0)
        self.assertEqual(svc.category_score(5, pear), 100.0)

    def test_code_99_and_unlisted_code_are_excluded_not_zero(self):
        """`99`(기타)와 표에 없는 코드는 채점 제외(`None`)다 — 0점으로 메우면 판정불가가
        부적합으로 조용히 바뀐다."""
        apple = self._code_scores("apple.json")
        pear = self._code_scores("pear.json")
        for code_scores in (apple, pear):
            self.assertIsNone(svc.category_score(99, code_scores))
            self.assertIsNone(svc.category_score(7, code_scores))  # codebook에도 없는 코드


if __name__ == "__main__":
    unittest.main()
