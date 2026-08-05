"""백엔드 생육지침이 `outcomes/`(ML 이관 계약)와 같은 값인지 검증.

**왜 필요한가**: 같은 밭 점수를 두 곳에서 계산한다 — `outcomes/scripts/ml/`(FarmML 이관본)과
백엔드 룰 엔진(`crop_growth_guide`)이다. 두 구현의 밴드가 갈리면 **같은 밭에 다른 점수**가
나오는데, 그건 배포해도 예외가 안 나고 화면에도 안 뜬다. `outcomes/README.md`가 "두 구현의
점수가 갈리면 안 되는 계약"이라고 명시했지만 **그걸 강제하는 장치가 없었다.**

실제로 갈렸던 적이 있다: FarmML PR #3이 사과·배 토양 밴드를 RDA 교본값으로 바꿨는데
(유효인산 300~550 → 200~300) 백엔드는 종전 값을 그대로 들고 있었다. 마이그레이션 0023이
맞췄고, 이 테스트가 다시 갈리는 것을 막는다.

DB가 필요 없다 — 마이그레이션의 상수 표와 `outcomes/` JSON을 직접 대조한다. 마이그레이션이
실제로 그 값을 적재하는지는 별개 문제이고(그건 `alembic upgrade`가 보장한다), 여기서 잡으려는
것은 **두 정의가 어긋나는 것**이다.
"""

import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CROP_RULES = ROOT / "outcomes" / "memory" / "crop_rules"
DISPERSION = ROOT / "outcomes" / "memory" / "indicator_dispersion.json"
SCORING = ROOT / "outcomes" / "scripts" / "ml" / "scoring.py"
VERSIONS = ROOT / "backend" / "alembic" / "versions"
MIGRATION = VERSIONS / "0023_rda_handbook_soil_bands.py"
MIGRATION_CATIONS = VERSIONS / "0024_soil_cations_k_ca_mg.py"
MIGRATION_EC = VERSIONS / "0028_soil_ec_guide_bands.py"
MIGRATION_LETTUCE_ORGANIC = VERSIONS / "0029_lettuce_organic_matter_guide.py"
MIGRATION_APPLE_CA = VERSIONS / "0030_apple_ca_one_sided_band.py"
MIGRATION_CUCUMBER_POTATO = VERSIONS / "0031_cucumber_potato_soil_bands.py"
# 2026-08-04 FarmML 동기화(사과 k·ca, 감자 ph·organic). **가장 마지막에 겹쳐 읽어야 한다** —
# 위 마이그레이션들이 심은 값을 UPDATE로 덮는 것이라 순서가 뒤바뀌면 낡은 값이 이긴다.
MIGRATION_BAND_SYNC = VERSIONS / "0035_farmml_20260804_band_sync.py"
# P1 성격 메타 컬럼 백필 (0038이 컬럼만 만들고, 0039가 이 값을 채운다).
MIGRATION_KIND_BACKFILL = VERSIONS / "0039_guide_boundary_kind_backfill.py"

# `outcomes/` 지표명 → 백엔드 `crop_growth_guide.indicator`.
# 이름이 다른 것은 역사적 이유다(백엔드 시드가 먼저 만들어졌다) — 매핑을 한 곳에 고정한다.
INDICATOR_ALIAS = {
    "ph": "ph",
    "organic_matter": "organic",
    "available_p": "p2o5",
    "k": "k",
    "ca": "ca",
    "mg": "mg",
    "ec": "ec",
}

