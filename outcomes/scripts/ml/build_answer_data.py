"""AnswerData.csv 생성 — 문헌 기반 이상적 기준값을 ML 지도학습 라벨 정의로 확정.

출처: `memory/crop_rules/`(작물별 승인 문헌 기준 파일 + `_shared.json`, 이미 출처 명시됨).
새 값을 추측하지 않는다 — crop_rules에 없는 항목은 만들지 않는다.

경계(2026-07-25 결정, CLAUDE.md §9 개정): 이 표는 향후 지도학습의 타깃(pseudo-label)
정의로 쓰인다. 라벨을 "정의"하는 것과 그 라벨로 학습한 모델의 정확도를 "주장"하는 것은
별개다 — 실제 GO/NO-GO는 여전히 §8 기준선 비교·게이트 통과 여부로만 판단한다.
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CROP_RULES_DIR = ROOT / "memory" / "crop_rules"
SHARED_RULES = CROP_RULES_DIR / "_shared.json"
OUT = ROOT / "AnswerData.csv"


def load_crops():
    """crop_rules/_shared.json을 제외한 나머지 파일 = 크롭별 규칙, crop_code를 키로."""
    crops = {}
    for path in sorted(CROP_RULES_DIR.glob("*.json")):
        if path.name == "_shared.json":
            continue
        crop = json.loads(path.read_text(encoding="utf-8"))
        crops[crop["crop_code"]] = crop
    return crops


def band_row(variable, rule, unit, source, scope):
    lo, hi = rule.get("optimal_min"), rule.get("optimal_max")
    mid = None if lo is None or hi is None else round((lo + hi) / 2, 3)
    return {
        "variable": variable,
        "ideal_value": mid,
        "ideal_min": lo,
        "ideal_max": hi,
        "unit": unit,
        # 단위가 같아도 측정 프로토콜이 다르면 값이 통째로 어긋난다(유효인산 약 6배, EC 5배).
        # crop_rules가 인용하는 출처 중 추출법을 명시한 것이 없어 현재는 전부 unknown이다 —
        # 빈칸으로 두면 "확인했는데 해당 없음"과 구분이 안 되므로 명시적으로 싣는다.
        "method": rule.get("method", "unknown [확인 필요] — method 필드 미기재"),
        "source": source,
        "scope": scope,
    }


# 단위는 컬럼에 고정한다(CLAUDE.md §4). k/ca/mg는 치환성 양이온으로 cmol/kg —
# 종전엔 매핑이 없어 상추 override 3행이 "-"로 나갔다(2026-08-02 정정).
def month_label(months):
    """연속 구간이면 `04-10`, 비연속(예: 상추 봄·가을 작기)이면 개별 월을 나열한다.
    `months[0]-months[-1]`만 쓰면 [4,5,9,10]이 '04-10'으로 보여 6~8월도 채점한 것처럼 읽힌다."""
    if months == list(range(months[0], months[-1] + 1)):
        return f"{months[0]:02d}-{months[-1]:02d}"
    return ".".join(f"{m:02d}" for m in months)


SOIL_UNITS = {"ph": "-", "organic_matter": "g/kg", "available_p": "mg/kg",
              "k": "cmol/kg", "ca": "cmol/kg", "mg": "cmol/kg", "ec": "dS/m"}
# 물리성(2026-08-03). 등급코드가 아니라 등급 상한 %로 환산한 값의 밴드다(_shared physical_code_maps).
PHYSICAL_UNITS = {"slope_pct": "%", "gravel_pct": "%",
                  # 범주형은 %로 환산하지 않는다 — 등급코드 자체가 배점표의 키다.
                  "subsoil_texture": "등급코드"}


def category_row(variable, rule, unit, source, scope):
    """범주형 배점표 행(2026-08-03). 밴드 컬럼(ideal_*)은 전부 null로 둔다.

    최고배점 등급코드를 ideal_min/max에 채우고 싶은 유혹이 있으나 그러면 안 된다 — 소비자가
    그 두 값을 연속 밴드로 읽고 band 곡선에 태우면 중간 등급(예: 사과 식양질 75점)이 곡선
    감점으로 잘못 계산된다. 값이 없음을 명시적으로 null로 노출하는 편이 조용히 틀린 숫자를
    주는 것보다 정직하다(CLAUDE.md §6 `available=False` 표기 원칙과 같은 성격).
    배점표 실물은 method에 직렬화해 싣는다.
    """
    table = ", ".join(
        f"{code}={'미채점' if score is None else f'{score:g}점'}"
        for code, score in rule["code_scores"].items()
    )
    return {
        "variable": variable,
        "ideal_value": None,
        "ideal_min": None,
        "ideal_max": None,
        "unit": unit,
        "method": f"범주형 배점표(밴드 아님) — 등급코드→점수: {table}. "
                  f"{rule.get('method', 'unknown [확인 필요] — method 필드 미기재')}",
        "source": source,
        "scope": scope,
    }


def main():
    shared = json.loads(SHARED_RULES.read_text(encoding="utf-8"))
    crops = load_crops()
    rows = []

    # 2026-08-03: 작물 무관 공유 soil_rules 블록이 사라졌다(출처 미확인으로 삭제). 라벨 정의도
    # 전부 작물별 문헌 밴드에서만 나온다 — 어느 문헌 기준인지 말할 수 없는 행을 싣지 않는다.
    if "soil_rules" in shared:
        raise ValueError("_shared.json에 soil_rules가 되살아났다 — 공유 밴드는 2026-08-03에 삭제됐다")

    for crop_code, crop in crops.items():
        name = crop["name"]
        for g in crop.get("temperature_guides", []):
            months = month_label(g["months"])
            rows.append(band_row(
                f"temperature_{crop_code}_{months}",
                g, "C", f"memory/crop_rules/{crop_code} ({name} 문헌 시드, {shared['knowledge_version']})",
                f"crop:{crop_code}:{name}:months={months}",
            ))
        for g in crop.get("precipitation_guides", []):
            if g.get("refuted"):
                continue
            months = month_label(g["months"])
            rows.append(band_row(
                f"precipitation_{crop_code}_{months}",
                g, "mm/week", f"memory/crop_rules/{crop_code} ({name} 문헌 시드, {shared['knowledge_version']})",
                f"crop:{crop_code}:{name}:months={months}",
            ))
        for var, rule in crop.get("soil_overrides", {}).items():
            rows.append(band_row(
                f"soil_{var}_{crop_code}",
                rule, SOIL_UNITS.get(var, "-"), f"memory/crop_rules/{crop_code} ({name} 작물전용 밴드, {shared['knowledge_version']})",
                f"crop:{crop_code}:{name}:soil",
            ))
        for var, rule in crop.get("physical_overrides", {}).items():
            # 범주형(배점표)과 연속형(밴드)은 행 형태가 다르다 — 섞어 내면 소비자가 등급코드를
            # 연속 밴드로 오독한다(category_row docstring).
            row = category_row if "code_scores" in rule else band_row
            kind = "물리성 배점표" if "code_scores" in rule else "물리성 밴드"
            rows.append(row(
                f"physical_{var}_{crop_code}",
                rule, PHYSICAL_UNITS.get(var, "-"), f"memory/crop_rules/{crop_code} ({name} {kind}, {shared['knowledge_version']})",
                f"crop:{crop_code}:{name}:physical",
            ))

    df = pd.DataFrame(rows)
    # 무결성 검증은 raise로 둔다 — assert는 `python -O`에서 통째로 사라져 검증 없이 CSV가 써진다.
    if not df["variable"].is_unique:
        raise ValueError("AnswerData 변수명 중복")
    if df.empty:
        raise ValueError("AnswerData 비어있음")
    # 측정법 미기재 밴드가 조용히 섞이지 않게 강제한다 — unknown이어도 "확인 결과 미상"임을 적어야 한다.
    if not (df["method"].notna().all() and (df["method"].str.strip() != "").all()):
        raise ValueError("method 비어있는 밴드 존재")

    df.to_csv(OUT, index=False, encoding="utf-8")
    print(f"{OUT.name}: {len(df)} rows (crops={len(crops)}, "
          f"knowledge_version={shared['knowledge_version']})")
    print(f"  scope별: {df['scope'].str.rsplit(':', n=1).str[-1].value_counts().to_dict()}")


if __name__ == "__main__":
    main()
