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

결측·이상치 처리(2026-07-29 개정 — 점수공간 최근접 단순평균을 원시피처 KNN으로 교체):
  대체는 `scripts/ml/imputation.py`가 담당한다. 핵심 변경 3가지.
  1. **점수 공간 → 원시값 공간**. band_score가 비선형(로그 감쇠)이라
     mean(score) != score(mean) — 종전엔 이 왜곡이 대체값에 그대로 들어갔다. 이제
     pH·유기물·유효인산·K·Ca·Mg와 작물 앵커월 평균기온을 원시값으로 채운 뒤 채점한다.
  2. **거리역수 가중 + CV로 k 선택**. k=5 고정·단순평균을 버리고 홀드아웃 20%로
     k∈{1,3,5,7,10,15}를 고른다. 종전 방식(neighbor_mean_k5)·전역평균과의 MAE 비교를
     `data/ml/imputation_validation.json`에 남긴다 — 종전 docstring의 "개선 여부 검증
     불가 [확인 필요]"를 실측으로 대체한 산출물이다.
  3. **다변량 예측인자**. 예측인자 = 공간(위경도→km 평면) + 기후 4피처 + 나머지 원시변수.
     K·Ca·Mg 결측 47개 중 23개는 pH·유기물·유효인산을 보유하므로 그 상관이 실제로 쓰인다.
  이상치: 이웃 대비 KNN 잔차가 크면(modified z>3.5) 결측 처리해 재대체한다. 판정된
  원본값은 `data/ml/imputation_outliers.csv`에 보존한다 — 지우지 않는다.
  폴백은 유지: KNN 불가 → 컬럼 평균 → (그래도 결측이면) 점수 50.0.
  원본 결측 여부는 `*_missing` 컬럼(TRUE/FALSE)으로 항상 보존하고, 대체 방법·빌린
  지역·거리는 `{변수}_impute_method` / `{변수}_impute_source` 컬럼으로 노출한다(§18-4).
  한계: 결측 지역엔 실측이 없어 그 지역의 대체 오차는 여전히 직접 검증 불가([확인 필요]).

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
import sys
from pathlib import Path

import pandas as pd

SCRIPTS_ML = Path(__file__).resolve().parent
if str(SCRIPTS_ML) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ML))

from dispersion import soil_rule, temp_rule
from imputation import impute, latlon_to_km
from scoring import band_score  # 백엔드 룰 엔진과 같은 곡선(scoring.py docstring 참조)

# 앵커월 평균기온 산출은 실험 스크립트와 **같은 함수**를 써야 한다 — 복제하면 두 산출물의
# 기온 정의가 조용히 갈라진다. `_anchor_month_temp`는 밑줄 이름이지만 이 목적상 의도적 재사용.
from crop_literature_anchor_experiment import (  # noqa: E402
    CROP_ANCHORS,
    _anchor_month_temp,
    climate_features,
    load_regions_weather,
)

ROOT = Path(__file__).resolve().parents[2]
# 원본 산출물 이관 시 `outcomes/data/`는 함께 오지 않았다(git 미추적). 동일 파일명 데이터가
# 레포 루트 `/data`에 있어 거기를 가리킨다 — outcomes/ 안에 데이터를 중복 복사하지 않는다.
DATA = ROOT / "data"
CROP_RULES_DIR = ROOT / "memory" / "crop_rules"
RULES = CROP_RULES_DIR / "_shared.json"
OUT = ROOT / "RegionalScore.csv"
MANIFEST = DATA / "ml" / "regional_score_manifest.json"
VALIDATION = DATA / "ml" / "imputation_validation.json"
OUTLIERS = DATA / "ml" / "imputation_outliers.csv"

# 가중치는 승인 파라미터에서 읽는다 — 종전엔 45/30을 하드코딩하고 강수 25를 암묵 재정규화해서
# 표기 가중치(45/30/25)와 실효 가중치(0.6/0.4)가 달랐다. 2026-08-01 재설계로 강수를 0으로
# 명시하고 60/40을 승인값으로 올렸다(실효값은 그대로라 점수는 바뀌지 않는다).
_WEIGHTS = json.loads(RULES.read_text(encoding="utf-8"))["weights"]
SOIL_WEIGHT, TEMP_WEIGHT = _WEIGHTS["soil"], _WEIGHTS["temperature"]
assert _WEIGHTS["precipitation"] == 0, (
    "강수 가중치가 0이 아니다 — 강수 점수를 실제로 산출하도록 이 스크립트를 고치기 전에는 "
    "0이 아닌 값을 두면 표기와 실효 가중치가 다시 갈린다."
)
SOIL_FRAC = SOIL_WEIGHT / (SOIL_WEIGHT + TEMP_WEIGHT)
TEMP_FRAC = TEMP_WEIGHT / (SOIL_WEIGHT + TEMP_WEIGHT)

