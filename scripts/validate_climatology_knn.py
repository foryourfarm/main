"""평년치 대체 방식 정확도 검증 — 현행(최근접 1개)을 바꿀 근거가 있는지 측정한다.

배경: `climatology_service.load_climatology`는 평년치가 없는 지역에 대해 격자상 **최근접
1개 지역의 12개월치를 통째로 복사**한다(k=1, 거리 무가중, 검증 없음).
`docs/ml/knn-imputation-backend-order.md` §3-3이 요구한 검증이며, **현행보다 나쁘면
교체하지 않는다** — 개선이 측정되지 않으면 바꿀 근거가 없다.

방법: 평년치를 12개월 전부 **보유한** 지역을 하나씩 홀드아웃(leave-one-out)해서, 나머지
지역만으로 그 지역 값을 예측하고 실측과 비교한다. 결측 지역 자체는 실측이 없어 직접
검증이 불가능하므로(`outcomes/scripts/ml/imputation.py` docstring의 한계와 동일),
"관측된 지역을 가려 맞히는" 오차로 대리 측정한다.

한계: 결측이 무작위가 아니다. 평년치가 없는 지역은 농업기상 관측지점이 없는 곳이라
산간·도서 비중이 다를 수 있고, 그만큼 실제 오차는 여기 수치보다 클 수 있다 [확인 필요].

거리는 `_grid_distance_km`을 그대로 import한다 — 런타임과 다른 공식을 쓰면 검증이
런타임을 대변하지 못한다.

사용법:
    python scripts/validate_climatology_knn.py

출력: docs/ml/climatology_knn_validation.json + stdout 비교표
"""

import csv
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

# Windows 기본 콘솔은 cp949라 한국어 표에 섞인 em-dash에서 UnicodeEncodeError로 죽는다.
sys.stdout.reconfigure(encoding="utf-8")

from app.db.session import SessionLocal  # noqa: E402
from app.models import Region, RegionGrid, WeatherClimatology  # noqa: E402
from app.services.climatology_service import KNN_K, _grid_distance_km  # noqa: E402

OUT_JSON = ROOT / "docs" / "ml" / "climatology_knn_validation.json"

# load_climatology가 대체 대상으로 삼는 수치 필드 전부(지시서 §3-2).
FIELDS = (
    "temp_avg_normal",
    "temp_night_min_normal",
    "rainfall_normal",
    "sunlight_normal",
    "solar_radiation_normal",
)
# 지시서는 k{1,3,5,7,10}을 요구했으나 10이 범위 끝단에서 최선으로 나와 범위를 넓혔다.
# k를 계속 키워도 좋아지면 "가까운 지역을 빌린다"가 아니라 전국 평균으로 회귀하는 것이므로
# 그 구분을 위해 전체 도너 수(115)까지 본다.
K_VALUES = (1, 3, 5, 7, 10, 15, 20, 30, 50, 115)
# 0으로 나누기 방지. 같은 격자칸(거리 0) 이웃이 있으면 그 이웃이 사실상 전부를 가져간다.
MIN_DISTANCE_KM = 0.001
MONTHS = range(1, 13)

REGION_ALTITUDE = ROOT / "docs" / "seed" / "region_altitude_seed.csv"

# 고도를 수평거리로 환산하는 계수(m/km). 지점쌍 실측에서 수평 10km ≈ MAE 1.13℃,
# 수직 100m ≈ MAE 1.0℃였으니 100m ≈ 10km, 즉 10 m/km가 물리 근거에서 나온 값이다.
# 그 주변을 함께 재서 실제로 최선인지 확인한다(계수를 눈대중으로 고정하지 않는다).
ALTITUDE_PENALTY_M_PER_KM = (5.0, 10.0, 20.0, 40.0)
# 고도차가 이보다 크면 도너에서 뺀다. 남는 도너가 이 수 밑으로 떨어지면 필터를 포기한다 —
# 없는 정보로 도너를 다 버리면 그 구역이 통째로 예측 불가가 된다.
ALTITUDE_FILTER_M = (100.0, 200.0, 400.0)
ALTITUDE_FILTER_K = (3, 5, 7, 10)
MIN_DONORS_AFTER_FILTER = 3