# outcomes 작물 파일 → 백엔드 crop_id (0003 시드 기준: 1 사과 / 2 배 / 3 오이 / 4 감자 / 5 상추)
# 상추는 `0019`(ph·p2o5)와 `0024`(k·ca·mg)가 나눠 적재한다.
#
# **오이·감자는 2026-08-03까지 이 목록에서 빠져 있었다.** 그래서 계약 테스트가 3작물만
# 검증했고, FarmML이 8/3에 두 작물 토양 밴드를 7개로 보강한 것을 **아무도 못 잡았다**
# (오이·감자 각 5개 누락 + 오이 ph 값 낡음). nexttodo가 "outcomes soil_overrides 전 지표가
# 백엔드와 같은 값"이라고 적은 것은 실제로는 사과·배·상추에만 해당하는 말이었다.
# 5작물 전부를 넣어 사각지대를 없앤다 — 새 작물이 생기면 여기에 반드시 추가할 것.
CROP_ID = {
    "apple.json": 1,
    "pear.json": 2,
    "cucumber.json": 3,
    "potato.json": 4,
    "lettuce.json": 5,
}

# 마이그레이션이 나뉘어 있어(컬럼 유무로 갈렸다) 밴드 정의도 두 파일에 흩어져 있다.
# 계약 검증은 "어느 파일에 있든 outcomes와 같은가"만 보므로 합쳐서 읽는다.
_EXTRA_BACKEND_BANDS = {
    # 0019가 적재한 상추 ph·p2o5 — 그 마이그레이션은 표 형태가 아니라 INSERT 문이라
    # 상수를 import할 수 없다. 값을 여기 옮겨 적되 outcomes와 대조되므로 갈리면 실패한다.
    (5, "ph"): (6.5, 7.0, 6.25, 7.25),
    (5, "p2o5"): (250.0, 400.0, 175.0, 475.0),
    # 0027이 backfill한 감자 organic — 같은 이유로(값이 SQL 문에 직접 박혀 있다) 여기 적는다.
    (4, "organic"): (30.0, 47.0, 10.0, 55.5),
}

BAND_KEYS = ("optimal_min", "optimal_max", "allowed_min", "allowed_max")


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_migration():
    return _load_module("m0023", MIGRATION)


class TestSoilBandContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.migration = _load_migration()
        cations = _load_module("m0024", MIGRATION_CATIONS)
        # (crop_id, indicator) → 밴드 4개. 0024는 뒤에 weight·source가 더 붙어 있어 4개만 취한다.
        cls.backend = {
            (crop_id, indicator): tuple(bands)
            for crop_id, indicator, *bands in cls.migration._BANDS
        }
        cls.backend.update(
            {(row[0], row[1]): tuple(row[2:6]) for row in cations._BANDS}
        )
        # 0028은 EC 하나만 다뤄서 행에 indicator 컬럼이 없다 — 키를 여기서 붙인다.
        ec = _load_module("m0028", MIGRATION_EC)
        cls.backend.update({(row[0], "ec"): tuple(row[1:5]) for row in ec._BANDS})
        # 0029도 (crop=5, organic) 단일 행이라 상수를 그대로 튜플로 조립한다.
        lettuce_organic = _load_module("m0029", MIGRATION_LETTUCE_ORGANIC)
        cls.backend[(5, "organic")] = (
            lettuce_organic._OPTIMAL_MIN,
            lettuce_organic._OPTIMAL_MAX,
            lettuce_organic._ALLOWED_MIN,
            lettuce_organic._ALLOWED_MAX,
        )
        # 0031은 오이·감자 신규 10건(_BANDS, 0024와 같은 8칸 표) + 오이 ph UPDATE 1건.
        # ph는 INSERT가 아니라 UPDATE라 표에 없으니 상수를 따로 붙인다.
        cp = _load_module("m0031", MIGRATION_CUCUMBER_POTATO)
        cls.backend.update({(row[0], row[1]): tuple(row[2:6]) for row in cp._BANDS})
        cls.backend[(3, "ph")] = cp._CUCUMBER_PH_NEW
        cls.backend.update(_EXTRA_BACKEND_BANDS)
        # 0030은 (1, "ca")의 optimal_max·allowed_max만 UPDATE로 NULL로 바꾼다(단측 밴드,
        # 사과 치환성 Ca "5~6cmol/kg 이상"). UPDATE라 상수 import가 안 되니 0024가 심어 둔
        # 최소값은 그대로 두고 최대값 두 칸만 여기서 덮는다(존재는 test_migration_files_exist가 확인).
        apple_ca_min, _, apple_ca_allowed_min, _ = cls.backend[(1, "ca")]
        cls.backend[(1, "ca")] = (apple_ca_min, None, apple_ca_allowed_min, None)
        # 0035는 위 전부를 UPDATE로 덮는 마지막 층이다(사과 k·ca, 감자 ph·organic).
        # 반드시 0030의 단측 밴드 처리 뒤에 와야 한다 — 사과 ca 상한을 다시 세우기 때문이다.
        sync = _load_module("m0035", MIGRATION_BAND_SYNC)
        cls.backend.update({(row[0], row[1]): tuple(row[2:6]) for row in sync._BANDS})

    def test_migration_files_exist(self):
        # 파일명이 바뀌면 위 로드가 조용히 실패해 검증이 공허해진다.
        for path in (
            MIGRATION,
            MIGRATION_CATIONS,
            MIGRATION_EC,
            MIGRATION_LETTUCE_ORGANIC,
            MIGRATION_APPLE_CA,
            MIGRATION_CUCUMBER_POTATO,
            MIGRATION_BAND_SYNC,
        ):
            with self.subTest(path=path.name):
                self.assertTrue(path.is_file(), f"{path} 가 없다")

    def test_apple_and_pear_bands_match_outcomes(self):
        for filename, crop_id in CROP_ID.items():
            rules = json.loads((CROP_RULES / filename).read_text(encoding="utf-8"))
            overrides = rules.get("soil_overrides", {})
            self.assertTrue(overrides, f"{filename}에 soil_overrides가 없다")
            for outcome_name, backend_name in INDICATOR_ALIAS.items():
                band = overrides.get(outcome_name)
                if band is None:
                    continue  # 그 작물이 재정의하지 않은 지표는 공유 밴드를 쓴다
                got = self.backend.get((crop_id, backend_name))
                with self.subTest(crop=filename, indicator=backend_name):
                    # 단측 밴드(2026-08-03): outcomes가 optimal_max 등을 null로 열어
                    # "그 방향엔 감점 없음"을 표현할 수 있다(band_score() 계약). null 여부
                    # 자체가 아니라 백엔드와 null 위치가 같은지가 계약이라 None을 그대로
                    # 비교한다 — 한쪽만 null이면 assertEqual이 잡는다.
                    expected = tuple(
                        None if band[k] is None else float(band[k]) for k in BAND_KEYS
                    )
                    self.assertIsNotNone(
                        got,
                        f"{filename} {outcome_name}이 outcomes에는 있는데 마이그레이션에 없다 "
                        "— 두 구현의 점수가 갈린다",
                    )
                    self.assertEqual(
                        got,
                        expected,
                        f"{filename} {outcome_name}: outcomes {expected} vs 백엔드 {got}",
                    )

    def test_unmirrored_indicators_are_known_and_deliberate(self):
        """새로운 토양 지표가 조용히 늘어나는 것을 잡는다.

        K·Ca·Mg는 `0024`로 반영됐으므로 미반영 목록이 비었다. outcomes에 모르는 지표가 생기면
        여기서 드러나 "백엔드에 넣을지" 판단을 강제한다 — 조용히 갈리는 것을 막는 게 목적이다.
        """
        known_unmirrored: set[str] = set()
        for filename in CROP_ID:
            rules = json.loads((CROP_RULES / filename).read_text(encoding="utf-8"))
            for name in rules.get("soil_overrides", {}):
                with self.subTest(crop=filename, indicator=name):
                    self.assertIn(
                        name,
                        set(INDICATOR_ALIAS) | known_unmirrored,
                        f"{filename}에 새 토양 지표 '{name}'이 생겼다 — 백엔드 반영 여부를 "
                        "판단하고 이 테스트의 목록을 갱신할 것",
                    )


