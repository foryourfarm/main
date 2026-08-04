"""원시 피처 KNN 대체 + 이웃 기반 이상치 탐지 (2026-07-29 도입).

**무엇을 교체했나**: 종전 `build_regional_score.impute_score_column`은 (1) 이미 채점된
**점수**를 (2) 최근접 5개 지역 **단순평균**으로 채웠다. 두 지점 모두 편향이 있다.

  (1) 점수 공간 대체의 편향: `scoring.band_score`는 로그 감쇠 곡선이라 비선형이다.
      mean(score(v_i)) != score(mean(v_i)) — 예컨대 pH 4.5(0점)와 6.5(100점) 이웃의
      점수평균은 50점이지만, 값평균 5.5의 실제 점수는 그와 다르다. 원시값을 먼저 채우고
      채점하면 이 왜곡이 사라진다.
  (2) 단순평균의 편향: 3km 이웃과 80km 이웃을 같은 무게로 쓴다. 또 k=5가 근거 없이
      고정돼 있었고, 개선 여부를 측정한 적이 없다(종전 docstring이 스스로 `[확인 필요]`로
      기록). 여기서는 거리역수 가중 + 홀드아웃 CV로 k를 고르고 베이스라인과 비교한다.

**왜 KNN이 성립하나**: 결측이 무작위가 아니다(2026-07-29 측정, 선정 150지역).
  - pH·유기물·유효인산: 24개 지역이 **동시** 결측(그 지역 토양조사 자체가 없음).
    → 이 24행은 토양 예측인자가 0개이므로 공간(위경도)+기후 피처만으로 예측된다.
      사실상 공간 KNN이고, 정직하게 말하면 종전 방식의 정교한 버전이다.
  - K·Ca·Mg: 45/47/47 결측이지만 그중 23행은 pH·유기물·유효인산을 **보유**한다.
    → 여기서만 진짜 다변량 이득이 난다(토양 화학성 간 상관을 예측에 쓴다).
  - 기온 앵커월 평균기온: 14개 지역 결측(해당 지역 기상 관측 자체가 없음).

**왜 sklearn KNNImputer를 안 쓰나**: 어느 지역 값을 몇 km에서 빌렸는지 되돌려주지
않는다. 이 프로젝트는 대체 출처를 UI에 병기할 의무가 있다(CLAUDE.md §18-4). 거리 계산
(`nan_euclidean_distances`)과 스케일링만 sklearn을 쓰고 가중평균·이웃 추적은 직접 한다.

**이상치**: row 단위 LocalOutlierFactor는 쓰지 않는다 — 한 행을 이상으로 판정하면 그
행의 유효 측정값 6개가 전부 결측이 되어 정보 손실이 크다. 대신 **변수 단위**로,
이웃 예측치 대비 robust 잔차(Iglewicz-Hoaglin modified z)가 임계를 넘는 값만 결측
처리하고 KNN으로 재대체한다. 판정된 원본값은 지우지 않고 호출부가
`data/ml/imputation_outliers.csv`로 보존한다 — "진짜 특이 토양"일 가능성을 남긴다.

**결정론**(CLAUDE.md §2): 랜덤 없음. 동거리 이웃은 행 인덱스(=region_code 정렬) 작은
쪽을 택하고, CV 마스킹은 seed 고정이다. 같은 입력 → 같은 출력.

**한계**: 결측 지역은 실측값이 없어 그 지역의 대체 오차를 직접 검증할 수 없다. CV는
"관측된 지역의 값을 가려 맞히는" 오차이므로, 결측이 무작위가 아닌 만큼(토양조사가 없는
지역은 접근성·경작규모가 다를 수 있음) 실제 오차는 CV보다 클 수 있다 — `[확인 필요]`.
"""
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import nan_euclidean_distances
from sklearn.preprocessing import StandardScaler

EPS = 1e-6  # 거리 0(동일 좌표) 이웃의 가중치 발산 방지
EARTH_R_KM = 6371.0

