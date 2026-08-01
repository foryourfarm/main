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
from app.services.climatology_service import _grid_distance_km  # noqa: E402

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


def predict_knn(
    target: int, donors: list[int], grids: dict, clim: dict, k: int
) -> dict[int, dict[str, float | None]]:
    """거리역수 가중 KNN. 동거리는 region_id 작은 쪽 — 결정론(CLAUDE.md §2)."""
    ranked = sorted(
        ((_grid_distance_km(grids[target], grids[d]), d) for d in donors if d in grids),
        key=lambda t: (t[0], t[1]),
    )[:k]
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


def evaluate(grids: dict, sido: dict, clim: dict) -> dict:
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

    methods = {"sido_mean": None, "nearest_1": 1}
    methods.update({f"knn_spatial_k{k}": k for k in K_VALUES})

    results: dict[str, dict] = {}
    for name, k in methods.items():
        # 필드별 오차 누적
        errors: dict[str, list[float]] = {f: [] for f in FIELDS}
        unpredicted: dict[str, int] = {f: 0 for f in FIELDS}

        for target in full:
            donors = [r for r in full if r != target]
            if name == "sido_mean":
                pred = predict_sido_mean(target, donors, sido, clim)
            else:
                pred = predict_knn(target, donors, grids, clim, k)

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

    report = evaluate(grids, sido, clim)

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