class TestRiskWidthContract(unittest.TestCase):
    def test_temp_day_risk_width_matches_dispersion(self):
        """감쇠폭은 산포도 재산출마다 바뀐다 — 백엔드가 낡은 값을 들고 있으면 곡선이 갈린다."""
        migration = _load_migration()
        dispersion = json.loads(DISPERSION.read_text(encoding="utf-8"))
        expected = float(dispersion["backend_indicator_risk_width"]["temp_day"])
        self.assertEqual(migration._TEMP_DAY_RISK_WIDTH_NEW, expected)

    def test_other_risk_widths_still_match_0020(self):
        """0023은 temp_day만 바꾼다 — 나머지가 달라졌으면 0020도 갱신해야 한다는 신호다."""
        spec = importlib.util.spec_from_file_location(
            "m0020", ROOT / "backend" / "alembic" / "versions" / "0020_indicator_risk_width.py"
        )
        m0020 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m0020)
        dispersion = json.loads(DISPERSION.read_text(encoding="utf-8"))["backend_indicator_risk_width"]
        for indicator, seeded in m0020.RISK_WIDTH.items():
            if indicator == "temp_day":
                continue  # 0023이 덮어쓴다
            with self.subTest(indicator=indicator):
                self.assertEqual(
                    float(seeded),
                    float(dispersion[indicator]),
                    f"'{indicator}' 감쇠폭이 outcomes와 다르다 — 0020 이후 산포도가 재산출됐다",
                )


def _shipped_allowed_kinds() -> frozenset[str]:
    """`outcomes/scripts/ml/scoring.py`의 `ALLOWED_KINDS`를 텍스트로 파싱한다.

    그 모듈을 직접 import하지 않는 이유는 `test_farmml_contract.py`와 같다 — pandas·numpy를
    요구하는데 백엔드 `requirements.txt`에는 둘 다 없다(§14 불필요한 의존성 금지)."""
    text = SCORING.read_text(encoding="utf-8")
    match = re.search(r"ALLOWED_KINDS\s*=\s*frozenset\(\{(.*?)\}\)", text, re.DOTALL)
    assert match, "scoring.py에서 ALLOWED_KINDS를 못 찾았다 — 이름이 바뀌었을 수 있다"
    return frozenset(re.findall(r'"([a-z_]+)"', match.group(1)))


def _load_kind_backfill():
    return _load_module("m0039", MIGRATION_KIND_BACKFILL)


# 백엔드 기온 지침 행의 실제 allowed_min/allowed_max. (crop_id, growth_stage) → (min, max),
# None은 그 방향에 값이 없다는 뜻(예: 감자 tuber allowed_min). 값 출처:
#   (1,*)      0021(fruit_growth min·maturity·coloring)+0012(fruit_growth max)
#   (2,growing) 0004(그대로 유지, 0015는 생육기 day_of_year만 바꿨다)
#   (3,growing) 0019(오이 온도 갱신 UPDATE)
#   (4,early)   0012(min=-3)+0004(max=27) / (4,tuber) 0004(min NULL, max=27)
#   (5,spring/fall) 0019(온도 갱신)+0025(fall은 spring을 그대로 복제)
# 이 상수는 "같은 방향+같은 값" 규칙이 0039의 TEMP_ROWS에 실제로 지켜졌는지 검증하는 용도라
# 0039 자체에는 없다(0039는 kind만 갖고 원본 allowed 값은 여러 과거 마이그레이션에 흩어져
# 있어 이 파일에서 다시 손으로 옮겨 적는다 — 위 각주가 그 근거다).
# 백엔드 기온 행의 허용경계. **여기서 다시 적지 않고 `0039`에서 읽는다** — 손으로 옮겨
# 적으면 미래에 어떤 마이그레이션이 기온 밴드를 바꿀 때 이 상수만 옛 값에 남아, "밴드가
# 성격 아래에서 움직였다"는 바로 이 테스트가 잡아야 할 드리프트를 놓친다. `0039`의 표는
# upgrade가 실행 시점에 실제 DB 행과 대조하는 값이라 같은 사실의 단일 소스다.
BACKEND_TEMP_ALLOWED: dict[tuple[int, str], tuple[float | None, float | None]] = {
    key: (None if lo is None else float(lo), None if hi is None else float(hi))
    for key, (lo, hi) in _load_module(
        "m0039_bounds", MIGRATION_KIND_BACKFILL
    ).EXPECTED_TEMP_BOUNDS.items()
}