# 물리적으로 불가능한 값의 범위. 농업 **기준값**이 아니라 물리 한계이므로 코드 상수로
# 둔다(§18-2가 금지하는 건 생육 기준값·가중치의 하드코딩이다).
# pH는 정의상 0~14, 농도·함량은 음수 불가. 상한은 두지 않는다 — 상한을 두면 그게 곧
# 농업 기준 판단이 되고, 실제 고농도 토양을 임의로 잘라낼 위험이 있다.
PHYSICAL_RANGE = {
    "pH": (0.0, 14.0),
    "organic_matter": (0.0, None),
    "available_p": (0.0, None),
    "k": (0.0, None),
    "ca": (0.0, None),
    "mg": (0.0, None),
    "ec": (0.0, None),
}

# 이웃 대비 robust 잔차 임계. Iglewicz-Hoaglin(1993)의 modified z-score 관례값 3.5.
# 통계 관례값이고 작물 기준이 아니다.
OUTLIER_MODIFIED_Z = 3.5
MAD_TO_SIGMA = 0.6745  # modified z 정의상의 상수

K_GRID = (1, 3, 5, 7, 10, 15)
CV_MASK_FRACTION = 0.2
CV_SEED = 42


def latlon_to_km(lat: pd.Series, lon: pd.Series) -> pd.DataFrame:
    """위경도 → 등거리 근사 평면좌표(km). 한국 정도의 남북 폭에서는 정거원통 근사로 충분.

    거리 계산에 위경도(도 단위)를 그대로 쓰면 경도 1도가 위도 1도보다 짧은 걸 무시해
    동서 거리를 과대평가한다. 평균 위도에서 cos 보정한 평면으로 옮겨 x·y를 같은 km
    단위로 만든다.
    """
    lat0 = np.radians(float(lat.mean()))
    return pd.DataFrame(
        {
            "x_km": np.radians(lon.to_numpy(dtype=float)) * EARTH_R_KM * np.cos(lat0),
            "y_km": np.radians(lat.to_numpy(dtype=float)) * EARTH_R_KM,
        },
        index=lat.index,
    )


def _distance_matrix(features: pd.DataFrame) -> np.ndarray:
    """표준화 후 nan-aware 유클리드 거리. 결측 피처는 관측 피처 수로 보정된다.

    `nan_euclidean_distances`는 두 행이 함께 관측한 피처만으로 거리를 재고 전체 피처
    수로 스케일업한다 — 토양이 전부 결측인 24행도 (공간+기후) 피처만으로 거리가 나온다.
    StandardScaler는 결측을 무시하고 관측값 기준으로 평균·표준편차를 낸다.
    """
    scaled = StandardScaler().fit_transform(features.to_numpy(dtype=float))
    return nan_euclidean_distances(scaled)


def _predictor_matrix(
    frame: pd.DataFrame,
    targets: list[str],
    base: pd.DataFrame,
    exclude: str,
    use_others: bool = True,
) -> pd.DataFrame:
    """대상 컬럼 `exclude`의 예측인자 행렬.

    자기 자신은 항상 제외한다 — 넣으면 거리가 그 값에 지배돼 "자기와 비슷한 값을 가진
    이웃"을 찾는 순환이 된다.

    `use_others`가 나머지 대상 변수를 예측인자로 쓸지 결정한다. 쓰면 토양 화학성 간
    상관을 활용할 수 있지만(K·Ca·Mg 결측 47개 중 23개는 pH·유기물·유효인산 보유),
    피처 수가 늘어 공간·기후가 거리에서 희석되는 부작용도 있다. 어느 쪽이 나은지는
    가정하지 않고 `select_k`가 홀드아웃 MAE로 고른다.
    """
    if not use_others:
        return base.copy()
    others = [c for c in targets if c != exclude]
    return pd.concat([base, frame[others]], axis=1)


