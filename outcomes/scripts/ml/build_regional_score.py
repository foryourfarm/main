"""RegionalScore.csv 생성 — AnswerData(문헌 기준)와 실제 지역 데이터를 비교한 지역별 점수.

기존 산출물을 확장(재계산 아님):
  - 토양: `data/01_soil_chemistry_modified.csv`(지역 조인 완료, 150/150) x
    `memory/crop_rules/_shared.json`의 soil_rules(공유: pH·유기물·유효인산). 크롭이
    `soil_overrides`를 가지면(예: 감자 유기물, 2026-07-25 도입) 해당 지표만 크롭전용
    밴드로 재계산해 `soil_score_total_{crop_code}` 컬럼을 별도로 만든다 — 나머지 지표는
    공유값 유지. `EXTRA_SOIL_COL`(k/ca/mg, 2026-07-25 상추 도입)처럼 공유 3지표에 아예
    없는 지표도 override로 추가할 수 있다 — 그 지표를 쓰는 크롭의 soil_score_total에만
    포함되고 다른 크롭에는 전혀 영향 없다.
  - 기온: `data/ml/crop_literature_anchor_experiment.csv`(3작물 문헌 앵커 편차 점수, 이미 산출됨).

결측 처리(2026-07-25 개정 — §7 원안의 전역평균을 공간 최근접평균으로 대체):
  1순위: 위경도(`instl_la`/`instl_lo`) 기준 최근접 K개 지역(결측 아닌 곳) 점수 평균.
    공간자기상관(가까운 지역은 토양·기후가 비슷함) 가정 — 전역평균보다 그럴듯한 근사.
    단 결측 지역은 실측값이 없어 실제 오차 개선 여부는 검증 불가([확인 필요]).
  2순위: 최근접 지역도 전부 결측(고립)이면 전역 평균으로 대체.
  3순위: 컬럼 전체가 결측이면 최고점(100)의 정확히 50%를 적용.
  원본 결측 여부는 `*_missing` 컬럼(TRUE/FALSE)으로 항상 보존.

신뢰도 플래그(2026-07-25 결정): pH·유기물·유효인산 결측이 변수별 무작위가 아니라
"토양조사 자체가 없는 동일 24개 지역"에서 항상 동시 발생함(EDA 확인). 개별
`*_missing` 3개만 두면 총점이 대체값 섞인 걸 한눈에 못 봄 — `soil_score_total_missing`
(3개 중 하나라도 결측)과 `total_score_{crop}_missing`(토양 or 해당 작물 기온 결측)을
추가해 총점 신뢰도를 명시한다. 대체 로직 자체(평균/50점)는 바꾸지 않음 — 표시만 강화.

가중치: 문헌 규칙은 토양45/기온30/강수25. 강수 점수는 이 확장에서 산출 안 됨
(원본 실험이 강수 앵커를 산출하지 않음) → 토양·기온만으로 재정규화(0.6/0.4)해서
총점을 낸다. 강수 미포함을 숨기지 않고 명시적으로 표기한다.

이진(binary) 채점 폐기(2026-07-25, 사용자 확인): pH·유기물·유효인산 모두 이제
`allowed_min/max`를 가져 optimal 이탈 시 0으로 뚝 떨어지지 않고 점진 감점된다.
감점 곡선은 2026-07-27 로그로 개정됐다(`scripts/ml/scoring.py`) — 최적 이탈 시 95에서
시작해 허용경계 60, 그 밖은 완충폭 1배에 걸쳐 0까지. 허용경계 밖이 곧바로 0점이던
절벽이 사라졌으므로 이 개정 이후 산출한 점수는 이전 CSV와 직접 비교할 수 없다.
실제 흙토람 공식 완충구간(진단기준표)은 여전히 로컬에 없어
(`scripts/ml/baselines.py`·`docs/ml/experiment_report.md`·`scripts/collect_soil_data.py`
재확인됨, 추측 금지 원칙 유지) — allowed 값은 optimal 폭의 ±50% **명시적
휴리스틱**이다(`memory/crop_rules/_shared.json` source 필드에 근거 기록,
`[확인 필요]`). 실제 완충구간 문헌 확보 시 교체 대상.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scoring import band_score  # 백엔드 룰 엔진과 같은 곡선(scoring.py docstring 참조)

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
CROP_RULES_DIR = ROOT / "memory" / "crop_rules"
RULES = CROP_RULES_DIR / "_shared.json"
OUT = ROOT / "RegionalScore.csv"
MANIFEST = DATA / "ml" / "regional_score_manifest.json"

SOIL_WEIGHT, TEMP_WEIGHT = 45, 30
SOIL_FRAC = SOIL_WEIGHT / (SOIL_WEIGHT + TEMP_WEIGHT)
TEMP_FRAC = TEMP_WEIGHT / (SOIL_WEIGHT + TEMP_WEIGHT)

CROPS = {"09001": "사과", "09011": "배", "07001": "상추", "03001": "감자", "04009": "오이"}
NEIGHBOR_K = 5

SOIL_COL = {"ph": "pH", "organic_matter": "organic_matter", "available_p": "available_p"}
# 공유 3지표 외에 크롭전용 override만 쓸 수 있는 추가 지표(예: 상추 K/Ca/Mg, 2026-07-25 도입).
# 공유 soil_rules에는 없어 이 지표를 override하지 않는 크롭의 soil_score_total에는 포함되지 않는다.
EXTRA_SOIL_COL = {"k": "k", "ca": "ca", "mg": "mg"}


def load_crop_soil_overrides():
    """crop_rules/<crop>.json의 선택적 soil_overrides 필드 → {crop_code: {indicator: rule}}.
    없는 크롭은 공유 soil_rules만 쓴다(기존 동작 유지)."""
    overrides = {}
    for path in sorted(CROP_RULES_DIR.glob("*.json")):
        if path.name == "_shared.json":
            continue
        crop = json.loads(path.read_text(encoding="utf-8"))
        so = crop.get("soil_overrides")
        if so:
            overrides[crop["crop_code"]] = so
    return overrides


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = (np.radians(x) for x in (lat1, lon1, lat2, lon2))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(a))


def impute_score_column(scores, lat, lon, k=NEIGHBOR_K):
    """1순위 최근접 k개 지역 평균, 2순위 전역 평균, 3순위(전부 결측) 50점.
    반환: (대체후 시리즈, 지역별 대체방법 라벨 시리즈, 결측 플래그)."""
    missing = scores.isna()
    filled = scores.copy()
    method = pd.Series("measured", index=scores.index)
    method[missing] = ""

    valid_idx = scores.index[~missing]
    global_mean = scores.mean()

    for idx in scores.index[missing]:
        if len(valid_idx) == 0:
            filled.loc[idx] = 50.0
            method.loc[idx] = "fallback_50"
            continue
        d = pd.Series(
            haversine_km(lat.loc[idx], lon.loc[idx], lat.loc[valid_idx].to_numpy(), lon.loc[valid_idx].to_numpy()),
            index=valid_idx,
        )
        nearest = d.nsmallest(min(k, len(valid_idx))).index
        neighbor_scores = scores.loc[nearest].dropna()
        if not neighbor_scores.empty:
            filled.loc[idx] = round(neighbor_scores.mean(), 2)
            method.loc[idx] = f"neighbor_mean_k{len(neighbor_scores)}"
        elif pd.notna(global_mean):
            filled.loc[idx] = round(global_mean, 2)
            method.loc[idx] = "global_mean"
        else:
            filled.loc[idx] = 50.0
            method.loc[idx] = "fallback_50"
    return filled, method, missing


def build_soil(regions, crop_soil_overrides):
    soil = pd.read_csv(DATA / "01_soil_chemistry_modified.csv", dtype={"region_code": str})
    soil = soil[["region_code", "pH", "organic_matter", "available_p", "k", "ca", "mg"]].drop_duplicates("region_code")
    rules = json.loads(RULES.read_text(encoding="utf-8"))["soil_rules"]

    df = regions.merge(soil, on="region_code", how="left")
    fill_log = {}
    for var, col in SOIL_COL.items():
        raw_score = df[col].apply(lambda v: band_score(v, rules[var]))
        filled, method, missing = impute_score_column(raw_score, df["instl_la"], df["instl_lo"])
        df[f"{var}_score"] = filled.round(1)
        df[f"{var}_missing"] = missing
        fill_log[f"{var}_score"] = {
            "missing_count": int(missing.sum()),
            "method_counts": method[missing].value_counts().to_dict(),
        }
    df["soil_score_total"] = df[["ph_score", "organic_matter_score", "available_p_score"]].mean(axis=1).round(1)
    df["soil_score_total_missing"] = df["ph_missing"] | df["organic_matter_missing"] | df["available_p_missing"]

    # 크롭전용 soil override: 공유 3지표는 override된 지표만 재계산(나머지는 공유값 유지),
    # 공유에 없는 추가 지표(EXTRA_SOIL_COL, 예: 상추 K/Ca/Mg)는 override한 크롭에만 더해진다.
    # 원본값 결측 여부는 규칙(rule)과 무관하므로 공유 지표는 기존 {var}_missing을 재사용한다.
    for crop_code, override_rules in crop_soil_overrides.items():
        indicator_scores = []
        missing_flags = []
        for var, col in SOIL_COL.items():
            if var in override_rules:
                raw_score = df[col].apply(lambda v: band_score(v, override_rules[var]))
                filled, method, missing = impute_score_column(raw_score, df["instl_la"], df["instl_lo"])
                score_col = f"{var}_score_{crop_code}"
                df[score_col] = filled.round(1)
                fill_log[score_col] = {
                    "missing_count": int(missing.sum()),
                    "method_counts": method[missing].value_counts().to_dict(),
                }
                indicator_scores.append(score_col)
                missing_flags.append(missing)
            else:
                indicator_scores.append(f"{var}_score")
                missing_flags.append(df[f"{var}_missing"])
        for var, rule in override_rules.items():
            if var in SOIL_COL:
                continue
            col = EXTRA_SOIL_COL[var]
            raw_score = df[col].apply(lambda v: band_score(v, rule))
            filled, method, missing = impute_score_column(raw_score, df["instl_la"], df["instl_lo"])
            score_col = f"{var}_score_{crop_code}"
            df[score_col] = filled.round(1)
            fill_log[score_col] = {
                "missing_count": int(missing.sum()),
                "method_counts": method[missing].value_counts().to_dict(),
            }
            indicator_scores.append(score_col)
            missing_flags.append(missing)
        df[f"soil_score_total_{crop_code}"] = df[indicator_scores].mean(axis=1).round(1)
        df[f"soil_score_total_{crop_code}_missing"] = pd.concat(missing_flags, axis=1).any(axis=1)
    return df, fill_log


def build_temp(df):
    anchor = pd.read_csv(DATA / "ml" / "crop_literature_anchor_experiment.csv", dtype={"region_code": str})
    fill_log = {}
    for crop_code, name in CROPS.items():
        col = f"score_{crop_code}_temp"
        raw = anchor.set_index("region_code")[col].reindex(df["region_code"]).reset_index(drop=True)
        filled, method, missing = impute_score_column(raw, df["instl_la"], df["instl_lo"])
        df[f"temp_{crop_code}_{name}_score"] = filled.round(1)
        df[f"temp_{crop_code}_{name}_missing"] = missing
        fill_log[f"temp_{crop_code}_{name}_score"] = {
            "missing_count": int(missing.sum()),
            "method_counts": method[missing].value_counts().to_dict(),
        }
        # 크롭전용 soil override가 있으면 그 총점(soil_score_total_{crop_code})을 쓰고, 없으면 공유 총점 사용.
        soil_col = f"soil_score_total_{crop_code}" if f"soil_score_total_{crop_code}" in df.columns else "soil_score_total"
        soil_missing_col = f"{soil_col}_missing"
        df[f"total_score_{crop_code}_{name}"] = (
            df[soil_col] * SOIL_FRAC + df[f"temp_{crop_code}_{name}_score"] * TEMP_FRAC
        ).round(1)
        df[f"total_score_{crop_code}_{name}_missing"] = (
            df[soil_missing_col] | df[f"temp_{crop_code}_{name}_missing"]
        )
    return df, fill_log


def add_percentile_columns(df):
    """크롭별 총점의 크롭내 상대순위(0~100, percentile rank).

    절대 total_score_{crop}는 그대로 둔다 — 크롭마다 문헌 기준의 엄격도가 달라
    절대값 자체가 이미 진짜 차이(예: 상추 RDA 토양기준이 감자보다 훨씬 좁음)이고
    이를 지우면 안 된다(CLAUDE.md §2 근거 없는 가중치 조정 금지, §1 정직성).
    percentile 컬럼은 "이 크롭 안에서 이 지역이 몇 등급인가"만 나타내는 표시용
    보조지표다 — 크롭간 절대 비교(예: 감자 상위20% == 상추 상위20%가 같은 수준의
    적합도)를 의미하지 않는다. 2026-07-25 사용자 확인."""
    for crop_code, name in CROPS.items():
        col = f"total_score_{crop_code}_{name}"
        df[f"{col}_percentile"] = (df[col].rank(pct=True) * 100).round(1)
    return df


def main():
    regions = pd.read_csv(DATA / "raw" / "selected_regions_modified.csv", dtype={"region_code": str})
    regions = regions[["region_code", "region_name", "instl_la", "instl_lo"]].drop_duplicates("region_code")

    crop_soil_overrides = load_crop_soil_overrides()
    df, soil_fill_log = build_soil(regions, crop_soil_overrides)
    df, temp_fill_log = build_temp(df)
    df = add_percentile_columns(df)

    score_cols = [c for c in df.columns if "_score" in c and not c.startswith("total_")]
    assert df[score_cols].apply(lambda s: s.between(0, 100)).all().all(), "점수 0-100 범위 위반"
    for crop_code, name in CROPS.items():
        assert df[f"total_score_{crop_code}_{name}"].between(0, 100).all(), f"{name} 총점 범위 위반"
        assert df[f"total_score_{crop_code}_{name}_percentile"].between(0, 100).all(), f"{name} percentile 범위 위반"
    for crop_code in crop_soil_overrides:
        assert f"soil_score_total_{crop_code}" in df.columns, f"{crop_code} soil override 총점 컬럼 누락"
    assert df["region_code"].is_unique, "지역 중복"

    df.to_csv(OUT, index=False, encoding="utf-8")

    manifest = {
        "knowledge_version": json.loads(RULES.read_text(encoding="utf-8"))["knowledge_version"],
        "weight_note": "강수(25) 점수 미산출 — 토양45/기온30만 재정규화(0.6/0.4)해 총점 계산. 강수 제외를 숨기지 않음.",
        "percentile_note": "total_score_{crop}_percentile(2026-07-25 도입)은 크롭 내부 상대순위(0~100)일 뿐, "
                            "크롭간 절대 비교가 아니다. 크롭마다 문헌 기준의 엄격도가 실제로 다르므로(예: 상추 RDA "
                            "토양기준이 감자보다 훨씬 좁음, 전국 pH 중앙값 5.91이 상추 optimal 6.5~7.0과 구조적으로 "
                            "어긋남) total_score_{crop} 절대값 자체는 그대로 둔다 — 가중치를 임의로 조정해 크롭간 "
                            "점수를 맞추지 않는다(CLAUDE.md §2·§8).",
        "imputation_rule": f"1순위: 최근접 {NEIGHBOR_K}개 지역(위경도 기준) 평균 대체. "
                            "2순위: 최근접도 전부 결측이면 전역 평균. 3순위: 컬럼 전체 결측이면 최고점 50%(=50.0).",
        "reliability_flag_rule": "soil_score_total_missing = ph/유기물/유효인산 중 하나라도 결측. "
                                  "total_score_{crop}_missing = 토양 결측 or 해당 작물 기온 결측. "
                                  "대체값 자체는 그대로 쓰되(총점 계산엔 포함), 신뢰도만 별도 표시.",
        "fill_log": {**soil_fill_log, **temp_fill_log},
        "soil_score_total_missing_count": int(df["soil_score_total_missing"].sum()),
        "crop_soil_overrides": {code: list(rules.keys()) for code, rules in crop_soil_overrides.items()} or "없음",
        "regions": len(df),
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{OUT.name}: {len(df)} regions")
    for col, v in manifest["fill_log"].items():
        print(f"  {col}: 결측 {v['missing_count']}건, 방법={v['method_counts']}")


if __name__ == "__main__":
    main()
