"""RegionalScore.csv 생성 — AnswerData(문헌 기준)와 실제 지역 데이터를 비교한 지역별 점수.

기존 산출물을 확장(재계산 아님):
  - 토양: `data/01_soil_chemistry_modified.csv`(지역 조인 완료, 150/150) + EC는
    `data/ml/soil_ec_by_region.csv` x 각 크롭의 `soil_overrides`. **공유 밴드는 없다**
    (2026-08-03 삭제, 출처 미확인) — 모든 화학 지표가 작물별 문헌 밴드로만 채점되고
    `soil_score_total_{crop_code}`만 산출된다. 작물 무관 `soil_score_total`은 사라졌다.
    필수 지표(`_shared.json.required_soil_indicators`)를 갖지 않은 크롭은 조용히 폴백하지
    않고 `load_crop_overrides()`가 `ValueError`로 즉시 실패한다.
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

가중치: `_shared.json.weights`에서 읽는다(토양60/기온40/강수0, 2026-08-01 재설계).
하드코딩하지 않으며 `precipitation != 0`이면 assert로 즉시 실패한다. 강수 0은
"중요하지 않다"가 아니라 "작물별 optimal range 문헌이 없어 채점하지 않는다"는 뜻이다.

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

from dispersion import physical_rule, soil_rule, temp_rule
from imputation import impute, latlon_to_km
from scoring import band_score, category_score  # 백엔드 룰 엔진과 같은 곡선(scoring.py docstring 참조)

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
SOIL_VALUE_COLS = ["pH", "organic_matter", "available_p", "k", "ca", "mg", "ec"]
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
# 문헌이 주는 크롭만 채점하는 추가 화학 지표(2026-07-25 상추 도입, 2026-08-03 5작물 전체 보유).
# ec(2026-08-03)는 01_soil_chemistry가 아니라 data/ml/soil_ec_by_region.csv에서 온다 — 처방 5차가
# EC 기준을 주는 작물은 오이·감자·상추 3종뿐이고(사과·배 칸은 '–') 그 3종만 채점된다.
EXTRA_SOIL_COL = {"k": "k", "ca": "ca", "mg": "mg", "ec": "ec"}

# 물리성 지표(2026-08-03 도입). 경로가 둘이다.
#   - 연속형(경사·자갈): 등급코드를 _shared.json physical_code_maps로 등급 상한 %로 환산해
#     화학 지표와 같은 band_score 곡선에 태운다. 자갈 기준은 문헌상 감자에만 있어 감자만 채점.
#   - 범주형(심토토성, 2026-08-03 신설): 등급코드 자체를 키로 문헌 배점표를 조회한다
#     (scoring.category_score). 토성은 단조 순위가 없어 %·순위 환산이 원리적으로 불가능하다 —
#     사과 최적은 사양질·미사사양질, 배 최적은 식양질·미사식양질로 순위가 정반대다.
#     배점표를 가진 사과·배만 채점된다.
_SHARED = json.loads(RULES.read_text(encoding="utf-8"))
PHYSICAL_CODE_MAPS = _SHARED["physical_code_maps"]
PHYSICAL_COL = PHYSICAL_CODE_MAPS["source_column"]  # {연속형 지표: 원본 등급코드 컬럼}
PHYSICAL_CATEGORY_COL = PHYSICAL_CODE_MAPS["category_source_column"]  # {범주형 지표: 원본 컬럼}
REQUIRED_SOIL = _SHARED["required_soil_indicators"]


def load_crop_overrides():
    """crop_rules/<crop>.json → ({crop_code: 화학 규칙}, {crop_code: 물리성 규칙}).

    2026-08-03: 공유 soil_rules가 삭제돼 폴백이 없다. 필수 지표(REQUIRED_SOIL)를 갖지 않은
    크롭은 조용히 공유값으로 채점되는 대신 즉시 실패한다 — 출처 없는 값이 산출물에 섞이는
    경로 자체를 없애기 위함이다(_shared.json soil_rules_removed_note).
    """
    soil, physical = {}, {}
    for path in sorted(CROP_RULES_DIR.glob("*.json")):
        if path.name == "_shared.json":
            continue
        crop = json.loads(path.read_text(encoding="utf-8"))
        code = crop["crop_code"]
        so = crop.get("soil_overrides", {})
        missing = [ind for ind in REQUIRED_SOIL if ind not in so]
        if missing:
            raise ValueError(
                f"{path.name}: 필수 토양 지표 {missing} 밴드 없음. 공유 soil_rules는 "
                "2026-08-03에 삭제됐다(출처 미확인) — 작물별 문헌 밴드를 추가하거나, "
                "문헌이 없다면 그 작물을 채점 대상에서 빼야 한다. 폴백은 두지 않는다."
            )
        soil[code] = so
        if crop.get("physical_overrides"):
            physical[code] = crop["physical_overrides"]
    return soil, physical


def physical_frame(regions):
    """물리성 원시 프레임. 연속형은 대표 %(등급 상한)로 환산하고, 범주형은 등급코드를 그대로 둔다.

    결측·99(기타)는 NaN으로 남긴다. KNN 대체 대상에 넣지 않는다 — 지형은 이웃 지역에서
    빌려올 수 있는 값이 아니고, 범주 3~6개를 연속값처럼 보간하면 없는 정밀도를 만들어낸다.
    결측은 기존 최종 폴백(UNFILLED_SCORE=50)으로 처리되고 `*_missing` 플래그로 노출된다.

    범주형(토성)을 환산하지 않는 이유: 어떤 %·순위로 바꾸든 단조 순서를 전제하게 되고,
    사과·배의 최적 토성이 정반대라 반드시 한쪽이 틀린다. 코드가 배점표의 키다.
    """
    phys = pd.read_csv(DATA / "02_soil_physical_modified.csv", dtype={"region_code": str})
    out = regions[["region_code"]].merge(phys, on="region_code", how="left")
    for indicator, col in PHYSICAL_COL.items():
        code_to_pct = {int(k): v for k, v in PHYSICAL_CODE_MAPS[indicator].items()}
        out[indicator] = out[col].map(
            lambda c: code_to_pct.get(int(c)) if pd.notna(c) else None
        ).astype("float64")
    for indicator, col in PHYSICAL_CATEGORY_COL.items():
        out[indicator] = out[col].map(
            lambda c: int(c) if pd.notna(c) else None
        ).astype("Int64")
    return out.set_index("region_code")[[*PHYSICAL_COL, *PHYSICAL_CATEGORY_COL]]


def temp_raw_col(crop_code: str) -> str:
    return f"temp_raw_{crop_code}"


def load_raw_features(regions):
    """지역별 원시 변수(토양 6 + 작물 앵커월 평균기온 5)와 KNN 예측인자 기본 피처.

    반환: (원시값 프레임, 예측인자 base 프레임, 대체 대상 컬럼 목록).
    base = 위경도 등거리 평면(x_km,y_km) + 기후 4피처. 기후 피처는 기상 관측이 없는
    14개 지역에서 결측이지만 nan-aware 거리라 남은 피처로 거리가 계산된다.
    """
    chem_cols = [c for c in SOIL_VALUE_COLS if c != "ec"]
    soil = pd.read_csv(DATA / "01_soil_chemistry_modified.csv", dtype={"region_code": str})
    soil = soil[["region_code", *chem_cols]].drop_duplicates("region_code")
    # EC는 별도 집계 파일에서 온다(흙토람 필지 실측 → 시군구 중앙값). 평균이 아니라 중앙값을
    # 쓰는 이유는 분포가 오른쪽으로 심하게 치우쳐 시설 염류집적 필지가 지역 대표값을 끌어올리기 때문.
    ec = pd.read_csv(DATA / "ml" / "soil_ec_by_region.csv", dtype={"region_code": str})
    soil = soil.merge(
        ec[["region_code", "ec_median"]].rename(columns={"ec_median": "ec"}),
        on="region_code", how="left",
    )

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


def build_soil(df, raw_missing, crop_soil_overrides, crop_physical_overrides, physical):
    """대체 완료된 원시 토양값 + 물리성으로 작물별 토양 총점을 낸다.

    2026-08-03 개정 2건:
      1. **공유 밴드 경로 삭제.** 종전엔 출처미상 공유 soil_rules로 `{var}_score`를 먼저 내고
         override가 있는 지표만 덮어썼다. 이제 모든 화학 지표가 작물별 문헌 밴드로만
         채점된다 — 작물 무관 `soil_score_total` 컬럼도 함께 사라진다(그 값이 어느 문헌
         기준인지 말할 수 없기 때문이다).
      2. **물리성 지표 합류.** 경사·자갈이 화학 지표와 같은 평균에 들어간다. 별도 가중치를
         만들지 않은 이유는 배분 비율을 줄 문헌이 없어서다(_shared.json scoring_version_note).

    반환: (df, {crop_code: [그 작물 총점을 구성한 지표 점수 컬럼]}). 두 번째 값은 제한요인
    (MLCM) 점수가 "어떤 인자들 중 최악인가"를 알아야 해서 필요하다 — 여기서 이미 조립한
    목록을 재계산하지 않고 그대로 넘긴다(정의가 갈라지면 안 된다).
    """
    crop_indicator_cols = {}
    for crop_code in CROPS:
        override_rules = crop_soil_overrides[crop_code]
        indicator_scores, missing_flags = [], []

        for var, rule in override_rules.items():
            col = SOIL_COL.get(var) or EXTRA_SOIL_COL[var]
            score_col = f"{var}_score_{crop_code}"
            df[score_col] = score_column(df[col], soil_rule(rule, var)).round(1)
            indicator_scores.append(score_col)
            missing_flags.append(raw_missing[col])

        for var, rule in crop_physical_overrides.get(crop_code, {}).items():
            values = df["region_code"].map(physical[var])
            # 원시값을 싣는다 — 연속형은 대표 %(등급 상한), 범주형은 등급코드 자체.
            # 프론트가 관측값을 보여줄 수 있어야 사람이 채점을 검증할 수 있다.
            df[var] = values
            score_col = f"{var}_score_{crop_code}"
            # `code_scores`를 가진 규칙은 밴드가 아니라 배점표다 — band_score에 넘기면
            # optimal_min/max가 없어 즉시 예외가 나거나(있다면) 없는 순위를 가정하게 된다.
            if "code_scores" in rule:
                scored = values.apply(lambda c: category_score(c, rule))
            else:
                scored = values.apply(lambda v: band_score(v, physical_rule(rule, var)))
            df[score_col] = scored.fillna(UNFILLED_SCORE).round(1)
            df[f"{var}_missing_{crop_code}"] = values.isna()
            indicator_scores.append(score_col)
            missing_flags.append(values.isna())

        df[f"soil_score_total_{crop_code}"] = df[indicator_scores].mean(axis=1).round(1)
        df[f"soil_score_total_{crop_code}_missing"] = pd.concat(missing_flags, axis=1).any(axis=1)
        crop_indicator_cols[crop_code] = indicator_scores

    # 원시값 결측 플래그는 작물과 무관하므로 한 번만 노출한다(종전 `{var}_missing`과 동일).
    for col in SOIL_VALUE_COLS:
        df[f"{col}_missing"] = raw_missing[col]
    return df, crop_indicator_cols


def build_temp(df, raw_missing, crop_indicator_cols):
    """대체 완료된 앵커월 평균기온으로 채점 + 작물별 총점 조립(가중평균·MLCM 두 가지).

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

        # 적지등급 기온(2026-08-04 ⓒ). 같은 앵커월 기온을 국가 적지평가 기준으로 다시 채점한다 —
        # `temp`는 "자랄 수 있는 기온인가", 이쪽은 "국가가 적지로 보는가"라는 다른 질문이다.
        # in_total=False라 주 총점 min 대상에서 빠진다(앵커 주석의 실측 근거 참고). 지금은
        # 사과만 이 지표를 갖는다 — 다른 작물은 적지/가능지 2단계 문헌이 없다.
        grade_rule = CROP_ANCHORS[crop_code].get("temp_suitability_grade")
        if grade_rule is not None:
            df[f"temp_grade_{crop_code}_{name}_score"] = score_column(
                df[col], temp_rule(grade_rule, crop_code)
            ).round(1)

        # 대체·이상치치환이 없었던 행만 비교한다(치환된 행은 당연히 달라진다).
        reference = df["region_code"].map(anchor[f"score_{crop_code}_temp"])
        observed = (df[f"{col}__impute_method"] == "measured") & reference.notna()
        if observed.any():
            drift = float((score[observed] - reference[observed]).abs().max())
            assert drift <= 0.1, f"{name} 기온 점수가 실험 CSV와 불일치(최대 {drift})"

        # 2026-08-03: 모든 작물이 작물별 토양 총점을 갖는다(공유 총점 폴백 없음).
        soil_col = f"soil_score_total_{crop_code}"
        soil_missing_col = f"{soil_col}_missing"
        # 종전 정의(가중평균). 2026-08-04부터 **주 총점이 아니다** — 회귀 진단과 기존
        # 산출물 대조용으로 남긴다. 지우면 점수가 왜 달라졌는지 설명할 수 없다.
        df[f"total_score_{crop_code}_{name}_weighted_mean"] = (
            df[soil_col] * SOIL_FRAC + df[f"temp_{crop_code}_{name}_score"] * TEMP_FRAC
        ).round(1)
        df[f"total_score_{crop_code}_{name}_missing"] = (
            df[soil_missing_col] | df[f"temp_{crop_code}_{name}_missing"]
        )

        # 🔴 **주 총점 = 국가 적지평가 3단 구조**(2026-08-04 사용자 결정).
        # 심교문 2016 영농기술정보 원문의 구조를 그대로 옮긴다:
        #     토양 항목 → 요인별 점수제 합산 → 토양 등급
        #     기후 항목 → 최대저해인자법     → 기후 등급
        #     두 등급을 다시 최대저해인자법으로 통합
        # 즉 MLCM은 토양 **내부**가 아니라 기후 내부와 토양↔기후 통합에서만 쓰인다. 우리
        # 토양 총점은 지표 균등평균(0~100)이라 국가의 '항목 20점 만점 합산 → 100점 만점'과
        # 같은 정규 척도이므로 그대로 토양 등급 자리에 놓을 수 있다. 기후는 기온 1축만
        # 채점하므로 그 축의 min = 기온 점수 자신이다(강수는 채점되지 않아 min 대상에서도 빠짐).
        #
        # 종전(2026-08-04 오전)에는 토양 지표 하나하나까지 한 번에 min하는 **평탄 min**이
        # 주 총점이었다. 실측으로 그 구조를 버렸다: 평탄 min은 지표 8~10개 중 하나만 낮아도
        # 총점이 그 값이 되어 150지역 중 사과 138·상추 148·감자 143지역이 C등급이 됐다.
        # 국가가 합산으로 처리하는 층에 MLCM을 겹쳐 적용한 것이 원인이다.
        # 🔴 등급 공간에서 min하는 안(FinalReport §3-1 ⓐ)은 채택하지 않았다 — 등급 함수가
        # 점수에 대해 단조라서 min∘등급 = 등급∘min이고, 150지역×5작물 전수에서 등급 분포가
        # 평탄 min과 완전히 일치했다(등급을 한 지역도 바꾸지 않는다).
        df[f"total_score_{crop_code}_{name}"] = pd.concat(
            [df[soil_col], df[f"temp_{crop_code}_{name}_score"]], axis=1
        ).min(axis=1).round(1)

        # 평탄 min은 진단용으로 보존한다 — 주 총점에서 밀려났을 뿐 "어느 지표 하나가
        # 치명적인가"를 보는 데는 이 값이 맞다. 지우면 구조 교체 전후를 대조할 수 없다.
        factor_cols = crop_indicator_cols[crop_code] + [f"temp_{crop_code}_{name}_score"]
        df[f"total_score_{crop_code}_{name}_mlcm_flat"] = df[factor_cols].min(axis=1).round(1)

        # 무엇이 총점을 정했는가. 국가 구조에서는 먼저 **층**(토양/기온)이 갈리고, 토양이
        # 결속했으면 그 안에서 가장 낮은 지표까지 알려준다 — 층만 알려주면 "토양이 문제"에서
        # 더 나아갈 수 없고, 지표만 알려주면 그 지표가 실제로 총점을 정했는지 알 수 없다.
        soil_binds = df[soil_col] <= df[f"temp_{crop_code}_{name}_score"]
        worst_soil = (
            df[crop_indicator_cols[crop_code]].idxmin(axis=1)
            .str.replace(f"_{crop_code}$", "", regex=True)
        )
        df[f"limiting_factor_{crop_code}_{name}"] = worst_soil.where(soil_binds, "기온")
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

    crop_soil_overrides, crop_physical_overrides = load_crop_overrides()
    physical = physical_frame(regions)

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

    df, crop_indicator_cols = build_soil(
        df, raw_missing, crop_soil_overrides, crop_physical_overrides, physical
    )
    df = build_temp(df, raw_missing, crop_indicator_cols)
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
        # 세 총점은 구조적으로 평탄 min ≤ 국가 3단 ≤ 가중평균이다. min 대상이 넓을수록
        # 낮고, min은 그 인자들의 가중평균을 넘을 수 없다. 순서가 깨지면 컬럼 정의가 뒤바뀐 것이다.
        weighted = df[f"total_score_{crop_code}_{name}_weighted_mean"]
        national = df[f"total_score_{crop_code}_{name}"]
        flat = df[f"total_score_{crop_code}_{name}_mlcm_flat"]
        assert weighted.between(0, 100).all(), f"{name} 가중평균 범위 위반"
        assert flat.between(0, 100).all(), f"{name} 평탄 MLCM 범위 위반"
        assert (national <= weighted + 0.05).all(), \
            f"{name} 국가구조 총점이 가중평균보다 높다 — min 정의 위반"
        assert (flat <= national + 0.05).all(), \
            f"{name} 평탄 MLCM이 국가구조 총점보다 높다 — 토양 합산/평탄 min 구조가 뒤바뀌었다"
        # 제한요인은 실제로 총점을 정한 쪽을 가리켜야 한다. "기온"이라 적혀 있으면 기온 점수가
        # 곧 총점이어야 한다 — 이 대조가 없으면 층 판정이 뒤집혀도 산출물에서 드러나지 않는다.
        is_temp = df[f"limiting_factor_{crop_code}_{name}"] == "기온"
        if is_temp.any():
            temp_score = df.loc[is_temp, f"temp_{crop_code}_{name}_score"]
            assert (national[is_temp] - temp_score).abs().max() <= 0.05, \
                f"{name} 제한요인이 기온인데 총점이 기온 점수와 다르다"
    for crop_code in CROPS:
        assert f"soil_score_total_{crop_code}" in df.columns, f"{crop_code} 토양 총점 컬럼 누락"
    assert "soil_score_total" not in df.columns, \
        "작물 무관 공유 토양 총점이 남아 있다 — 공유 밴드는 2026-08-03에 삭제됐다"
    assert df["region_code"].is_unique, "지역 중복"

    df.to_csv(OUT, index=False, encoding="utf-8")

    # 가중평균 vs MLCM 분포 비교. 2026-08-04에 MLCM이 주 총점이 됐으므로 이제 이 표는
    # "교체 판단 자료"가 아니라 **교체로 무엇이 얼마나 달라졌는가의 기록**이다.
    mlcm_compare = {}
    for crop_code, name in CROPS.items():
        w = df[f"total_score_{crop_code}_{name}_weighted_mean"]
        n = df[f"total_score_{crop_code}_{name}"]          # 주 총점 = 국가 3단 구조
        m = df[f"total_score_{crop_code}_{name}_mlcm_flat"]  # 진단용 평탄 min
        soil = df[f"soil_score_total_{crop_code}"]
        mlcm_compare[name] = {
            "weighted_mean": round(float(w.mean()), 1),
            "national_mean": round(float(n.mean()), 1),
            "national_zero_regions": int((n == 0).sum()),
            "flat_mlcm_mean": round(float(m.mean()), 1),
            "flat_mlcm_zero_regions": int((m == 0).sum()),
            "national_rank_spearman": round(float(w.rank().corr(n.rank(), method="pearson")), 3),
            # 국가 구조에서 총점을 정한 쪽이 토양인 지역 수(나머지는 기온이 제한요인).
            "national_limiting_soil_regions": int((soil <= df[f"temp_{crop_code}_{name}_score"]).sum()),
            # 🔴 기후층이 결속하지 않으면 주 총점은 토양 총점 자신이 된다 — 그때 기온은 채점에
            # 사실상 기여하지 않는다. 이 차이가 0에 가까우면 그 상태라는 신호다.
            "national_minus_soil_mean": round(float((n - soil).mean()), 2),
            "limiting_factor_top": (
                df[f"limiting_factor_{crop_code}_{name}"].value_counts().head(3).to_dict()
            ),
        }

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
        "crop_band_precision_note": "크롭간 근거 정밀도가 비대칭이다. 2026-08-03 이후 5작물 "
                            "전부 작물별 문헌 밴드로만 채점되지만(공유 밴드 삭제) 출처 계열이 다르다 — "
                            "사과·배는 RDA 교본(사과 표5-21 2018·2025 동일 / 배 표5-25), 감자·오이·상추는 "
                            "RDA 비료사용처방 5차(2022, 각각 p83·p103·p169)이며 후자는 원문이 "
                            "「시설재배토양」 표기인데 우리 실측은 노지다. `allowed`는 문헌 직접값이 있는 "
                            "일부를 빼면 여전히 `optimal ±50%` 휴리스틱이다. 따라서 "
                            "total_score_{crop} 절대값의 크롭간 비교는 어긋난다 — "
                            "percentile(크롭 내 상대순위)만 크롭간 나란히 "
                            "읽을 수 있다. 또한 같은 토양이 작물별로 정반대 판정을 받을 수 있다: "
                            "치환성 Ca를 사과 교본은 '5~6 cmol/kg 이상'(상한 없음 → 단측 밴드)으로, "
                            "배 교본은 '5~6'(양측)으로 써서 Ca 14.42 지역이 사과 100점·배 0점이 된다. "
                            "계산 오류가 아니라 두 교본의 표기 차이를 그대로 반영한 것이며, 어느 "
                            "표기가 옳은지는 미확정이다([확인 필요], knowledge-base/registry.md §1).",
        "imputation_rule": "2026-07-29 개정: 원시값 공간에서 거리역수 가중 KNN 대체"
                            f"(k={impute_report['k_used']}, 홀드아웃 CV로 선택). 예측인자 = 공간(위경도→km "
                            "평면) + 기후 4피처 + 나머지 원시변수. 폴백: KNN 불가 → 컬럼 평균 → 점수 50.0. "
                            "이상치는 이웃 대비 KNN 잔차 modified z>3.5를 결측 처리해 재대체하고 원본값은 "
                            "imputation_outliers.csv에 보존한다. 상세·베이스라인 비교는 imputation_validation.json.",
        "reliability_flag_rule": "soil_score_total_{crop}_missing = 그 작물 토양 총점을 구성한 "
                                  "지표(화학 + 물리성) 중 하나라도 원본 결측. "
                                  "total_score_{crop}_missing = 토양 결측 or 해당 작물 기온 결측. "
                                  "대체값 자체는 그대로 쓰되(총점 계산엔 포함), 신뢰도만 별도 표시. "
                                  "2026-08-03: 작물 무관 soil_score_total(_missing) 컬럼은 사라졌다.",
        "shared_band_removal_note": "2026-08-03 사용자 결정: 출처미상 공유 soil_rules(ph 6.0~7.0 / "
                            "organic_matter 20~30 / available_p 300~550)를 채점에서 제거하고 5작물 "
                            "전부 문헌 출처가 있는 작물별 밴드로 전환했다. 특히 available_p 300~550은 "
                            "RDA 비료사용처방 5차(작물별 200~500)와 국가농업환경변동조사 등급표"
                            "(최적 200~450) 양쪽에서 반증된 값이었다. 감자는 종전에 ph override가 없어 "
                            "공유 6.0~7.0으로 채점됐는데 감자는 산성 토양 작물(교본 5.0~6.0)이라 방향이 "
                            "반대였다 — 이번 개정의 최대 결함 수정이다. 코드는 필수 지표 밴드가 없는 "
                            "작물을 만나면 폴백하지 않고 즉시 실패한다.",
        "physical_axis_note": "2026-08-03 신규: 물리성(경사 slope_pct, 자갈 gravel_pct)을 토양 총점 "
                            "구성인자로 추가했다. 근거는 RDA 「작물별 비료사용처방」 5차(2022) 물리성 표"
                            "(사과 경사 0-15% / 나머지 0-7%, 자갈은 감자만 0-35%)이고, 입력은 "
                            "data/02_soil_physical_modified.csv의 등급코드를 _shared.json "
                            "physical_code_maps로 등급 상한 %로 환산한 값이다. ⚠️근사·한계 3건: "
                            "① 등급 내 최악값(상한)을 대표로 쓴다 — 등급 내 실제 분포가 데이터에 없다. "
                            "② 자갈 최상위 등급('35% 이상')은 상한이 열려 있어 물리적 최대 100%로 둔다. "
                            "③ 등급이 3~6개뿐이라 해상도가 화학 지표보다 훨씬 거칠고, 자갈은 사실상 "
                            "'코드 1·2 = 100점 / 코드 3 = 0점'으로 작동한다. "
                            "가중치(soil 60/temp 40)는 바꾸지 않았고 토양 총점 내부 균등 평균에 합류시켰다 "
                            "— 물리성 배분 비율을 줄 문헌이 없기 때문이다(추측 금지).",
        "texture_axis_note": "2026-08-03 신규(4차 리서치 유입): 심토토성(subsoil_texture)을 사과·배 "
                            "토양 총점 구성인자로 추가했다. 종전엔 '처방 5차의 사양질~식양질 코드 순서 "
                            "해석이 문헌으로 확정되지 않는다'는 이유로 미채점이었는데, 그 사유는 순서를 "
                            "추정하려 했기 때문에 생긴 것이다. 심교문(2016) 「토양·기후요인을 종합적으로 "
                            "고려한 과수 재배적지 구분」(국립농업과학원 영농기술정보)이 등급 이름 그대로 "
                            "4등급 배점표(20/15/10/5)를 주므로 순서 추정이 불필요해졌다 — 등급코드를 키로 "
                            "배점표를 직접 조회한다(scripts/ml/scoring.py category_score, 밴드 아님). "
                            "교차 확인: climate-soil-integrated-suitability-2021(PJ013548) 표11·표14와 일치. "
                            "🔴 사과와 배의 최적 토성이 정반대다 — 사과는 사양질·미사사양질(20점), 배는 "
                            "식양질·미사식양질(20점). 같은 흙이 두 작물에서 100점/50점으로 갈리며 이는 "
                            "계산 오류가 아니라 국가 배점표 자체의 작물별 차이다. 공통 토성 규칙을 쓰면 "
                            "반드시 한쪽이 틀린다. 감자·오이·상추는 등급별 배점표가 없어 미채점 유지 "
                            "(처방 5차엔 '사양질~식양질' 범위만 있다). 배점 20/15/10/5 → 100/75/50/25 환산은 "
                            "국가 토양 적지평가가 항목당 20점 만점 합산이라는 사실의 산술 변환이며 휴리스틱이 "
                            "아니다. ⚠️미채택 2건(문헌은 확보, 데이터가 없다): 같은 배점표의 배수등급은 "
                            "「양호 20점 > 매우양호 15점」의 U자형(과배수도 감점)이고 유효토심 4등급도 있으나 "
                            "data/02_soil_physical_modified.csv에 두 컬럼이 아예 없다(codebook 검색 0건) — "
                            "밴드를 만들지 않는다. 배 자갈은 배점표 최적 경계가 <10%인데 우리 최하 등급이 "
                            "0-15%라 경계가 어긋나 분해되지 않는다. ⚠️미해결 충돌 1건: 사과 경사를 처방 5차는 "
                            "단일 구간 0-15%로, 이 배점표는 0-7(20점)/7-15(15점) 4등급으로 준다 — 국가 자료 "
                            "2건이 충돌해 기존 처방 5차 값을 유지했다 [확인 필요]. 사과·배 soil_score_total은 "
                            "지표가 7→8개로 늘어 이전 산출과 직접 비교할 수 없다(scoring_version 2026-08-03-v3). "
                            "⚠️값 충돌 주의: 토성 결측(등급코드 없음 5지역, 99=기타)은 다른 지표와 같은 최종 폴백 "
                            "UNFILLED_SCORE=50점을 받는데, 토성에서 50점은 '가능지'라는 **실제 등급값**이기도 하다 "
                            "— 즉 subsoil_texture_score 50은 '가능지'와 '판정불가'가 같은 숫자로 나온다. "
                            "구분은 subsoil_texture_missing_{crop} 플래그로만 가능하고, 그 플래그는 "
                            "soil_score_total_{crop}_missing으로도 전파된다. 점수만 읽고 등급을 역추론하면 안 된다.",
        "mlcm_note": "🔴 **2026-08-04: total_score_{crop}은 국가 적지평가 3단 구조다.** "
                      "min(토양 총점, 기온 점수) — 토양은 요인별 점수제로 합산해 토양 등급을 내고, "
                      "기후는 최대저해인자법으로 묶고, 두 결과를 다시 최대저해인자법으로 통합한다"
                      "(심교문 2016 영농기술정보 원문: '토양요인 … 요인별 점수제를 활용' / '기후요인 … "
                      "최대저해인자법을 활용' / '기후요인 결과값과 토양요인 결과값을 최대저해인자법으로 통합'). "
                      "종전 정의(가중평균)는 total_score_{crop}_weighted_mean으로 병기하고, 토양 지표 "
                      "하나하나까지 한 번에 min하는 **평탄 min**은 total_score_{crop}_mlcm_flat으로 "
                      "진단용 보존한다. 무엇이 총점을 정했는지는 limiting_factor_{crop}에 있다 — 토양이 "
                      "결속했으면 그 안의 최악 지표명, 기온이 결속했으면 '기온'이다. "
                      "🔴 **구조 교체 경위(같은 날 두 번 바뀌었다)**: 오전에 평탄 min을 주 총점으로 "
                      "올렸는데 실측에서 150지역 중 사과 138·상추 148·감자 143지역이 C등급이 됐다. "
                      "지표 8~10개 중 하나만 낮아도 총점이 그 값이 되기 때문이고, 국가가 합산으로 처리하는 "
                      "층에 MLCM을 겹쳐 적용한 것이 원인이다. 등급 공간에서 min하는 안(FinalReport §3-1 ⓐ)은 "
                      "**채택하지 않았다** — 등급 함수가 점수에 대해 단조라서 min∘등급 = 등급∘min이고 "
                      "150지역×5작물 전수에서 등급 분포가 평탄 min과 완전히 일치했다(등급을 한 지역도 "
                      "바꾸지 않는다). 사용자 결정으로 국가 3단 구조를 채택했다. "
                      "근거: 김호정 외(2016) 한국농림기상학회지 18(3):127-134이 MLCM을 '최악 인자 등급 "
                      "채택'으로 정의, Kim & Shim(2019)이 MLCM(전국 적지 19.55%)이 AHP(99.08%)보다 실측 "
                      "재배면적에 근접함을 확인, Boguszewska 2022에서 감자 고온 14.9% + 건조 23.2%의 복합 "
                      "처리가 단순합 38.1%가 아니라 실제 29.2%(합산은 복합 스트레스를 과대평가한다). "
                      "⚠️근사·한계 4건: ① 원문은 등급(최적지·적지·가능지·저위생산지) 기반 min인데 여기서는 "
                      "연속 점수의 min을 쓴다 — 국가 컷(토양 85/80/70)으로 이산화하지 않았다. "
                      "② 우리 토양 총점은 지표 균등평균이고 국가는 5항목 × 20점 합산이다. 둘 다 100점 만점 "
                      "정규 척도라 같은 자리에 놓을 수 있지만 항목 집합이 다르다 — 국가 5항목(토성·경사·배수· "
                      "유효토심·자갈) 중 우리는 토성·경사만 갖고 배수·유효토심 컬럼이 없으며 대신 화학 6~7지표가 "
                      "들어가 있다. ③ 기후는 기온 1축만 채점하므로 그 층의 min은 기온 점수 자신이다 — 강수는 "
                      "채점되지 않아 min 대상에서도 빠진다(가중평균과 같은 누락). "
                      "④ 🔴 **기온이 사실상 총점에 기여하지 않는다.** national_minus_soil_mean 필드가 이걸 "
                      "정량화한다 — 사과는 +0.00으로 주 총점이 토양 총점과 완전히 같다. 생육적온 18~28이 "
                      "월평균 기온에는 거의 항상 만족돼(사과 기온 점수 평균 99.5, S 148/150) min에서 결속하지 "
                      "않기 때문이다. 즉 현재 주 총점은 실질적으로 토양 총점이다 [확인 필요]. "
                      "⚠️토양60/기온40 가중치는 이 구조에서 쓰이지 않는다 — 최소값에 가중 개념이 없다. "
                      "두 상수는 _weighted_mean 산출에만 남는다. "
                      "⚠️컬럼 정의가 바뀌었으므로 종전 산출물과 같은 이름의 값을 직접 비교하면 안 된다.",
        "temp_grade_note": "temp_grade_{crop}_{name}_score(2026-08-04 신규, 사과만)는 **적지 등급** "
                      "기온이다. temp_{crop}_{name}_score(생육적온 18~28)와 같은 앵커월 기온을 쓰지만 "
                      "다른 질문에 답한다 — 앞은 '이 작물이 자랄 수 있는 기온인가', 이쪽은 '국가 적지평가가 "
                      "이 지역을 사과 적지로 보는가'다. 한 지표에 두 값을 겹쳐 쓰던 것이 성격 오인이었고 "
                      "사용자 결정(2026-08-04 ⓒ)으로 분리했다. 밴드는 arccas 적지 14.5~18.5 / 가능지 "
                      "13.5~19.5로 두 경계 모두 문헌값이다(휴리스틱 없음). "
                      "🔴 **주 총점의 min 대상에 넣지 않는다**(in_total=False). 실측: 앵커월 전국평균 "
                      "20.67℃가 가능지 상한 19.5를 넘어 이 지표는 전국 평균 29.9점이고, min에 넣으면 사과 "
                      "주 총점이 74.9 → 30 아래로 무너져 C등급이 130지역을 넘는다(평탄 min 138지역보다 "
                      "나아지지 않는다). 그 숫자가 틀렸다는 뜻이 아니다 — 국가 기준으로는 한국 대부분이 이미 "
                      "사과 적지가 아닐 수 있고, 그 판단은 문헌이 아니라 사람이 내려야 한다 [확인 필요]. "
                      "하드 페널티(게이트)도 두지 않았다 — 감점 폭을 줄 문헌이 없어 만들면 휴리스틱이 된다. "
                      "다른 작물은 적지/가능지 2단계 문헌이 없어 이 지표를 갖지 않는다.",
        "mlcm_vs_weighted": mlcm_compare,
        "imputation": {k: v for k, v in impute_report.items() if k != "outliers"},
        "soil_score_total_missing_count": {
            name: int(df[f"soil_score_total_{code}_missing"].sum()) for code, name in CROPS.items()
        },
        "crop_soil_indicators": {code: list(rules.keys()) for code, rules in crop_soil_overrides.items()},
        "crop_physical_indicators": {code: list(rules.keys()) for code, rules in crop_physical_overrides.items()} or "없음",
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
