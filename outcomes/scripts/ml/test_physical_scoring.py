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

from scoring import band_score  # noqa: E402


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


if __name__ == "__main__":
    for _name, _fn in sorted(list(globals().items())):
        if _name.startswith("test_"):
            _fn()
            print(f"  OK {_name}")
    print("ALL PHYSICAL SCORING TESTS PASSED.")
