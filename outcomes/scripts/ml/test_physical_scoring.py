"""2026-08-03 신규 채점축(물리성·EC) 회귀검사.

검사 대상 5가지 — 전부 조용히 틀릴 수 있는 지점이다.
  1. 등급코드 -> 대표 %(등급 상한) 환산이 codebook과 어긋나지 않는가.
  2. 그 대표값을 문헌 밴드에 태웠을 때 등급별 판정이 문헌과 같은가
     (예: 자갈 35% 이상 등급은 감자에서 감점, 15~35%는 만점).
  3. 경사 기준이 사과만 0-15%라는 문헌 차이가 실제 점수 차이로 나타나는가.
  4. EC 밴드가 문헌이 주는 3작물에만 있고, 시군구 폴백 커버리지(103/150)가 유지되는가
     — 폴백이 사라지면 종전의 16/150으로 조용히 되돌아간다.
  5. 공유 soil_rules 삭제 이후 필수 지표 밴드가 없는 작물이 조용히 폴백하지 않고 실패하는가.

실행: python scripts/ml/test_physical_scoring.py
"""
import json
import sys
from pathlib import Path

import pandas as pd

SCRIPTS_ML = Path(__file__).resolve().parent
if str(SCRIPTS_ML) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ML))

ROOT = SCRIPTS_ML.parents[1]
CROP_RULES_DIR = ROOT / "memory" / "crop_rules"

from scoring import band_score, category_score  # noqa: E402


def _shared():
    return json.loads((CROP_RULES_DIR / "_shared.json").read_text(encoding="utf-8"))


def _crop(name):
    return json.loads((CROP_RULES_DIR / f"{name}.json").read_text(encoding="utf-8"))


def test_code_maps_match_codebook():
    """등급 상한 환산표가 codebook의 등급 집합과 일치하고 99(기타)는 채우지 않는다."""
    maps = _shared()["physical_code_maps"]
    codebook = pd.read_csv(ROOT / "data" / "99_codebook_modified.csv")

    expected = {
        # codebook: slope 1=0-2%, 2=2-7%, 3=7-15%, 4=15-30%, 5=30-60%, 6=60-100%
        "slope_pct": {1: 2.0, 2: 7.0, 3: 15.0, 4: 30.0, 5: 60.0, 6: 100.0},
        # codebook: 자갈 1=0-15%, 2=15-35%, 3=35% 이상.
        # 최상위 등급은 상한이 열려 있어 물리적 최대 100%로 둔다(_shared physical_code_maps 주석).
        "gravel_pct": {1: 15.0, 2: 35.0, 3: 100.0},
    }
    for indicator, want in expected.items():
        got = {int(k): v for k, v in maps[indicator].items()}
        assert got.pop(99) is None, f"{indicator}: 99(기타)는 null이어야 한다(추측 금지)"
        assert got == want, f"{indicator} 환산표 불일치: {got} != {want}"

    for code_type, indicator in (("slope", "slope_pct"), ("subsoil_gravel", "gravel_pct")):
        codes = set(codebook.loc[codebook["code_type"] == code_type, "code"].astype(int))
        mapped = {int(k) for k in maps[indicator]}
        assert codes == mapped, f"{indicator}: codebook 코드 {codes}와 매핑 {mapped}가 다르다"


def test_gravel_band_matches_literature():
    """감자 자갈 0-35%(RDA 처방 5차). 등급 1·2는 만점, 35% 초과 등급은 0점."""
    rule = _crop("potato")["physical_overrides"]["gravel_pct"]
    assert band_score(15.0, rule) == 100.0, "자갈 0-15% 등급이 만점이 아니다"
    assert band_score(35.0, rule) == 100.0, "자갈 15-35% 등급이 만점이 아니다(문헌 상한이 35%)"
    assert band_score(100.0, rule) == 0.0, "자갈 35% 이상 등급이 감점되지 않는다"


def test_slope_band_differs_by_crop():
    """경사 기준이 사과만 0-15%, 나머지는 0-7%라는 문헌 차이가 점수에 실제로 나타난다."""
    apple = _crop("apple")["physical_overrides"]["slope_pct"]
    pear = _crop("pear")["physical_overrides"]["slope_pct"]
    assert band_score(15.0, apple) == 100.0, "사과 경사 0-15% 기준이 반영되지 않았다"
    assert band_score(15.0, pear) < 100.0, "배 경사 0-7% 기준이 반영되지 않았다"
    assert band_score(2.0, apple) == band_score(2.0, pear) == 100.0, "평탄지는 두 작물 모두 만점"


