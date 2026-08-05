"""KNN 대체·이상치 탐지 계약 테스트 (scripts/ml/imputation.py).

검증 항목:
1. 결정론 — 같은 입력을 두 번 넣으면 같은 출력(CLAUDE.md §2).
2. 이웃 정보를 실제로 쓴다 — 전역 평균보다 이웃 값에 가깝게 채운다.
3. 다변량 예측 — 다른 변수와의 상관을 쓴다(공간만으로는 못 맞히는 케이스로 확인).
4. 폴백 — 컬럼 전체 결측·예측인자 전무에도 예외로 죽지 않는다(§18-5).
5. 물리 범위 위반값은 결측 처리된다.
6. 이상치 탐지 — 이웃 대비 튀는 값을 잡고, 치환 여부는 호출부가 고른다(원본 보존).
7. 산출물 계약 — RegionalScore.csv에 대체 방법·출처·이상치 컬럼이 있다.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ML = ROOT / "scripts" / "ml"
if str(SCRIPTS_ML) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ML))

from imputation import (  # noqa: E402
    OUTLIER_MODIFIED_Z,
    flag_physical_violations,
    impute,
    latlon_to_km,
    select_k,
)


def _grid_frame(n_side: int = 6):
    """격자 위의 합성 지역들. 값이 위치에 매끄럽게 의존하도록 만들어 이웃 정보가 실제로
    유효한 상황을 구성한다(공간자기상관 가정을 테스트에서도 성립시킨다)."""
    rows = []
    for i in range(n_side):
        for j in range(n_side):
            ph = 5.5 + 0.1 * i
            rows.append(
                {
                    "name": f"R{i}{j}",
                    "lat": 35.0 + i * 0.2,
                    "lon": 127.0 + j * 0.2,
                    "pH": ph,
                    # organic_matter는 pH의 선형 함수 → 다변량 예측 검증용
                    "organic_matter": 10.0 + 4.0 * ph,
                    "climate": 12.0 + 0.3 * i,
                }
            )
    frame = pd.DataFrame(rows)
    base = pd.concat([latlon_to_km(frame["lat"], frame["lon"]), frame[["climate"]]], axis=1)
    return frame, base


def test_deterministic():
    frame, base = _grid_frame()
    frame.loc[[3, 10, 22], "pH"] = np.nan
    targets = ["pH", "organic_matter"]
    first, r1 = impute(frame.copy(), targets, base, frame["name"])
    second, r2 = impute(frame.copy(), targets, base, frame["name"])
    pd.testing.assert_frame_equal(first, second)
    assert r1["k_used"] == r2["k_used"]
    assert r1["k_selection"]["normalized_mae"] == r2["k_selection"]["normalized_mae"]


def test_uses_neighbors_not_global_mean():
    """결측을 전역 평균이 아니라 이웃 값 근처로 채워야 한다."""
    frame, base = _grid_frame()
    truth = frame.loc[5, "pH"]
    frame.loc[5, "pH"] = np.nan
    filled, _ = impute(frame, ["pH", "organic_matter"], base, frame["name"], k=5)
    predicted = filled.loc[5, "pH"]
    global_mean = frame["pH"].mean()
    assert abs(predicted - truth) < abs(global_mean - truth), (
        f"이웃 대체가 전역평균보다 나쁘다: 예측 {predicted}, 실제 {truth}, 전역평균 {global_mean}"
    )
    assert filled.loc[5, "pH__impute_method"].startswith("knn_k")
    assert filled.loc[5, "pH__impute_source"], "대체 출처(빌린 지역·거리)가 비어 있다"


def test_multivariate_option_uses_other_variables():
    """`use_others=True`가 다른 변수와의 상관을 실제로 반영한다.

    한 행의 pH를 이웃과 동떨어지게 만들고 organic_matter만 가린다.
    organic_matter = f(pH)이므로 pH를 거리에 넣으면 넣지 않은 경우보다 실제값에 가까워야
    한다. **공간 이웃보다 항상 낫다고 주장하지 않는다** — 예측인자가 늘면 공간이 희석되므로
    어느 쪽이 나은지는 데이터마다 다르고, 그래서 select_k가 측정해서 고른다.
    """
    frame, base = _grid_frame()
    frame.loc[7, "pH"] = 9.9
    truth = 10.0 + 4.0 * 9.9
    frame.loc[7, "organic_matter"] = np.nan
    kwargs = dict(k=3, detect_outliers=False)
    with_others, _ = impute(
        frame.copy(), ["pH", "organic_matter"], base, frame["name"], use_others=True, **kwargs
    )
    without, _ = impute(
        frame.copy(), ["pH", "organic_matter"], base, frame["name"], use_others=False, **kwargs
    )
    err_with = abs(with_others.loc[7, "organic_matter"] - truth)
    err_without = abs(without.loc[7, "organic_matter"] - truth)
    assert err_with < err_without, (
        f"타변수 상관이 반영되지 않았다: 다변량 오차 {err_with:.2f} >= 공간전용 {err_without:.2f}"
    )


def test_fallbacks_do_not_raise():
    """컬럼 전체 결측·예측인자 전무에도 예외로 죽지 않는다(§18-5)."""
    frame, base = _grid_frame(3)
    frame["pH"] = np.nan  # 컬럼 전체 결측 → 대체 불가
    filled, report = impute(frame, ["pH", "organic_matter"], base, frame["name"], k=3)
    assert filled["pH"].isna().all(), "값이 없는데 만들어냈다"
    assert set(report["columns"]["pH"]["method_counts"]) == {"unfilled"}

    frame2, base2 = _grid_frame(3)
    frame2.loc[0, "organic_matter"] = np.nan
    base2.loc[0, :] = np.nan  # 이 행은 공간·기후 예측인자가 전무
    filled2, _ = impute(frame2, ["organic_matter"], base2, frame2["name"], k=3)
    assert pd.notna(filled2.loc[0, "organic_matter"]), "폴백이 값을 채우지 못했다"


def test_physical_range_violation_is_masked():
    frame, base = _grid_frame(4)
    frame.loc[2, "pH"] = 20.0  # 정의상 불가능(0~14)
    assert flag_physical_violations(frame, ["pH"]).loc[2, "pH"]
    filled, report = impute(frame, ["pH", "organic_matter"], base, frame["name"], k=3)
    assert report["columns"]["pH"]["physical_violation"] == 1
    assert filled.loc[2, "pH"] < 14.0, "물리범위 위반값이 그대로 남았다"


def test_outlier_flag_and_replace_switch():
    """이웃 대비 튀는 값을 잡되, 치환은 호출부가 고른다(원본은 항상 보존)."""
    frame, base = _grid_frame()
    frame.loc[9, "pH"] = 13.5  # 물리범위 안이지만 이웃 대비 극단
    original = frame.loc[9, "pH"]

    flagged_only, report = impute(
        frame.copy(), ["pH", "organic_matter"], base, frame["name"], k=5, replace_outliers=False
    )
    assert report["columns"]["pH"]["knn_outlier"] >= 1, "이웃 대비 극단값을 못 잡았다"
    assert flagged_only.loc[9, "pH"] == original, "치환하지 않기로 했는데 값이 바뀌었다"
    assert flagged_only.loc[9, "pH__outlier"], "이상치 플래그가 노출되지 않았다"
    assert report["outlier_replaced"] is False
    assert any(rec["original_value"] == original for rec in report["outliers"]), (
        "원본값이 리포트에 보존되지 않았다"
    )

    replaced, report2 = impute(
        frame.copy(), ["pH", "organic_matter"], base, frame["name"], k=5, replace_outliers=True
    )
    assert replaced.loc[9, "pH"] != original, "치환하기로 했는데 값이 그대로다"
    assert report2["outlier_replaced"] is True


def test_cv_reports_baselines():
    """k 선택 리포트에 종전 방식·전역평균 베이스라인이 함께 담긴다(개선 여부 검증 가능)."""
    frame, base = _grid_frame()
    rng = np.random.default_rng(0)
    frame.loc[rng.choice(len(frame), size=8, replace=False), "pH"] = np.nan
    report = select_k(frame, ["pH", "organic_matter"], base)
    mae = report["normalized_mae"]
    assert "global_mean" in mae and "legacy_neighbor_mean_k5" in mae
    assert any(n.startswith("knn_spatial_k") for n in mae)
    assert any(n.startswith("knn_multivar_k") for n in mae)
    assert report["chosen_k"] in (1, 3, 5, 7, 10, 15)
    assert isinstance(report["chosen_use_others"], bool)
    assert "확인 필요" in report["limitation"], "검증 한계 표기가 사라졌다"


def test_regional_score_exposes_provenance():
    """산출물 계약: 대체 방법·출처·이상치 컬럼이 CSV에 노출된다(§18-4)."""
    csv = ROOT / "RegionalScore.csv"
    if not csv.exists():
        return  # 아직 산출 전 — 로직 자체는 위 테스트들이 검증한다
    df = pd.read_csv(csv, dtype={"region_code": str})
    for col in ("pH", "organic_matter", "available_p", "k", "ca", "mg"):
        assert f"{col}_impute_method" in df.columns, f"{col}_impute_method 누락"
        assert f"{col}_impute_source" in df.columns, f"{col}_impute_source 누락"
        assert f"{col}_outlier" in df.columns, f"{col}_outlier 누락"
    methods = set(df["pH_impute_method"])
    allowed = {"measured", "column_mean", "unfilled"} | {f"knn_k{k}" for k in range(1, 16)}
    assert methods <= allowed, f"예상 밖 대체 방법 라벨: {methods - allowed}"
    borrowed = df[df["pH_impute_method"].str.startswith("knn_k")]
    assert borrowed["pH_impute_source"].str.len().gt(0).all(), "대체했는데 출처가 비었다"


def main():
    test_deterministic()
    test_uses_neighbors_not_global_mean()
    test_multivariate_option_uses_other_variables()
    test_fallbacks_do_not_raise()
    test_physical_range_violation_is_masked()
    test_outlier_flag_and_replace_switch()
    test_cv_reports_baselines()
    test_regional_score_exposes_provenance()
    print(f"ALL IMPUTATION TESTS PASSED (outlier z>{OUTLIER_MODIFIED_Z}).")


if __name__ == "__main__":
    main()