class TestBoundaryKindBackfillContract(unittest.TestCase):
    """0039가 채운 성격 메타 컬럼(cultivation_type/allowed_min_kind/allowed_max_kind/method)이
    계약과 일치하는지, 그리고 "같은 방향+같은 값" 규칙이 실제로 지켜졌는지 검증한다."""

    @classmethod
    def setUpClass(cls):
        cls.backfill = _load_kind_backfill()
        cls.rules = {
            filename: json.loads((CROP_RULES / filename).read_text(encoding="utf-8"))
            for filename in CROP_ID
        }
        cls.crop_filename = {crop_id: filename for filename, crop_id in CROP_ID.items()}

    def test_migration_files_exist(self):
        for path in (
            VERSIONS / "0038_guide_boundary_kind_columns.py",
            MIGRATION_KIND_BACKFILL,
        ):
            with self.subTest(path=path.name):
                self.assertTrue(path.is_file(), f"{path} 가 없다")

    def test_soil_rows_match_outcomes_contract(self):
        """0039.SOIL_ROWS의 4컬럼이 outcomes soil_overrides와 같은지 — 지표명은 INDICATOR_ALIAS로."""
        alias_by_backend = {backend: outcome for outcome, backend in INDICATOR_ALIAS.items()}
        checked = 0
        for crop_id, indicator, cultivation_type, amink, amaxk, method in self.backfill.SOIL_ROWS:
            filename = self.crop_filename[crop_id]
            rules = self.rules[filename]
            outcome_name = alias_by_backend[indicator]
            band = rules["soil_overrides"][outcome_name]
            with self.subTest(crop=filename, indicator=indicator):
                self.assertEqual(cultivation_type, band["cultivation_type"])
                self.assertEqual(amink, band.get("allowed_min_kind"))
                self.assertEqual(amaxk, band.get("allowed_max_kind"))
                self.assertEqual(method, band["method"])
            checked += 1
        self.assertEqual(checked, 33, f"토양 지표 33행을 기대했는데 {checked}행이다")

    def test_temp_rows_kind_only_set_when_value_matches_contract(self):
        """기온 행은 백엔드 allowed_min/max가 계약 allowed_min/max와 같은 방향에서 같은 값일
        때만 그 방향의 kind를 갖는다 — 값이 다르면(구조가 달라 흔하다) NULL이어야 한다."""
        checked = 0
        for crop_id, stage, cultivation_type, amink, amaxk in self.backfill.TEMP_ROWS:
            filename = self.crop_filename[crop_id]
            band = self.rules[filename]["temperature_guides"][0]
            backend_min, backend_max = BACKEND_TEMP_ALLOWED[(crop_id, stage)]
            expected_min_kind = (
                band["allowed_min_kind"]
                if backend_min is not None and float(backend_min) == float(band["allowed_min"])
                else None
            )
            expected_max_kind = (
                band["allowed_max_kind"]
                if backend_max is not None and float(backend_max) == float(band["allowed_max"])
                else None
            )
            with self.subTest(crop=filename, stage=stage):
                self.assertEqual(
                    amink, expected_min_kind,
                    f"{filename}.{stage} allowed_min_kind: 백엔드 {amink} vs 기대 {expected_min_kind} "
                    f"(백엔드 allowed_min={backend_min}, 계약 allowed_min={band['allowed_min']})",
                )
                self.assertEqual(
                    amaxk, expected_max_kind,
                    f"{filename}.{stage} allowed_max_kind: 백엔드 {amaxk} vs 기대 {expected_max_kind} "
                    f"(백엔드 allowed_max={backend_max}, 계약 allowed_max={band['allowed_max']})",
                )
                # 계약 기온 밴드는 5작물 전부 open_field다 — 값 대조 없이 지표 대응만으로 옮긴다.
                self.assertEqual(cultivation_type, band["cultivation_type"])
            checked += 1
        self.assertEqual(checked, 9, f"기온 지표 9행을 기대했는데 {checked}행이다")

    def test_apple_temp_allowed_min_kind_is_never_literature_limit(self):
        """사과 기온 3행의 allowed_min_kind가 literature_limit이면 안 된다 — 이게 뒤집히면
        구조가 다른 밴드(생육단계별 세분 vs 계약 단일 4~10월 밴드)의 값을 섞어 쓴 것이고,
        사과 0점 지역이 93→121로 늘어난다(계약 문서에 실측으로 기록됨)."""
        apple_rows = [row for row in self.backfill.TEMP_ROWS if row[0] == 1]
        self.assertEqual(len(apple_rows), 3, "사과 기온 행이 3개가 아니다")
        for crop_id, stage, _ct, amink, amaxk in apple_rows:
            with self.subTest(stage=stage):
                self.assertNotEqual(amink, "literature_limit")
                # 검증용 검산: 지금 시점엔 min·max 모두 NULL이어야 한다(계약 allowed
                # 13.5~33.0과 세 행 전부 값이 달라 어느 방향도 매칭이 안 된다).
                self.assertIsNone(amink)
                self.assertIsNone(amaxk)

    def test_allowed_kind_values_are_within_scoring_allowed_kinds(self):
        """오타 방어 — outcomes/scripts/ml/scoring.py가 모르는 kind에 ValueError를 낸다."""
        shipped = _shipped_allowed_kinds()
        self.assertGreaterEqual(len(shipped), 6, "ALLOWED_KINDS 파싱 결과가 비정상적으로 적다")
        seen = set()
        for _crop, _ind_or_stage, _ct, amink, amaxk, *_rest in (
            [(c, i, ct, amink, amaxk, m) for c, i, ct, amink, amaxk, m in self.backfill.SOIL_ROWS]
            + [(c, s, ct, amink, amaxk, None) for c, s, ct, amink, amaxk in self.backfill.TEMP_ROWS]
        ):
            seen.add(amink)
            seen.add(amaxk)
        seen.discard(None)
        self.assertTrue(seen, "kind 값이 하나도 없다 — 백필이 비었는지 확인")
        for kind in seen:
            with self.subTest(kind=kind):
                self.assertIn(kind, shipped)