def _f(value: object) -> float | None:
    """Numeric → float. 0.0을 결측으로 보지 않도록 `is None`으로만 판정한다
    (climatology_service._as_float와 같은 이유 — 강원 산간 1월 평년기온 0.0℃)."""
    return None if value is None else float(value)


def load_data(db: object) -> tuple[dict, dict, dict]:
    """(region_id → 격자, region_id → sido, region_id → {month: {field: value}})"""
    grids = {g.region_id: g for g in db.query(RegionGrid)}
    sido = {r.id: r.sido for r in db.query(Region)}
    names = {r.id: r.name for r in db.query(Region)}

    clim: dict[int, dict[int, dict[str, float | None]]] = {}
    for row in db.query(WeatherClimatology):
        clim.setdefault(row.region_id, {})[row.month] = {
            f: _f(getattr(row, f)) for f in FIELDS
        }
    return grids, sido, clim, names


def weighted_mean(pairs: list[tuple[float, float]]) -> float | None:
    """[(값, 가중치)] → 가중평균. 가중치는 여기서 정규화한다.

    필드별로 독립 처리한다 — 어떤 도너가 그 필드만 결측이면 그 필드에서만 제외하고
    남은 도너로 재정규화한다. 도너 행 전체를 버리지 않는다(지시서 §3-2).
    """
    if not pairs:
        return None
    total = sum(w for _, w in pairs)
    if total <= 0:
        return None
    return sum(v * w for v, w in pairs) / total


def rank_donors(
    target: int,
    donors: list[int],
    grids: dict,
    k: int,
    altitudes: dict[int, float] | None = None,
    penalty_m_per_km: float | None = None,
    filter_m: float | None = None,
) -> list[tuple[float, int]]:
    """(가중용 거리, region_id) 상위 k개. 동거리는 region_id 작은 쪽 — 결정론(§2).

    고도 옵션이 없으면 종전과 완전히 같다(수평거리만). 옵션은 둘 중 하나다:
      - penalty_m_per_km: 고도차를 수평거리로 환산해 유클리드로 합친다(연속적).
      - filter_m: 고도차가 그 밖인 도너를 뺀다(이산적, AWS 적재 경로와 같은 방식).
    """
    my_alt = (altitudes or {}).get(target)
    pairs: list[tuple[float, int]] = []
    for d in donors:
        if d not in grids:
            continue
        dist = _grid_distance_km(grids[target], grids[d])
        d_alt = (altitudes or {}).get(d)
        # 고도를 모르는 쪽이 있으면 그 도너는 종전대로 수평거리만 본다 — 없는 정보로
        # 도너를 버리면 그 구역이 통째로 비어버린다.
        if my_alt is not None and d_alt is not None:
            gap = abs(my_alt - d_alt)
            if filter_m is not None and gap > filter_m:
                continue
            if penalty_m_per_km is not None:
                dist = (dist**2 + (gap / penalty_m_per_km) ** 2) ** 0.5
        pairs.append((dist, d))

    ranked = sorted(pairs, key=lambda t: (t[0], t[1]))[:k]
    if filter_m is not None and len(ranked) < MIN_DONORS_AFTER_FILTER:
        # 필터가 너무 많이 걷어냈다 — 근사가 없는 것보다는 낫다. 필터를 포기한다.
        return rank_donors(target, donors, grids, k)
    return ranked