def _knn_predict(
    values: pd.Series, dist: np.ndarray, k: int, rows: np.ndarray
) -> tuple[dict[int, float], dict[int, list[tuple[int, float]]]]:
    """`rows`(행 위치)에 대해 거리역수 가중 KNN 예측. 자기 자신은 이웃에서 제외한다.

    반환: ({행위치: 예측값}, {행위치: [(이웃 행위치, 거리), ...]}).
    이웃이 없으면(해당 컬럼 관측 행이 없거나 거리가 전부 NaN) 키를 만들지 않는다 —
    호출부가 폴백(컬럼 평균)으로 내려간다.
    """
    observed = np.flatnonzero(values.notna().to_numpy())
    obs_values = values.to_numpy(dtype=float)
    preds: dict[int, float] = {}
    prov: dict[int, list[tuple[int, float]]] = {}

    for i in rows:
        candidates = observed[observed != int(i)]
        if candidates.size == 0:
            continue
        d = dist[int(i), candidates]
        usable = np.isfinite(d)
        if not usable.any():
            continue
        candidates, d = candidates[usable], d[usable]
        # 동거리는 행 위치(=region_code 정렬) 작은 쪽 — 결정론 보장.
        order = np.lexsort((candidates, d))[:k]
        nb, nd = candidates[order], d[order]
        w = 1.0 / np.maximum(nd, EPS)
        preds[int(i)] = float(np.average(obs_values[nb], weights=w))
        prov[int(i)] = [(int(j), float(round(dd, 4))) for j, dd in zip(nb, nd)]
    return preds, prov