MIGRATION_SUBSOIL_TEXTURE = VERSIONS / "0041_apple_pear_subsoil_texture_guides.py"

# outcomes/data/99_codebook_modified.csv의 subsoil_texture 코드북(등급코드→이름). 여기서 다시
# 손으로 옮겨 적지 않고 CSV를 직접 읽어 대조한다 — 코드북이 바뀌면 이 테스트도 따라 실패해야
# 한다(주석에만 적어두면 드리프트를 못 잡는다).
CODEBOOK = ROOT / "outcomes" / "data" / "99_codebook_modified.csv"


def _load_subsoil_texture_labels() -> dict[str, str]:
    """CSV에서 code_type=subsoil_texture 행만 code(선행 0 제거)→label로 뽑는다."""
    import csv

    labels: dict[str, str] = {}
    with CODEBOOK.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["code_type"] == "subsoil_texture":
                labels[str(int(row["code"]))] = row["label"]
    return labels


def _load_subsoil_texture_migration():
    return _load_module("m0041", MIGRATION_SUBSOIL_TEXTURE)


class TestSubsoilTextureCategoryScoreContract(unittest.TestCase):
    """0041의 code_scores 상수 표가 계약(outcomes/memory/crop_rules/{apple,pear}.json)과
    키·값 전수 일치하는지, 그리고 category_score()가 그 표를 계약과 같게 조회하는지 검증한다
    (finalplan.md P4 완료조건 — 사과·배 순위가 정반대인 것을 값으로 못박는다)."""

    @classmethod
    def setUpClass(cls):
        cls.migration = _load_subsoil_texture_migration()
        cls.rules = {
            filename: json.loads((CROP_RULES / filename).read_text(encoding="utf-8"))
            for filename in ("apple.json", "pear.json")
        }
        cls.labels = _load_subsoil_texture_labels()
        from app.services.suitability_service import category_score

        cls.category_score = staticmethod(category_score)

    def test_migration_file_exists(self):
        self.assertTrue(MIGRATION_SUBSOIL_TEXTURE.is_file(), f"{MIGRATION_SUBSOIL_TEXTURE} 가 없다")

    def test_codebook_confirms_texture_labels(self):
        """코드북에서 실제로 02=사양질, 05=미사식양질임을 읽어 확인한다(주석이 아니라 값)."""
        self.assertEqual(self.labels["2"], "사양질")
        self.assertEqual(self.labels["5"], "미사식양질")

    def test_apple_code_scores_match_outcomes_exactly(self):
        contract = self.rules["apple.json"]["physical_overrides"]["subsoil_texture"]["code_scores"]
        self.assertEqual(contract.keys(), self.migration._APPLE_CODE_SCORES.keys())
        for key, expected in contract.items():
            with self.subTest(code=key):
                self.assertEqual(self.migration._APPLE_CODE_SCORES[key], expected)

    def test_pear_code_scores_match_outcomes_exactly(self):
        contract = self.rules["pear.json"]["physical_overrides"]["subsoil_texture"]["code_scores"]
        self.assertEqual(contract.keys(), self.migration._PEAR_CODE_SCORES.keys())
        for key, expected in contract.items():
            with self.subTest(code=key):
                self.assertEqual(self.migration._PEAR_CODE_SCORES[key], expected)

    def test_apple_and_pear_rank_sandy_loam_and_silty_clay_loam_oppositely(self):
        """코드북 02=사양질, 05=미사식양질(위 테스트로 확인) 기준 — 사과 사양질=100/배
        사양질=75, 사과 미사식양질=50/배 미사식양질=100. 뒤집히면 실패해야 한다."""
        self.assertEqual(self.labels["2"], "사양질")
        self.assertEqual(self.labels["5"], "미사식양질")
        self.assertEqual(self.category_score(2, self.migration._APPLE_CODE_SCORES), 100.0)
        self.assertEqual(self.category_score(2, self.migration._PEAR_CODE_SCORES), 75.0)
        self.assertEqual(self.category_score(5, self.migration._APPLE_CODE_SCORES), 50.0)
        self.assertEqual(self.category_score(5, self.migration._PEAR_CODE_SCORES), 100.0)

    def test_code_99_is_excluded_not_zero(self):
        """기타(99)는 채점 제외(None)여야 한다 — 0점으로 메우면 안 된다."""
        self.assertIsNone(self.category_score(99, self.migration._APPLE_CODE_SCORES))
        self.assertIsNone(self.category_score(99, self.migration._PEAR_CODE_SCORES))

    def test_unknown_code_is_none(self):
        """표에 없는 코드(예: 7 — codebook에도 없다)는 결측이지 0점이 아니다."""
        self.assertIsNone(self.category_score(7, self.migration._APPLE_CODE_SCORES))
        self.assertIsNone(self.category_score(7, self.migration._PEAR_CODE_SCORES))


if __name__ == "__main__":
    unittest.main()
