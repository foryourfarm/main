"""문헌값을 채점 앵커로 쓰는 5작물(사과·배·상추·감자·오이) 실험.

두 부분으로 나뉜다.
1) 결정론 룰: 문헌 이상치로부터의 편차 점수(ML 아님, "문헌 기반 예상 적합도").
2) unsupervised ML: 지역 기후 피처의 군집·이상치 구조(성과 레이블 무관, 서술형).

경계(CLAUDE.md §9): 성과 예측·ML 정확도 주장 없음. 앵커는 provisional이며
`[확인 필요]` 플래그를 유지한다. memory/crop_rules/·outcomes/는
건드리지 않는다 — 이 산출은 리서치 전용이다.

데이터 현실(2026-07-25 진단):
  - 선정 150지역 ∩ 기상2025 = 150 (완전). 군집·기온 점수는 여기서 가능.
  - 선정 150지역 ∩ 토양 화학성(05) = 2 (격자 불일치, open-gaps 결합 문제).
    → 토양 편차 점수는 사실상 산출 불가. 강제 대체하지 않고 결측으로 남긴다.

근거 앵커: memory/crop-domain-knowledge-3crops.md 및 memory/registry.md.
3작물 문서가 지시한 정정을 반영한다:
  - 오이 구 temp_day(20-22, P09)는 실제로 '근권 지온' 문헌값 → 대기 기온 채점에서 제외했었음.
    2026-07-25 사용자 승인으로 P14(강소라, ISSN 1229-1889) 시설 대기온도 22-28(최적25)을
    신규 앵커로 등록·채점 반영(외기↔시설 근사 가정, [확인 필요] 04009=코드북상 노지재배).
  - 감자 rainfall(33.3-66.7)은 문헌이 반증 → 강수 채점에서 제외.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
# 원본 산출물 이관 시 `outcomes/data/`는 함께 오지 않았다(git 미추적). 동일 파일명 데이터가
# 레포 루트 `/data`에 있어 거기를 가리킨다 — outcomes/ 안에 데이터를 중복 복사하지 않는다.
DATA = ROOT / "data"
OUT = DATA / "ml" / "crop_literature_anchor_experiment.csv"
MANIFEST = DATA / "ml" / "crop_literature_anchor_manifest.json"
SCORE_YEAR = 2025
SEED = 42

SOIL_RULES = {
    "ph": {"optimal_min": 6.0, "optimal_max": 7.0},
    "organic_matter": {"optimal_min": 20.0, "optimal_max": 30.0},
    "available_p": {"optimal_min": 300.0, "optimal_max": 550.0},
}

# 크롭별 문헌 앵커는 scripts/ml/crop_anchors/<crop>.py로 분리(작물마다 memory/문헌자료/
# 데이터가 달라 교차 오염 방지). 여기서는 조립만 한다.
SCRIPTS_ML = Path(__file__).resolve().parent
if str(SCRIPTS_ML) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ML))

from crop_anchors import apple, cucumber, lettuce, pear, potato
from dispersion import temp_rule  # 감쇠폭(전국 실측 산포도) 주입
from scoring import band_score  # 백엔드 룰 엔진과 같은 곡선(모듈 docstring 참조)

CROP_ANCHORS = {
    "09001": apple.ANCHOR,
    "09011": pear.ANCHOR,
    "07001": lettuce.ANCHOR,
    "03001": potato.ANCHOR,
    "04009": cucumber.ANCHOR,
}


def load_regions_weather():
    """선정 150지역 + 2025 월별 기상(피벗)."""
    regions = pd.read_csv(DATA / "raw" / "selected_regions_modified.csv", dtype={"region_code": str})
    regions = regions[["region_code", "region_name", "clmt_zone_code"]].drop_duplicates("region_code")

    w = pd.read_csv(DATA / "03_weather_monthly_modified.csv", dtype={"region_code": str})
    w = w[w["year"].astype(str) == str(SCORE_YEAR)].copy()
    w["month"] = pd.to_numeric(w["month"], errors="coerce")
    for c in ("avg_temp", "precipitation"):
        w[c] = pd.to_numeric(w[c], errors="coerce")
    return regions, w


def climate_features(regions, w):
    grow = w[w["month"].between(4, 9)]
    agg = w.groupby("region_code").agg(
        annual_mean_temp=("avg_temp", "mean"),
        temp_seasonality=("avg_temp", "std"),
        annual_precip=("precipitation", "sum"),
        weather_months=("month", "nunique"),
    ).reset_index()
    # 관측월이 12개 미만인 지역의 연간 집계는 연평균이 아니다 — 2026-08-01에 문경 흥덕동이
    # 1월(-3.0℃) 한 달만 유효한데 annual_mean_temp=-3.0으로 실려 KNN 예측인자·군집 피처를
    # 왜곡하고 있었다. 부분 관측은 결측으로 돌린다(가짜 연평균을 만들지 않는다).
    #
    # `weather_months`(=month.nunique())로는 못 잡는다: 그 지역은 12개월 행이 다 있고
    # avg_temp만 11개월이 NaN이라 nunique는 12다. 값이 실제로 있는 월을 따로 센다.
    valid = w.dropna(subset=["avg_temp"]).groupby("region_code")["month"].nunique()
    agg["valid_temp_months"] = agg["region_code"].map(valid).fillna(0).astype(int)
    partial = agg["valid_temp_months"] < 12
    agg.loc[partial, ["annual_mean_temp", "temp_seasonality", "annual_precip"]] = float("nan")
    grow_agg = grow.groupby("region_code").agg(growing_temp=("avg_temp", "mean")).reset_index()
    return regions.merge(agg, on="region_code", how="left").merge(grow_agg, on="region_code", how="left")


def _anchor_month_temp(w, months):
    sub = w[w["month"].isin(months)]
    return sub.groupby("region_code")["avg_temp"].mean()


def deterministic_scores(df, w):
    """문헌 앵커 편차 점수(결정론 룰). 앵커 없으면 NaN — 강제 대체 금지."""
    for crop_code, crop in CROP_ANCHORS.items():
        rule = crop["temp"]
        if rule is None:
            df[f"score_{crop_code}_temp"] = np.nan
        else:
            t = _anchor_month_temp(w, rule["months"])
            # 감쇠폭은 그 작물 앵커월 기온의 전국 실측 산포도 기반(2026-07-29, dispersion.py).
            scored_rule = temp_rule(rule, crop_code)
            df[f"score_{crop_code}_temp"] = (
                df["region_code"].map(t).apply(lambda v: band_score(v, scored_rule)).round(1)
            )
        # 토양 편차: 조인 실패로 사실상 결측. 이 실험에서는 기온만 총점 성분.
        df[f"score_{crop_code}_total"] = df[f"score_{crop_code}_temp"]
    return df


def unsupervised_structure(df):
    """지역 기후 피처의 군집·이상치. 성과 레이블 무관, 서술형."""
    feats = ["annual_mean_temp", "growing_temp", "temp_seasonality", "annual_precip"]
    usable = df.dropna(subset=feats).copy()
    X = StandardScaler().fit_transform(usable[feats])
    best = {"sil": -1.0}
    for k in range(2, 7):
        km = KMeans(n_clusters=k, random_state=SEED, n_init=10).fit(X)
        sil = silhouette_score(X, km.labels_)
        if sil > best["sil"]:
            best = {"k": k, "sil": sil, "labels": km.labels_, "km": km}
    dist = np.linalg.norm(X - best["km"].cluster_centers_[best["labels"]], axis=1)
    usable["env_cluster"] = best["labels"]
    usable["env_anomaly_dist"] = dist.round(3)
    usable["env_anomaly_flag"] = dist > np.quantile(dist, 0.90)
    df = df.merge(usable[["region_code", "env_cluster", "env_anomaly_dist", "env_anomaly_flag"]],
                  on="region_code", how="left")
    # 서술 교차확인: KMeans 군집 vs 공식 기후대(clmt_zone_code).
    xtab = pd.crosstab(usable["env_cluster"], df.set_index("region_code").loc[usable["region_code"], "clmt_zone_code"].values)
    info = {"k": best["k"], "silhouette": round(best["sil"], 3), "usable_regions": len(usable),
            "features": feats, "cluster_vs_climate_zone": xtab.to_dict()}
    return df, info


def main():
    regions, w = load_regions_weather()
    df = climate_features(regions, w)
    df = deterministic_scores(df, w)
    df, cluster_info = unsupervised_structure(df)

    for crop_code in CROP_ANCHORS:
        s = df[f"score_{crop_code}_total"].dropna()
        assert s.empty or s.between(0, 100).all(), f"{crop_code} 총점 0-100 위반"
    cucumber_rules = CROP_ANCHORS["04009"]["environment_rules"]
    assert all(rule["min"] <= rule["optimal"] <= rule["max"] for rule in cucumber_rules), "오이 환경 기준 범위 오류"
    assert df["score_04009_temp"].notna().any(), "오이 대기온도(P14) 점수 산출 실패"
    assert CROP_ANCHORS["09001"]["temp"] is not None, "사과 온도 앵커 등록 실패"
    assert df["score_09001_temp"].notna().any(), "사과 온도 점수 산출 실패"
    assert CROP_ANCHORS["09011"]["temp"] is not None, "배 사용자 지정 온도 앵커 등록 실패"
    assert df["score_09011_temp"].notna().any(), "배 온도 점수 산출 실패"
    assert cluster_info["usable_regions"] >= cluster_info["k"], "군집 표본 부족"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8")
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "anchor_source": "memory/crop-domain-knowledge-3crops.md",
        "score_year": SCORE_YEAR,
        "crops": {c: CROP_ANCHORS[c]["name"] for c in CROP_ANCHORS},
        "unscored_literature_anchors": {
            c: {"name": crop["name"], "documented_rules": crop["documented_rules"], "flag": crop["flag"]}
            for c, crop in CROP_ANCHORS.items() if crop["temp"] is None
        },
        "environment_rules": {"04009": cucumber_rules},
        "corrections_applied": [
            "오이 구 대기 기온 앵커(20-22, P09) 제거(근권 지온 혼동)",
            "오이 신규 대기 기온 앵커(22-28, P14) 등록·반영(2026-07-25 사용자 승인)",
            "감자 강수 앵커 제거(문헌 반증)",
        ],
        "data_reality": {"regions": len(df), "soil_chem_join": "실패(150중 2, 05 기준) — 토양 편차 점수 제외",
                         "score_component": "기온만"},
        "unsupervised": {k: v for k, v in cluster_info.items() if k != "cluster_vs_climate_zone"},
        "provisional": True,
        "approved_rules_touched": True,
        "claim_boundary": "문헌 기반 예상 적합도(기온) + 기후 군집. 성과 예측·ML 정확도 주장 아님(§9). 오이 앵커는 시설값의 노지 근사([확인 필요]).",
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{OUT.name}: {len(df)} regions | cluster k={cluster_info['k']} "
          f"sil={cluster_info['silhouette']} usable={cluster_info['usable_regions']}")
    for crop_code, crop in CROP_ANCHORS.items():
        col = df[f"score_{crop_code}_total"]
        n = col.notna().sum()
        m = round(col.mean(), 1) if n else "N/A"
        print(f"  {crop['name']}({crop_code}): 점수 지역 {n}, 평균 {m}")


if __name__ == "__main__":
    main()