def predict_knn(
    target: int,
    donors: list[int],
    grids: dict,
    clim: dict,
    k: int,
    altitudes: dict[int, float] | None = None,
    penalty_m_per_km: float | None = None,
    filter_m: float | None = None,
) -> dict[int, dict[str, float | None]]:
    """거리역수 가중 KNN. 고도 옵션은 도너 선택·가중에만 관여한다."""
    ranked = rank_donors(
        target, donors, grids, k, altitudes, penalty_m_per_km, filter_m
    )
    out = {}
    for month in MONTHS:
        out[month] = {}
        for field in FIELDS:
            pairs = [
                (clim[d][month][field], 1.0 / max(dist, MIN_DISTANCE_KM))
                for dist, d in ranked
                if month in clim[d] and clim[d][month][field] is not None
            ]
            out[month][field] = weighted_mean(pairs)
    return out


def predict_sido_mean(
    target: int, donors: list[int], sido: dict, clim: dict
) -> dict[int, dict[str, float | None]]:
    """같은 시/도 내 도너 단순평균. 같은 시/도에 도너가 없으면 전부 None(예측 불가)."""
    same = [d for d in donors if sido.get(d) == sido.get(target)]
    out = {}
    for month in MONTHS:
        out[month] = {}
        for field in FIELDS:
            values = [
                clim[d][month][field]
                for d in same
                if month in clim[d] and clim[d][month][field] is not None
            ]
            out[month][field] = statistics.fmean(values) if values else None
    return out


def load_region_altitudes() -> dict[int, float]:
    """구역 대표 고도(m). 없으면 빈 dict — 고도 방식만 조용히 빠지고 나머지는 그대로 돈다."""
    if not REGION_ALTITUDE.exists():
        return {}
    return {
        int(r["region_id"]): float(r["altitude_m"])
        for r in csv.DictReader(REGION_ALTITUDE.open(encoding="utf-8"))
    }


def evaluate(grids: dict, sido: dict, clim: dict, altitudes: dict[int, float]) -> dict:
    """12개월 완비 지역을 leave-one-out으로 돌려 방식별 오차를 낸다."""
    full = sorted(r for r, months in clim.items() if len(months) == 12 and r in grids)

    # 필드별 실측 표준편차 — 정규화 MAE의 분모. 단위가 다른 필드를 합산하려면 필요하다.
    observed = {
        f: [
            clim[r][m][f]
            for r in full
            for m in MONTHS
            if clim[r][m][f] is not None
        ]
        for f in FIELDS
    }
    field_sd = {
        f: (statistics.stdev(v) if len(v) > 1 else None) for f, v in observed.items()
    }
    scored_fields = [f for f in FIELDS if observed[f] and field_sd[f]]

    # (k, 고도옵션) — 고도옵션은 predict_knn kwargs. 현행 k와 비교 가능하도록 KNN_K에 맞춘다.
    methods: dict[str, tuple[int | None, dict]] = {"sido_mean": (None, {})}
    methods["nearest_1"] = (1, {})
    methods.update({f"knn_spatial_k{k}": (k, {}) for k in K_VALUES})
    if altitudes:
        for w in ALTITUDE_PENALTY_M_PER_KM:
            methods[f"knn_alt_penalty{w:g}"] = (
                KNN_K,
                {"altitudes": altitudes, "penalty_m_per_km": w},
            )
        # k와 고도 필터는 독립이 아니다 — 필터가 도너를 걷어내면 남는 수가 줄어 최적 k가
        # 달라진다. 둘을 따로 최적화하면 조합을 놓치므로 격자로 함께 훑는다.
        for k in ALTITUDE_FILTER_K:
            for t in ALTITUDE_FILTER_M:
                methods[f"knn_k{k}_alt{t:g}m"] = (
                    k,
                    {"altitudes": altitudes, "filter_m": t},
                )

    results: dict[str, dict] = {}
    for name, (k, options) in methods.items():
        # 필드별 오차 누적
        errors: dict[str, list[float]] = {f: [] for f in FIELDS}
        unpredicted: dict[str, int] = {f: 0 for f in FIELDS}

        for target in full:
            donors = [r for r in full if r != target]
            if name == "sido_mean":
                pred = predict_sido_mean(target, donors, sido, clim)
            else:
                pred = predict_knn(target, donors, grids, clim, k, **options)

            for month in MONTHS:
                for field in FIELDS:
                    truth = clim[target][month][field]
                    if truth is None:
                        continue  # 실측이 없으면 채점 대상이 아니다
                    guess = pred[month][field]
                    if guess is None:
                        unpredicted[field] += 1
                        continue
                    errors[field].append(guess - truth)

        per_field = {}
        for field in FIELDS:
            errs = errors[field]
            if not errs:
                per_field[field] = {
                    "n": 0,
                    "note": "실측 전무 — 채점 불가",
                    "unpredicted": unpredicted[field],
                }
                continue
            mae = statistics.fmean(abs(e) for e in errs)
            rmse = (statistics.fmean(e * e for e in errs)) ** 0.5
            per_field[field] = {
                "n": len(errs),
                "mae": round(mae, 4),
                "rmse": round(rmse, 4),
                "normalized_mae": round(mae / field_sd[field], 4),
                "unpredicted": unpredicted[field],
            }

        results[name] = {
            "per_field": per_field,
            "normalized_mae_mean": round(
                statistics.fmean(
                    per_field[f]["normalized_mae"] for f in scored_fields
                ),
                4,
            ),
        }

    return {
        "holdout_regions": len(full),
        "scored_fields": scored_fields,
        "skipped_fields": {
            f: "DB 전 행 NULL — 대체 대상이지만 검증할 실측이 없다"
            for f in FIELDS
            if f not in scored_fields
        },
        "field_sd": {f: round(sd, 4) for f, sd in field_sd.items() if sd},
        "methods": results,
    }