def flag_physical_violations(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """물리 범위 밖 값의 불리언 마스크. 범위 정의가 없는 컬럼은 전부 False."""
    mask = pd.DataFrame(False, index=frame.index, columns=columns)
    for col in columns:
        lo, hi = PHYSICAL_RANGE.get(col, (None, None))
        series = frame[col]
        bad = pd.Series(False, index=frame.index)
        if lo is not None:
            bad |= series < lo
        if hi is not None:
            bad |= series > hi
        mask[col] = bad.fillna(False)
    return mask


def flag_knn_outliers(
    frame: pd.DataFrame,
    columns: list[str],
    base: pd.DataFrame,
    k: int,
    use_others: bool = True,
) -> pd.DataFrame:
    """변수 단위 이웃 대비 이상치 마스크(leave-one-out KNN 잔차의 modified z > 임계).

    row 단위 LOF를 쓰지 않는 이유는 모듈 docstring 참조. 잔차 척도는 표준편차가 아니라
    MAD를 쓴다 — 이상치 자신이 척도를 부풀려 스스로를 정상으로 만드는 걸 막는다.
    """
    mask = pd.DataFrame(False, index=frame.index, columns=columns)
    for col in columns:
        observed = np.flatnonzero(frame[col].notna().to_numpy())
        if observed.size < 3:  # 이웃 잔차 척도를 낼 표본 부족
            continue
        dist = _distance_matrix(
            _predictor_matrix(frame, columns, base, exclude=col, use_others=use_others)
        )
        preds, _ = _knn_predict(frame[col], dist, k, observed)
        if not preds:
            continue
        pos = np.array(sorted(preds))
        resid = frame[col].to_numpy(dtype=float)[pos] - np.array([preds[p] for p in pos])
        center = float(np.median(resid))
        mad = float(np.median(np.abs(resid - center)))
        if mad <= 0:  # 잔차가 사실상 상수 — 판정 불가, 조용히 넘어간다
            continue
        z = MAD_TO_SIGMA * (resid - center) / mad
        flagged = pos[np.abs(z) > OUTLIER_MODIFIED_Z]
        if flagged.size:
            mask.iloc[flagged, mask.columns.get_loc(col)] = True
    return mask


def _fill_column(
    frame: pd.DataFrame,
    col: str,
    targets: list[str],
    base: pd.DataFrame,
    labels: pd.Series,
    k: int,
    use_others: bool,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """한 컬럼의 결측을 KNN → 컬럼평균 순으로 채운다.

    반환: (채운 값, 방법 라벨, 이웃 출처 문자열). 방법 라벨은
    measured / knn_k{n} / column_mean / unfilled.
    """
    series = frame[col]
    filled = series.copy()
    method = pd.Series("measured", index=series.index, dtype=object)
    source = pd.Series("", index=series.index, dtype=object)
    missing = np.flatnonzero(series.isna().to_numpy())
    if missing.size == 0:
        return filled, method, source

    dist = _distance_matrix(
        _predictor_matrix(frame, targets, base, exclude=col, use_others=use_others)
    )
    preds, prov = _knn_predict(series, dist, k, missing)
    column_mean = series.mean()

    for i in missing:
        pos = int(i)
        if pos in preds:
            filled.iloc[pos] = preds[pos]
            method.iloc[pos] = f"knn_k{len(prov[pos])}"
            source.iloc[pos] = "; ".join(
                f"{labels.iloc[j]}(d={d:.2f})" for j, d in prov[pos]
            )
        elif pd.notna(column_mean):
            filled.iloc[pos] = float(column_mean)
            method.iloc[pos] = "column_mean"
        else:
            method.iloc[pos] = "unfilled"  # 컬럼 전체 결측 — 채점 단계 폴백으로 넘긴다
    return filled, method, source


SPATIAL_COLS = ("x_km", "y_km")


def _candidate_predictors(k_grid):
    """CV 후보들: (이름, 예측함수). 예측함수는 가려진 행 위치의 값 배열을 돌려준다.

    후보 구성:
      - global_mean: 컬럼 평균(종전 2순위 폴백)
      - legacy_neighbor_mean_k5: 위경도 최근접 5개 **단순평균**. 종전 1순위를 그대로
        재현한다 — 종전 코드는 기후·타변수를 쓰지 않고 haversine 거리만 썼다.
      - knn_spatial_k{k}: 거리역수 가중, 예측인자 = 공간+기후(base)만
      - knn_multivar_k{k}: 거리역수 가중, 예측인자 = base + 나머지 대상 변수
    """

    def global_mean(masked, col, targets, base, held):
        m = masked[col].mean()
        return None if pd.isna(m) else np.full(len(held), float(m))

    def legacy_neighbor_mean_k5(masked, col, targets, base, held):
        spatial = [c for c in SPATIAL_COLS if c in base.columns]
        if not spatial:
            return None
        dist = _distance_matrix(base[spatial])
        observed = np.flatnonzero(masked[col].notna().to_numpy())
        values = masked[col].to_numpy(dtype=float)
        out = []
        for i in held:
            cand = observed[observed != int(i)]
            d = dist[int(i), cand]
            ok = np.isfinite(d)
            if not ok.any():
                return None
            cand, d = cand[ok], d[ok]
            nb = cand[np.lexsort((cand, d))[:5]]
            out.append(float(np.mean(values[nb])))  # 단순평균 — 종전 방식
        return np.array(out)

    def make_knn(k, use_others):
        def predict(masked, col, targets, base, held):
            dist = _distance_matrix(
                _predictor_matrix(masked, targets, base, exclude=col, use_others=use_others)
            )
            preds, _ = _knn_predict(masked[col], dist, k, held)
            if len(preds) != len(held):
                return None
            return np.array([preds[int(i)] for i in held])

        return predict

    return [
        ("global_mean", global_mean),
        ("legacy_neighbor_mean_k5", legacy_neighbor_mean_k5),
        *[(f"knn_spatial_k{k}", make_knn(k, False)) for k in k_grid],
        *[(f"knn_multivar_k{k}", make_knn(k, True)) for k in k_grid],
    ]


def select_k(
    frame: pd.DataFrame, targets: list[str], base: pd.DataFrame, k_grid=K_GRID
) -> dict:
    """관측값을 가려 맞히는 홀드아웃으로 (k, 예측인자 구성)을 고른다.

    후보와 베이스라인은 `_candidate_predictors` 참조. 다변량 예측인자가 실제로 도움이
    되는지도 **가정하지 않고 여기서 측정해 고른다** — 피처가 늘면 공간·기후가 거리에서
    희석되므로 늘 이득이라는 보장이 없다.

    오차는 컬럼 표준편차로 나눈 정규화 MAE로 합산한다 — 유효인산(mg/kg)이 pH를 압도하는
    걸 막는다. 마스킹은 seed 고정 셔플의 앞 20%로 결정적이다.
    """
    rng = np.random.default_rng(CV_SEED)
    folds: dict[str, np.ndarray] = {}
    for col in targets:
        observed = np.flatnonzero(frame[col].notna().to_numpy())
        if observed.size < 10:
            continue
        shuffled = observed.copy()
        rng.shuffle(shuffled)
        folds[col] = np.sort(shuffled[: max(1, int(len(shuffled) * CV_MASK_FRACTION))])
    if not folds:
        return {
            "chosen_k": k_grid[0],
            "chosen_use_others": True,
            "chosen_by": "검증 표본 부족 — 그리드 최소값·다변량 기본값 사용",
        }

    normalized: dict[str, float] = {}
    per_column: dict[str, dict[str, float]] = {}
    for name, predictor in _candidate_predictors(k_grid):
        norm_maes, col_maes = [], {}
        for col, held in folds.items():
            masked = frame.copy()
            truth = masked[col].to_numpy(dtype=float)[held].copy()
            masked.loc[masked.index[held], col] = np.nan
            preds = predictor(masked, col, targets, base, held)
            if preds is None:
                continue
            mae = float(np.mean(np.abs(preds - truth)))
            sd = float(frame[col].std())
            col_maes[col] = round(mae, 4)
            norm_maes.append(mae / sd if sd > 0 else mae)
        if norm_maes:
            normalized[name] = round(float(np.mean(norm_maes)), 4)
            per_column[name] = col_maes

    knn = {n: v for n, v in normalized.items() if n.startswith("knn_")}
    chosen_name = min(knn, key=knn.get) if knn else f"knn_multivar_k{k_grid[0]}"
    return {
        "chosen_k": int(chosen_name.rsplit("_k", 1)[1]),
        "chosen_use_others": chosen_name.startswith("knn_multivar"),
        "chosen_candidate": chosen_name,
        "chosen_by": "정규화 MAE 최소(홀드아웃 20%, seed 42)",
        "normalized_mae": normalized,
        "mae_per_column": per_column,
        "held_out_counts": {c: int(len(h)) for c, h in folds.items()},
        "limitation": "결측 지역 자체의 오차는 실측이 없어 검증 불가 — 이 수치는 관측 지역 "
                      "기준이며, 결측이 무작위가 아닌 만큼 낙관적일 수 있다 [확인 필요]",
    }


def impute(
    frame: pd.DataFrame,
    targets: list[str],
    base: pd.DataFrame,
    labels: pd.Series,
    k: int | None = None,
    use_others: bool = True,
    detect_outliers: bool = True,
    replace_outliers: bool = True,
    fill: bool = True,
) -> tuple[pd.DataFrame, dict]:
    """원시 피처 결측·이상치를 KNN으로 채운다(`fill=False`면 탐지만 하고 채우지 않는다).

    Args:
        frame: 대상 컬럼(`targets`)을 담은 원시값 프레임.
        targets: 대체할 원시 변수 컬럼명들.
        base: 공간·기후 등 항상 예측인자로 쓰는 피처(행 정렬 동일).
        labels: 행별 표시용 이름(지역명) — 대체 출처 문자열에 쓴다.
        k: None이면 홀드아웃 CV로 고른다(예측인자 구성도 함께 고른다).
        use_others: 나머지 대상 변수를 예측인자로 쓸지. `k`를 지정한 경우에만 쓰인다 —
            k=None이면 CV가 이 값도 고른다.
        detect_outliers: 이웃 대비 이상치를 탐지해 플래그할지.
        replace_outliers: 탐지된 이상치를 결측 처리해 재대체할지. False면 플래그만 남기고
            값은 그대로 쓴다. 탐지된 값이 "데이터 오류"인지 "진짜 극단값"인지는 데이터마다
            다르다 — 판단은 호출부가 근거를 남기고 결정한다.
        fill: 결측을 실제로 채울지. **False면 결측을 그대로 두고 탐지·플래그만 한다** —
            이상치 탐지(이웃 대비 잔차)는 대체와 별개의 기능이라 하나를 끄려고 다른 하나를
            버릴 필요가 없다. `{col}__impute_method`는 `measured` 또는 `missing`이 된다.
            🔴 토양 데이터가 이 경로를 쓴다(2026-08-05 사용자 확정): 토양은 '리' 단위라
            KNN으로 이웃에서 빌려올 수 있는 값이 아니고, 결측 지표는 채우는 대신 채점에서
            제외하고 UI에 명시한다. KNN 대체는 기상 데이터에만 적용한다.

    Returns:
        (대체 후 프레임, 리포트 dict). 프레임에는 컬럼별 `{col}__impute_method`,
        `{col}__impute_source`가 추가된다. 리포트에는 k 선택 근거·베이스라인 비교·
        컬럼별 대체 방법 집계·이상치 목록이 담긴다(호출부가 매니페스트/CSV로 남긴다).
    """
    frame = frame.reset_index(drop=True).copy()
    base = base.reset_index(drop=True)
    labels = labels.reset_index(drop=True)

    original_missing = frame[targets].isna()
    physical = flag_physical_violations(frame, targets)
    frame[targets] = frame[targets].mask(physical)

    cv = (
        select_k(frame, targets, base)
        if k is None
        else {"chosen_k": k, "chosen_use_others": use_others, "chosen_by": "호출부 지정"}
    )
    k_used = int(cv["chosen_k"])
    others_used = bool(cv["chosen_use_others"])

    outliers = pd.DataFrame(False, index=frame.index, columns=targets)
    outlier_records: list[dict] = []
    if detect_outliers:
        outliers = flag_knn_outliers(frame, targets, base, k_used, use_others=others_used)
        for col in targets:
            for pos in np.flatnonzero(outliers[col].to_numpy()):
                outlier_records.append(
                    {
                        "row": int(pos),
                        "label": labels.iloc[int(pos)],
                        "variable": col,
                        "original_value": float(frame[col].iloc[int(pos)]),
                        "detector": f"knn_residual_modified_z>{OUTLIER_MODIFIED_Z}",
                        "replaced": bool(replace_outliers),
                    }
                )
        if replace_outliers:
            frame[targets] = frame[targets].mask(outliers)

    report_cols = {}
    for col in targets:
        # 플래그는 치환 여부와 무관하게 항상 노출한다 — 근사·특이값 표기 의무(§18-4).
        frame[f"{col}__outlier"] = outliers[col]
        if fill:
            filled, method, source = _fill_column(
                frame, col, targets, base, labels, k_used, others_used
            )
            frame[col] = filled
        else:
            # 값은 건드리지 않는다. 결측은 결측으로 남고 채점에서 제외된다.
            method = frame[col].notna().map({True: "measured", False: "missing"})
            source = pd.Series("", index=frame.index)
        frame[f"{col}__impute_method"] = method
        frame[f"{col}__impute_source"] = source
        report_cols[col] = {
            "original_missing": int(original_missing[col].sum()),
            "physical_violation": int(physical[col].sum()),
            "knn_outlier": int(outliers[col].sum()),
            "method_counts": method.value_counts().to_dict(),
        }

    return frame, {
        "k_selection": cv,
        "k_used": k_used,
        "other_variables_as_predictors": others_used,
        "predictor_base": list(base.columns),
        "targets": targets,
        "outlier_rule": f"이웃 대비 KNN 잔차 modified z > {OUTLIER_MODIFIED_Z}. row 단위 LOF 미사용 "
                        "— 한 행을 판정하면 그 행의 유효 측정값이 함께 버려진다. 원본값은 보존한다.",
        "outlier_replaced": bool(detect_outliers and replace_outliers),
        "filled": bool(fill),
        "physical_range": {name: list(rng_) for name, rng_ in PHYSICAL_RANGE.items()},
        "columns": report_cols,
        "outliers": outlier_records,
    }


__all__ = [
    "impute",
    "select_k",
    "latlon_to_km",
    "flag_knn_outliers",
    "flag_physical_violations",
    "PHYSICAL_RANGE",
    "OUTLIER_MODIFIED_Z",
]