def test_ec_band_and_coverage():
    """EC(2026-08-03): 문헌이 주는 3작물만 채점하고, 시군구 폴백 커버리지가 유지된다."""
    have_ec = {name for name in ("cucumber", "potato", "lettuce", "apple", "pear")
               if "ec" in _crop(name)["soil_overrides"]}
    # 처방 5차 화학성 표에서 사과·배 EC 칸은 '–'(값 없음)라 밴드를 만들지 않는다.
    assert have_ec == {"cucumber", "potato", "lettuce"}, f"EC 밴드 작물 집합이 다르다: {have_ec}"

    lettuce_ec = _crop("lettuce")["soil_overrides"]["ec"]
    assert lettuce_ec["optimal_max"] == 2.0
    # 상추 allowed 상한만 휴리스틱이 아니라 실측값(노안성 2004, 수량 20% 감소 2.9 dS/m)이다.
    assert lettuce_ec["allowed_max"] == 2.9
    assert band_score(0.5, lettuce_ec) == 100.0, "전국 대부분인 저EC가 만점이 아니다"
    assert band_score(2.5, lettuce_ec) < 100.0, "기준 초과 EC가 감점되지 않는다"

    ec = pd.read_csv(ROOT / "data" / "ml" / "soil_ec_by_region.csv")
    measured = ec["ec_median"].notna().sum()
    # 종전 16/150은 읍면동 완전일치만 찾은 결과였다 — 폴백이 사라지면 여기서 잡힌다.
    assert measured >= 100, f"EC 실측 커버리지 급감({measured}/150) — 시군구 폴백 확인"


def test_subsoil_texture_table_matches_literature():
    """심교문(2016) 국가 과수 적지 배점표를 그대로 옮겼는가 — 사과·배가 정반대여야 한다.

    문헌(knowledge-base/papers/common/rda-fruit-suitability-integration-shim-2016.md):
      사과 20점 사양질·미사사양질 / 15점 식양질 / 10점 미사식양질·식질 / 5점 사질·역질·사력질
      배   20점 식양질·미사식양질 / 15점 사양질·미사사양질 / 10점 식질 / 5점 사질·역질·사력질
    배점 20/15/10/5는 항목 만점 20으로 나눠 100/75/50/25로 싣는다.
    """
    apple = _crop("apple")["physical_overrides"]["subsoil_texture"]
    pear = _crop("pear")["physical_overrides"]["subsoil_texture"]
    # codebook: 1=사질 2=사양질 3=미사사양질 4=식양질 5=미사식양질 6=식질
    assert apple["code_scores"] == {"1": 25.0, "2": 100.0, "3": 100.0, "4": 75.0,
                                    "5": 50.0, "6": 50.0, "99": None}, "사과 배점표가 문헌과 다르다"
    assert pear["code_scores"] == {"1": 25.0, "2": 75.0, "3": 75.0, "4": 100.0,
                                   "5": 100.0, "6": 50.0, "99": None}, "배 배점표가 문헌과 다르다"

    # 🔴 순위 역전이 실제 점수로 나타나야 한다 — 공통 규칙으로 되돌아가면 여기서 잡힌다.
    assert category_score(2, apple) == 100.0 and category_score(2, pear) == 75.0, \
        "사양질에서 사과·배 점수가 갈리지 않는다"
    assert category_score(5, apple) == 50.0 and category_score(5, pear) == 100.0, \
        "미사식양질에서 사과·배 점수가 갈리지 않는다"

    # 등급 이름이 codebook과 어긋나면 배점표 매핑 자체가 무의미해진다.
    codebook = pd.read_csv(ROOT / "data" / "99_codebook_modified.csv")
    texture = codebook[codebook["code_type"] == "subsoil_texture"]
    names = dict(zip(texture["code"].astype(int), texture["label"]))
    assert names[2] == "사양질" and names[3] == "미사사양질", f"codebook 등급 이름 변경: {names}"
    assert names[4] == "식양질" and names[5] == "미사식양질", f"codebook 등급 이름 변경: {names}"
    assert set(names) == {int(c) for c in apple["code_scores"]}, \
        f"codebook 코드 집합 {set(names)}과 배점표 키가 다르다"


def test_category_score_never_invents_values():
    """범주형은 표에 없는 코드·결측을 0점이 아니라 NaN으로 둔다(판정불가 != 부적합)."""
    apple = _crop("apple")["physical_overrides"]["subsoil_texture"]
    assert pd.isna(category_score(99, apple)), "99(기타)가 점수를 받았다 — 추측 금지 위반"
    assert pd.isna(category_score(None, apple)), "결측이 점수를 받았다"
    assert pd.isna(category_score(7, apple)), "표에 없는 코드가 점수를 받았다"
    # 밴드 지표와 경로가 섞이면 안 된다 — 배점표 규칙엔 optimal_min이 아예 없다.
    assert "optimal_min" not in apple, "범주형 규칙에 밴드 필드가 섞였다"