def main() -> None:
    db = SessionLocal()
    try:
        grids, sido, clim, names = load_data(db)
    finally:
        db.close()

    altitudes = load_region_altitudes()
    if not altitudes:
        print(f"[주의] {REGION_ALTITUDE.name}이 없어 고도 방식은 건너뛴다\n")
    report = evaluate(grids, sido, clim, altitudes)
    report["region_altitudes"] = len(altitudes)

    baseline = report["methods"]["nearest_1"]["normalized_mae_mean"]
    ranked = sorted(
        report["methods"].items(), key=lambda kv: kv[1]["normalized_mae_mean"]
    )
    report["baseline_nearest_1"] = baseline
    report["best"] = ranked[0][0]
    report["improvement_vs_nearest_1_pct"] = round(
        (baseline - ranked[0][1]["normalized_mae_mean"]) / baseline * 100, 2
    )

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"홀드아웃 지역: {report['holdout_regions']}개 (12개월 완비)")
    print(f"채점 필드: {', '.join(report['scored_fields'])}")
    for field, why in report["skipped_fields"].items():
        print(f"  제외 {field}: {why}")
    print()
    header = f"{'방식':<20} {'정규화MAE':>10} {'현행대비':>9}   필드별 MAE"
    print(header)
    print("-" * len(header) * 2)
    for name, res in ranked:
        norm = res["normalized_mae_mean"]
        delta = (baseline - norm) / baseline * 100
        detail = "  ".join(
            f"{f.replace('_normal', '')} {res['per_field'][f]['mae']}"
            for f in report["scored_fields"]
        )
        mark = " ←현행" if name == "nearest_1" else ""
        print(f"{name:<20} {norm:>10.4f} {delta:>+8.2f}%   {detail}{mark}")
    print()
    unpred = {
        n: sum(r["per_field"][f]["unpredicted"] for f in report["scored_fields"])
        for n, r in report["methods"].items()
    }
    for name, count in unpred.items():
        if count:
            print(f"주의 {name}: 예측 불가 {count}건 (도너 부재)")
    print(f"\n최선 {report['best']}, 현행 대비 {report['improvement_vs_nearest_1_pct']:+.2f}%")
    print(f"저장: {OUT_JSON.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
