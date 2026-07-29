"""지표별 전국 실측 산포도 산출 → `memory/indicator_dispersion.json` (2026-07-29 도입).

**왜 필요한가**: 종전 채점 곡선은 위험구간(허용경계 밖)의 감쇠 거리를 **완충폭 1배**로 잡았다.
완충폭은 `allowed = optimal 폭 ±50%` 휴리스틱에서 나오므로, optimal이 좁은 지표는 완충폭도
좁고 위험구간까지 연동돼 좁아진다 — 3중 압축이다. 그 결과 채점이 사실상 이진이 됐다
(2026-07-29 측정, 150지역): 상추 pH 0점 107건, 사과 기온 0점 92건, 상추 Ca 0점 56건.

**해결**: 감쇠 거리를 문헌 밴드 폭이 아니라 **그 지표의 전국 실측 산포도**로 정한다.
"문헌 최적범위에서 전국 지역간 변동성의 N배 이상 벗어났다"를 0점 기준으로 삼는다.
지표 단위(mg/kg, ℃, cmol/kg)가 달라도 같은 의미의 척도가 되고, 문헌 밴드가 좁아도
채점이 절벽으로 무너지지 않는다.

**산포도는 표준편차가 아니라 robust 추정치(MAD 기반)를 쓴다**: 유효인산은 실측 최대
1288mg/kg(시설재배 인산 과다 축적, 실재값)이 섞여 표준편차가 부풀려진다. 이상치 하나가
전국 채점 척도를 늘려버리면 안 된다. 두 값을 모두 기록하고 `risk_width`는 robust 쪽으로 낸다.

**한계**: `RISK_SD_MULTIPLIER`(감쇠 거리 = robust 산포도의 몇 배인가)는 문헌 근거가 아니라
**명시적 휴리스틱**이다 — 정규 가정에서 2배는 전국 지역의 약 95%가 들어오는 폭이고,
"전국 어느 지역도 문헌 이탈만으로 곧바로 0점이 되지 않되 극단 지역은 0점"이 되는 지점으로
골랐다. 실제 감수 곡선 문헌을 확보하면 교체 대상이다 — `[확인 필요]`.
(`allowed = optimal ±50%`도 같은 성격의 휴리스틱이다. `memory/crop_rules/_shared.json` 참조.)
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT.parent / "data"
OUT = ROOT / "memory" / "indicator_dispersion.json"

SCRIPTS_ML = Path(__file__).resolve().parent
if str(SCRIPTS_ML) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ML))

from crop_literature_anchor_experiment import CROP_ANCHORS  # noqa: E402

SCORE_YEAR = 2025
MAD_TO_SIGMA = 1.4826  # MAD → 정규분포 표준편차 환산 상수

# 감쇠 거리 = robust 산포도 × 이 배수. 모듈 docstring의 한계 표기 참조.
RISK_SD_MULTIPLIER = 2.0

# 토양 원시 컬럼 → (outcomes 채점 규칙 키, 백엔드 indicator 이름)
SOIL_MAP = {
    "pH": ("ph", "ph"),
    "organic_matter": ("organic_matter", "organic"),
    "available_p": ("available_p", "p2o5"),
    "k": ("k", "k"),
    "ca": ("ca", "ca"),
    "mg": ("mg", "mg"),
}


def dispersion(values: pd.Series) -> dict:
    """전국 산포도. sd와 robust(MAD 기반)를 둘 다 기록하고 risk_width는 robust로 낸다."""
    v = values.dropna().astype(float)
    median = float(v.median())
    mad = float(np.median(np.abs(v - median)))
    robust_sd = MAD_TO_SIGMA * mad
    return {
        "n": int(len(v)),
        "median": round(median, 4),
        "sd": round(float(v.std()), 4),
        "robust_sd": round(robust_sd, 4),
        "risk_width": round(RISK_SD_MULTIPLIER * robust_sd, 4),
    }


def main():
    soil = pd.read_csv(
        DATA / "01_soil_chemistry_modified.csv", dtype={"region_code": str}
    ).drop_duplicates("region_code")
    weather = pd.read_csv(DATA / "03_weather_monthly_modified.csv", dtype={"region_code": str})
    weather = weather[weather["year"].astype(str) == str(SCORE_YEAR)].copy()
    for col in ("month", "avg_temp", "precipitation"):
        weather[col] = pd.to_numeric(weather[col], errors="coerce")

    soil_out, backend_out = {}, {}
    for raw_col, (rule_key, backend_name) in SOIL_MAP.items():
        d = dispersion(soil[raw_col])
        soil_out[rule_key] = d
        backend_out[backend_name] = d["risk_width"]

    # 기온은 작물별 앵커월이 달라 산포도도 달라진다 — 작물별로 낸다.
    temp_out = {}
    for crop_code, anchor in CROP_ANCHORS.items():
        rule = anchor["temp"]
        if rule is None:
            continue
        per_region = (
            weather[weather["month"].isin(rule["months"])].groupby("region_code")["avg_temp"].mean()
        )
        temp_out[crop_code] = dispersion(per_region) | {"months": rule["months"]}

    # 강수(월 합계)의 지역간 산포도. 현재 outcomes 채점에 쓰이는 강수 규칙은 없지만
    # (감자 강수 앵커는 문헌이 반증해 제외) 백엔드 rainfall 지표가 살아 있어 함께 낸다.
    monthly_precip = weather.groupby(["region_code", "month"])["precipitation"].sum()
    rainfall = dispersion(monthly_precip.groupby("region_code").mean())

    payload = {
        "generated_from": [
            "data/01_soil_chemistry_modified.csv",
            f"data/03_weather_monthly_modified.csv (year={SCORE_YEAR})",
        ],
        "method": "risk_width = RISK_SD_MULTIPLIER x robust_sd, robust_sd = 1.4826 x MAD. "
                  "표준편차 대신 robust 추정치를 쓰는 이유는 모듈 docstring 참조(유효인산 극단값).",
        "multiplier": RISK_SD_MULTIPLIER,
        "limitation": "multiplier는 문헌 근거가 아니라 명시적 휴리스틱이다 — 실제 감수 곡선 "
                      "문헌 확보 시 교체 대상 [확인 필요].",
        "soil": soil_out,
        "temp_by_crop": temp_out,
        "rainfall_monthly": rainfall,
        "backend_indicator_risk_width": backend_out
        | {"temp_day": round(float(np.mean([t["risk_width"] for t in temp_out.values()])), 4)},
        "backend_note": "temp_night_min·rainfall_daily는 이 데이터로 지역간 산포도를 낼 수 없어 "
                        "제외한다 — 백엔드는 그 지표에서 종전 완충폭 기준으로 폴백한다(숨기지 않음). "
                        "temp_day는 작물별 앵커월 산포도의 평균이다 [확인 필요].",
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"{OUT.name} 생성")
    for key, d in soil_out.items():
        print(f"  {key}: n={d['n']} sd={d['sd']} robust_sd={d['robust_sd']} risk_width={d['risk_width']}")
    for crop_code, d in temp_out.items():
        print(f"  temp[{crop_code}]: robust_sd={d['robust_sd']} risk_width={d['risk_width']}")
    print(f"  rainfall_monthly: risk_width={rainfall['risk_width']}")
    print(f"  백엔드 이관용: {payload['backend_indicator_risk_width']}")


if __name__ == "__main__":
    main()