CROPS = {"09001": "사과", "09011": "배", "07001": "상추", "03001": "감자", "04009": "오이"}

# 대체 대상 원시 변수. 토양 6종 + 작물별 앵커월 평균기온 5종을 **한 번에** 대체한다 —
# 따로 돌리면 서로를 예측인자로 쓸 수 없고, 이미 대체된 값이 다음 대체에 섞여 들어간다.
SOIL_VALUE_COLS = ["pH", "organic_matter", "available_p", "k", "ca", "mg"]
CLIMATE_COLS = ["annual_mean_temp", "growing_temp", "temp_seasonality", "annual_precip"]
UNFILLED_SCORE = 50.0  # 원시값이 끝까지 결측인 경우의 최종 폴백(최고점의 50%)

# 이웃 대비 이상치로 판정된 값을 KNN으로 **치환**할지. 탐지·플래그는 항상 한다.
#
# [확인 필요] 2026-07-29 1차 실행에서 판정된 20건을 전수 확인한 결과 전부 물리적으로 실재
# 가능한 극단값이었다: 태백시·홍천군·봉화군 명호면(고지대 저온 — 예측인자에 고도가 없어
# 잔차가 큰 것이지 데이터 오류가 아니다), 유효인산 1288·1261mg/kg(시설재배 인산 과다 축적),
# Ca 14.4cmol/kg(석회 과용), 제주 유기물 43g/kg(화산토). 이 값들을 이웃값으로 치환하면
# 제품이 경고해야 할 진짜 신호를 지운다(CLAUDE.md §1 정확성 우선, §18-4).
# 그래서 기본은 치환하지 않고 플래그만 남긴다 — `{변수}_outlier` 컬럼으로 노출된다.
# 데이터 오류(센서 고장·단위 혼입)가 실제로 확인되면 True로 바꾼다.
REPLACE_KNN_OUTLIERS = False

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


def temp_raw_col(crop_code: str) -> str:
    return f"temp_raw_{crop_code}"


def load_raw_features(regions):
    """지역별 원시 변수(토양 6 + 작물 앵커월 평균기온 5)와 KNN 예측인자 기본 피처.

    반환: (원시값 프레임, 예측인자 base 프레임, 대체 대상 컬럼 목록).
    base = 위경도 등거리 평면(x_km,y_km) + 기후 4피처. 기후 피처는 기상 관측이 없는
    14개 지역에서 결측이지만 nan-aware 거리라 남은 피처로 거리가 계산된다.
    """
    soil = pd.read_csv(DATA / "01_soil_chemistry_modified.csv", dtype={"region_code": str})
    soil = soil[["region_code", *SOIL_VALUE_COLS]].drop_duplicates("region_code")

    regions_full, weather = load_regions_weather()
    climate = climate_features(regions_full, weather)[["region_code", *CLIMATE_COLS]]

    frame = regions.merge(soil, on="region_code", how="left").merge(
        climate, on="region_code", how="left"
    )
    targets = list(SOIL_VALUE_COLS)
    for crop_code in CROPS:
        rule = CROP_ANCHORS[crop_code]["temp"]
        col = temp_raw_col(crop_code)
        if rule is None:  # 앵커 없는 작물은 기온 채점 자체가 없다 — 대체 대상도 아님
            frame[col] = pd.NA
            continue
        frame[col] = frame["region_code"].map(_anchor_month_temp(weather, rule["months"]))
        targets.append(col)

    base = pd.concat(
        [latlon_to_km(frame["instl_la"], frame["instl_lo"]), frame[CLIMATE_COLS]], axis=1
    )
    return frame, base, targets


def score_column(values, rule):
    """원시값 → 점수. 대체 실패로 값이 끝까지 결측이면 최종 폴백 50점(종전 3순위와 동일)."""
    return values.apply(lambda v: band_score(v, rule)).fillna(UNFILLED_SCORE)