def test_texture_scored_only_where_literature_gives_a_table():
    """배점표가 있는 사과·배만 채점한다. 감자·오이·상추는 순서 추정 없이 점수를 만들 수 없다."""
    have = {name for name in ("apple", "pear", "potato", "cucumber", "lettuce")
            if "subsoil_texture" in _crop(name).get("physical_overrides", {})}
    assert have == {"apple", "pear"}, f"토성 채점 작물 집합이 다르다: {have}"

    maps = _shared()["physical_code_maps"]
    # 범주형은 %/순위 환산표를 갖지 않는다 — 가지면 누군가 단조 순위를 되살린 것이다.
    assert "subsoil_texture" in maps["category_source_column"], "범주형 source 컬럼 등록 누락"
    assert "subsoil_texture" not in maps["source_column"], \
        "토성이 연속형 경로에 등록됐다 — %/순위 환산은 사과·배 중 한쪽을 반드시 틀리게 한다"
    assert "subsoil_texture" not in maps, "토성 코드→% 환산표가 생겼다(순위 가정 부활)"


def test_no_shared_soil_band_fallback():
    """공유 soil_rules는 삭제됐고, 필수 지표가 없는 작물은 즉시 실패한다."""
    shared = _shared()
    assert "soil_rules" not in shared, "출처 미확인 공유 밴드가 되살아났다"
    required = shared["required_soil_indicators"]

    from build_regional_score import load_crop_overrides

    soil, physical = load_crop_overrides()
    assert len(soil) == 5, f"5작물 전부 작물별 토양 밴드를 가져야 한다(현재 {len(soil)})"
    for code, rules in soil.items():
        missing = [ind for ind in required if ind not in rules]
        assert not missing, f"{code}: 필수 지표 {missing} 누락"
    assert physical, "물리성 밴드를 가진 작물이 하나도 없다"

    # 필수 지표를 뺀 임시 규칙 파일에서 실패해야 한다 — 조용한 폴백이 되살아나면 여기서 잡힌다.
    probe = CROP_RULES_DIR / "_probe_missing_band.json"
    probe.write_text(
        json.dumps({"crop_code": "99999", "name": "검사용", "temperature_guides": [],
                    "precipitation_guides": [], "soil_overrides": {}}, ensure_ascii=False),
        encoding="utf-8",
    )
    try:
        load_crop_overrides()
    except ValueError:
        pass
    else:
        raise AssertionError("필수 지표 없는 작물에서 실패하지 않았다 — 조용한 폴백이 남아 있다")
    finally:
        probe.unlink()


def test_apple_ca_is_two_sided_with_derived_upper():
    """사과 치환성 Ca는 양측 밴드이고 상한 성격이 `derived`다(2026-08-04 사용자 결정).

    이 밴드는 2026-08-02에 단측(상한 null)으로 갔다가 이번에 되돌아왔다. 두 번 뒤집힌
    필드라 조용히 다시 null이 되면 아무도 모른다 — 전국 중앙값 7.23이 상한 6.5 밖이어서
    상한 유무가 사과 총점 평균을 68.6 ↔ 74.9로 흔든다.

    상한 6.5는 문헌값이 아니라 우리 역산치(염기포화도 80% × CEC 10)라 `derived`여야 한다.
    `heuristic`으로 적으면 ±50% 기계 산출과 구분이 사라지고, 문헌 kind로 적으면 없는
    문헌을 있는 척하게 된다.
    """
    ca = _crop("apple")["soil_overrides"]["ca"]
    assert (ca["optimal_min"], ca["optimal_max"]) == (5.0, 6.0), f"사과 ca optimal 변경됨: {ca}"
    assert (ca["allowed_min"], ca["allowed_max"]) == (4.5, 6.5), f"사과 ca allowed 변경됨: {ca}"
    assert ca["allowed_max_kind"] == "derived", (
        f"상한 6.5는 우리 역산치다. kind가 {ca['allowed_max_kind']!r}면 출처 성격이 사라진다"
    )
    # 상한 초과 구간의 감점 기울기에는 근거가 없다(FinalReport §3-1: 국내외 0건).
    # 그 사실이 source에서 사라지면 「문헌 기반 점수」로 오표기될 수 있다.
    assert "기준 초과" in ca["source"], "상한 초과 구간을 「기준 초과」로만 표기하라는 단서가 사라졌다"


def test_potato_ph_stays_open_field():
    """감자 pH는 노지 밴드를 쓴다(2026-08-04 사용자 결정, decision.md §1-1 우선).

    답변 파일이 §1-1(노지)과 §2-4 ⓐ(시설 5.5~6.2)로 갈렸고 사용자가 노지를 택했다.
    5작물 중 재배형이 지표별로 갈리는 유일한 작물이라(감자 pH·온도만 노지, 나머지 화학성은
    시설) 일괄 치환에 휩쓸리기 쉽다.
    """
    ph = _crop("potato")["soil_overrides"]["ph"]
    assert (ph["optimal_min"], ph["optimal_max"]) == (5.5, 7.0), f"감자 pH 밴드 변경됨: {ph}"
    assert ph["cultivation_type"] == "open_field", f"감자 pH가 노지 기준이 아니다: {ph['cultivation_type']!r}"


if __name__ == "__main__":
    for _name, _fn in sorted(list(globals().items())):
        if _name.startswith("test_"):
            _fn()
            print(f"  OK {_name}")
    print("ALL PHYSICAL SCORING TESTS PASSED.")
