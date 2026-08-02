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


def month_label(months):
    """연속 구간이면 `04-10`, 비연속(예: 상추 봄·가을 작기)이면 개별 월을 나열한다.
    `months[0]-months[-1]`만 쓰면 [4,5,9,10]이 '04-10'으로 보여 6~8월도 채점한 것처럼 읽힌다."""
    if months == list(range(months[0], months[-1] + 1)):
        return f"{months[0]:02d}-{months[-1]:02d}"
    return ".".join(f"{m:02d}" for m in months)


SOIL_UNITS = {"ph": "-", "organic_matter": "g/kg", "available_p": "mg/kg"}


def main():
    shared = json.loads(SHARED_RULES.read_text(encoding="utf-8"))
    crops = load_crops()
    rows = []

    for var, rule in shared["soil_rules"].items():
        rows.append(band_row(var, rule, SOIL_UNITS.get(var, "-"), rule["source"], "soil"))

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
                rule, SOIL_UNITS.get(var, "-"), f"memory/crop_rules/{crop_code} ({name} 작물전용 override, {shared['knowledge_version']})",
                f"crop:{crop_code}:{name}:soil_override",
            ))

    df = pd.DataFrame(rows)
    assert df["variable"].is_unique, "AnswerData 변수명 중복"
    assert not df.empty, "AnswerData 비어있음"
    # 측정법 미기재 밴드가 조용히 섞이지 않게 강제한다 — unknown이어도 "확인 결과 미상"임을 적어야 한다.
    assert df["method"].notna().all() and (df["method"].str.strip() != "").all(), "method 비어있는 밴드 존재"

    df.to_csv(OUT, index=False, encoding="utf-8")
    print(f"{OUT.name}: {len(df)} rows (soil={len(shared['soil_rules'])}, "
          f"crops={len(crops)}, knowledge_version={shared['knowledge_version']})")


if __name__ == "__main__":
    main()