def build_soil(df, raw_missing, crop_soil_overrides):
    """대체 완료된 원시 토양값으로 채점한다. 대체 자체는 main에서 한 번에 끝난 상태다."""
    rules = json.loads(RULES.read_text(encoding="utf-8"))["soil_rules"]

    for var, col in SOIL_COL.items():
        df[f"{var}_score"] = score_column(df[col], soil_rule(rules[var], var)).round(1)
        df[f"{var}_missing"] = raw_missing[col]
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
                score_col = f"{var}_score_{crop_code}"
                df[score_col] = score_column(
                    df[col], soil_rule(override_rules[var], var)
                ).round(1)
                indicator_scores.append(score_col)
            else:
                indicator_scores.append(f"{var}_score")
            # 원본 결측 여부는 채점 규칙과 무관하므로 override 여부와 상관없이 원시값 기준.
            missing_flags.append(raw_missing[col])
        for var, rule in override_rules.items():
            if var in SOIL_COL:
                continue
            col = EXTRA_SOIL_COL[var]
            score_col = f"{var}_score_{crop_code}"
            df[score_col] = score_column(df[col], soil_rule(rule, var)).round(1)
            indicator_scores.append(score_col)
            missing_flags.append(raw_missing[col])
        df[f"soil_score_total_{crop_code}"] = df[indicator_scores].mean(axis=1).round(1)
        df[f"soil_score_total_{crop_code}_missing"] = pd.concat(missing_flags, axis=1).any(axis=1)
    return df


