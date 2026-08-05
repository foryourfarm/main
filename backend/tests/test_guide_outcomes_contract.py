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
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CROP_RULES = ROOT / "outcomes" / "memory" / "crop_rules"
DISPERSION = ROOT / "outcomes" / "memory" / "indicator_dispersion.json"
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


if __name__ == "__main__":
    unittest.main()