def build_temp(df, raw_missing):
    """대체 완료된 앵커월 평균기온으로 채점 + 작물별 총점 조립.

    종전엔 실험 CSV의 **점수**를 읽어 점수공간에서 대체했다. 이제 원시 기온을 대체한 뒤
    같은 곡선으로 채점한다 — 원래 관측이 있던 지역의 점수는 실험 CSV와 일치해야 하므로
    아래에서 교차검증한다. 두 산출물의 기온 정의가 갈라지면 즉시 실패한다.
    """
    anchor = pd.read_csv(
        DATA / "ml" / "crop_literature_anchor_experiment.csv", dtype={"region_code": str}
    ).set_index("region_code")
    for crop_code, name in CROPS.items():
        col = temp_raw_col(crop_code)
        score = score_column(
            df[col], temp_rule(CROP_ANCHORS[crop_code]["temp"], crop_code)
        ).round(1)
        df[f"temp_{crop_code}_{name}_score"] = score
        df[f"temp_{crop_code}_{name}_missing"] = raw_missing[col]

        # 대체·이상치치환이 없었던 행만 비교한다(치환된 행은 당연히 달라진다).
        reference = df["region_code"].map(anchor[f"score_{crop_code}_temp"])
        observed = (df[f"{col}__impute_method"] == "measured") & reference.notna()
        if observed.any():
            drift = float((score[observed] - reference[observed]).abs().max())
            assert drift <= 0.1, f"{name} 기온 점수가 실험 CSV와 불일치(최대 {drift})"

        # 크롭전용 soil override가 있으면 그 총점(soil_score_total_{crop_code})을 쓰고, 없으면 공유 총점 사용.
        soil_col = f"soil_score_total_{crop_code}" if f"soil_score_total_{crop_code}" in df.columns else "soil_score_total"
        soil_missing_col = f"{soil_col}_missing"
        df[f"total_score_{crop_code}_{name}"] = (
            df[soil_col] * SOIL_FRAC + df[f"temp_{crop_code}_{name}_score"] * TEMP_FRAC
        ).round(1)
        df[f"total_score_{crop_code}_{name}_missing"] = (
            df[soil_missing_col] | df[f"temp_{crop_code}_{name}_missing"]
        )
    return df


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

    # 원시값 대체를 **한 번에** 끝낸 뒤 채점한다(모듈 docstring 결측·이상치 처리 참조).
    frame, base, targets = load_raw_features(regions)
    raw_missing = frame[targets].isna()
    df, impute_report = impute(
        frame,
        targets,
        base,
        labels=frame["region_name"],
        replace_outliers=REPLACE_KNN_OUTLIERS,
    )

    df = build_soil(df, raw_missing, crop_soil_overrides)
    df = build_temp(df, raw_missing)
    df = add_percentile_columns(df)
    # 대체 출처 컬럼은 사람이 읽는 이름으로 노출한다(§18-4 근사 표기 의무).
    df = df.rename(
        columns=lambda c: c.replace("__impute_", "_impute_").replace("__outlier", "_outlier")
    )

    score_cols = [c for c in df.columns if "_score" in c and not c.startswith("total_")]
    assert df[score_cols].apply(lambda s: s.between(0, 100)).all().all(), "점수 0-100 범위 위반"
    for crop_code, name in CROPS.items():
        assert df[f"total_score_{crop_code}_{name}"].between(0, 100).all(), f"{name} 총점 범위 위반"
        assert df[f"total_score_{crop_code}_{name}_percentile"].between(0, 100).all(), f"{name} percentile 범위 위반"
    for crop_code in crop_soil_overrides:
        assert f"soil_score_total_{crop_code}" in df.columns, f"{crop_code} soil override 총점 컬럼 누락"
    assert df["region_code"].is_unique, "지역 중복"

    df.to_csv(OUT, index=False, encoding="utf-8")

    shared = json.loads(RULES.read_text(encoding="utf-8"))
    manifest = {
        "knowledge_version": shared["knowledge_version"],
        # 문헌 밴드값과 채점 곡선은 따로 움직인다 — 곡선만 바뀌어도 숫자가 전부 달라지므로
        # 소비자(ForYourFarm)가 knowledge_version만 보고 "변화 없음"으로 오독하지 않게 분리 노출.
        "scoring_version": shared["scoring_version"],
        "weights": _WEIGHTS,
        "weight_note": "2026-08-01 가중치 재설계(사용자 확인): 토양60/기온40/강수0. 종전 표기(45/30/25)는 "
                        "강수 점수를 한 번도 산출한 적이 없어 실효 가중치(0.6/0.4)와 달랐다 — 실효값을 명시값으로 "
                        "올린 것이라 총점 숫자는 바뀌지 않는다. precipitation=0은 '중요하지 않다'가 아니라 "
                        "'작물별 optimal range 문헌이 없어 채점하지 않는다'는 뜻이다(memory/open-gaps.md 필요문헌 4번).",
        "percentile_note": "total_score_{crop}_percentile(2026-07-25 도입)은 크롭 내부 상대순위(0~100)일 뿐, "
                            "크롭간 절대 비교가 아니다. 크롭마다 문헌 기준의 엄격도가 실제로 다르므로(예: 상추 RDA "
                            "토양기준이 감자보다 훨씬 좁음, 전국 pH 중앙값 5.91이 상추 optimal 6.5~7.0과 구조적으로 "
                            "어긋남) total_score_{crop} 절대값 자체는 그대로 둔다 — 가중치를 임의로 조정해 크롭간 "
                            "점수를 맞추지 않는다(CLAUDE.md §2·§8).",
        "imputation_rule": "2026-07-29 개정: 원시값 공간에서 거리역수 가중 KNN 대체"
                            f"(k={impute_report['k_used']}, 홀드아웃 CV로 선택). 예측인자 = 공간(위경도→km "
                            "평면) + 기후 4피처 + 나머지 원시변수. 폴백: KNN 불가 → 컬럼 평균 → 점수 50.0. "
                            "이상치는 이웃 대비 KNN 잔차 modified z>3.5를 결측 처리해 재대체하고 원본값은 "
                            "imputation_outliers.csv에 보존한다. 상세·베이스라인 비교는 imputation_validation.json.",
        "reliability_flag_rule": "soil_score_total_missing = ph/유기물/유효인산 중 하나라도 결측. "
                                  "total_score_{crop}_missing = 토양 결측 or 해당 작물 기온 결측. "
                                  "대체값 자체는 그대로 쓰되(총점 계산엔 포함), 신뢰도만 별도 표시.",
        "imputation": {k: v for k, v in impute_report.items() if k != "outliers"},
        "soil_score_total_missing_count": int(df["soil_score_total_missing"].sum()),
        "crop_soil_overrides": {code: list(rules.keys()) for code, rules in crop_soil_overrides.items()} or "없음",
        "regions": len(df),
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    VALIDATION.write_text(
        json.dumps(impute_report["k_selection"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    # 이상치로 판정된 원본값은 지우지 않고 남긴다 — "진짜 특이 토양"일 수 있다(§18-4).
    pd.DataFrame(impute_report["outliers"]).to_csv(OUTLIERS, index=False, encoding="utf-8")

    print(f"{OUT.name}: {len(df)} regions | KNN k={impute_report['k_used']}")
    for name, mae in impute_report["k_selection"].get("normalized_mae", {}).items():
        print(f"  CV 정규화 MAE {name}: {mae}")
    for col, v in impute_report["columns"].items():
        print(f"  {col}: 원본결측 {v['original_missing']}, 이상치 {v['knn_outlier']}, "
              f"물리범위위반 {v['physical_violation']}, 방법={v['method_counts']}")


if __name__ == "__main__":
    main()
