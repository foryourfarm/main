"""일사량 도너 선택 방식 검증 - leave-one-out (오프라인, API·DB 불필요).

**무엇을 정하려고 만들었나**: `load_solar_radiation_normal.py`가 구역에 일사량을 배정할 때
최근접 지점 1개를 쓰고 있었다. AWS 기온 ETL은 k개 거리가중 + 고도 필터를 쓰는데, 그 작업이
"최근접 1개는 지점 고유 잡음을 그대로 받는다"는 것을 기온에서 측정했다. 그러면 일사량도
바꿔야 하는가 — 그리고 고도 필터까지 같이 가져와야 하는가.

**추측하지 않고 쟀다.** 일사량 12개월 완비 지점 하나를 빼고 나머지로 그 지점 값을 예측해
실제와 비교한다. 구역 배정과 같은 연산(거리역수 가중)이라 배정 규칙의 우열이 그대로 드러난다.

**결과 (165지점 × 12개월, MAE MJ/m²/day)**

    k=1  1.2647    k=5  0.9758    k=10  0.9404    k=15  0.9299    k=30+  0.9260(평탄)

최근접 1개는 도달 가능한 최선보다 25.6% 나쁘다. k=10이 개선폭의 95.7%를 잡고 그 뒤는 회당
1% 미만이다. k=30 이후 값이 k=전체와 같은 것은 거리역수 가중이라 먼 도너 기여가 급감해
큰 k가 스스로 제한되기 때문이다.

고도 필터는 **역효과**다 — 모든 k에서 나빠졌다(k=10: 0.9404 → 0.9937 at ±100m). 고도가
일사량을 기온만큼 지배하지 않는다. 그래서 AWS 기온 ETL의 고도 필터를 여기로 가져오지 않았다.

거리 상한은 정확도가 아니라 **커버리지** 문제다. 40km부터 정확도가 평탄한데(하한 대비 0.9%)
10km로 좁히면 165지점 중 108개가 예측 불가가 된다. `station_service.MAX_DISTANCE_KM`(40km)를
그대로 쓴다.

> 상한을 비교할 때는 **상한마다 예측 가능한 지점 집합이 달라진다**는 함정이 있다. 좁은 상한은
> "가까운 이웃이 있는 지점"만 평가하게 되어 MAE가 되레 좋아 보인다(20km가 10km보다 나빠
> 보이는 역전이 실제로 나왔다). 그래서 모든 상한에서 예측 가능한 공통 집합으로 다시 잰다.

실행: backend/.venv/Scripts/python.exe scripts/validate_solar_donors.py
"""

import csv
import json
import statistics
import sys
from math import cos, radians
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "docs" / "seed" / "observation_point_seed.csv"
SOLAR = ROOT / "docs" / "seed" / "solar_radiation_station_monthly.json"

# 위도 36.5°(국토 중앙) 기준 1도당 km. 지점간 수십~수백 km라 이 근사로 충분하다.
_KX, _KY = 111.32 * cos(radians(36.5)), 110.57
MIN_DISTANCE_KM = 0.001  # 거리역수 가중의 0 나눗셈 방지
CAPS = (20.0, 30.0, 40.0, 60.0, 200.0)


def _distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    return (((a[0] - b[0]) * _KY) ** 2 + ((a[1] - b[1]) * _KX) ** 2) ** 0.5


def load_stations() -> tuple[dict[str, tuple[float, float]], dict[str, float]]:
    """농업기상 지점의 (위경도, 고도). 일사량은 이 관측망에만 있다."""
    coords: dict[str, tuple[float, float]] = {}
    altitudes: dict[str, float] = {}
    with SEED.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["network"] != "agri":
                continue
            try:
                coords[row["point_code"]] = (float(row["lat"]), float(row["lon"]))
                altitudes[row["point_code"]] = float(row["altitude"])
            except (ValueError, KeyError):
                continue  # 좌표·고도 결측 지점은 평가에서 제외
    return coords, altitudes


def load_solar() -> dict[str, dict[int, float]]:
    raw = json.loads(SOLAR.read_text(encoding="utf-8"))["monthly"]
    out: dict[str, dict[int, float]] = {}
    for key, value in raw.items():
        code, month = key.split("|")
        out.setdefault(code, {})[int(month)] = value
    return out


def predict(
    target: str,
    usable: list[str],
    coords: dict[str, tuple[float, float]],
    altitudes: dict[str, float],
    solar: dict[str, dict[int, float]],
    k: int,
    alt_tol: float | None,
    cap_km: float,
) -> dict[int, float] | None:
    """target을 뺀 나머지로 target의 12개월 값을 예측. 도너가 없으면 None."""
    near = sorted((_distance_km(coords[target], coords[o]), o) for o in usable if o != target)
    near = [(d, o) for d, o in near if d <= cap_km]
    if alt_tol is not None and target in altitudes:
        base = altitudes[target]
        kept = [(d, o) for d, o in near if abs(altitudes[o] - base) <= alt_tol]
        near = kept or near  # 다 걸러지면 필터를 포기한다(AWS ETL과 같은 규칙)
    near = near[:k]
    if not near:
        return None
    return {
        month: (
            sum(solar[o][month] / max(d, MIN_DISTANCE_KM) for d, o in near)
            / sum(1.0 / max(d, MIN_DISTANCE_KM) for d, o in near)
        )
        for month in range(1, 13)
    }


def mae(
    stations: list[str], usable: list[str], k: int, alt_tol: float | None, cap_km: float, **ctx
) -> tuple[float | None, int]:
    errors: list[float] = []
    unpredictable = 0
    for station in stations:
        got = predict(station, usable, k=k, alt_tol=alt_tol, cap_km=cap_km, **ctx)
        if got is None:
            unpredictable += 1
            continue
        errors.extend(abs(got[m] - ctx["solar"][station][m]) for m in range(1, 13))
    return (statistics.mean(errors) if errors else None), unpredictable


def main() -> None:
    coords, altitudes = load_stations()
    solar = load_solar()
    # 12개월 완비 + 좌표 보유 지점만. 예측 대상과 도너에 같은 조건을 적용해야 공정하다.
    usable = sorted(s for s, months in solar.items() if len(months) == 12 and s in coords)
    if len(usable) < 20:
        print(f"평가 가능한 지점이 {len(usable)}개뿐이다 - 시드를 확인할 것", file=sys.stderr)
        raise SystemExit(1)
    ctx = {"coords": coords, "altitudes": altitudes, "solar": solar, "usable": usable}
    print(f"평가 대상 지점 {len(usable)}개 (일사량 12개월 완비 + 좌표 보유)")

    nearest = sorted(
        min(_distance_km(coords[s], coords[o]) for o in usable if o != s) for s in usable
    )
    print(
        f"최근접 동종 지점 거리: 중앙값 {statistics.median(nearest):.1f}km / "
        f"p90 {nearest[int(len(nearest) * 0.9)]:.1f}km / 최대 {nearest[-1]:.1f}km"
    )

    print("\n[1] k와 고도 필터 (상한 60km) - MAE MJ/m2/day, 낮을수록 좋다")
    print(f"{'k':>4} {'무필터':>10} {'+-100m':>10} {'+-200m':>10}")
    for k in (1, 2, 3, 5, 10, 15, 30, len(usable) - 1):
        cells = []
        for tol in (None, 100.0, 200.0):
            value, _ = mae(usable, k=k, alt_tol=tol, cap_km=60.0, **ctx)
            cells.append(f"{value:10.4f}")
        print(f"{k:>4} " + " ".join(cells))
    print("  고도 필터가 모든 k에서 나쁘다 → 일사량에는 걸지 않는다")

    print("\n[2] 거리 상한 - 공통 평가 집합으로 고정 (k=10, 무필터)")
    common = [
        s
        for s in usable
        if all(predict(s, k=10, alt_tol=None, cap_km=c, **ctx) is not None for c in CAPS)
    ]
    print(f"  공통 집합 {len(common)}/{len(usable)}개 지점")
    for cap in CAPS:
        value, _ = mae(common, k=10, alt_tol=None, cap_km=cap, **ctx)
        print(f"  상한 {cap:5.0f}km  MAE {value:.4f}")

    print("\n[3] 상한별 예측불가 지점 수 (k=10) - 상한은 커버리지 문제다")
    for cap in (10.0, 20.0, 30.0, 40.0, 60.0, 200.0):
        _, missing = mae(usable, k=10, alt_tol=None, cap_km=cap, **ctx)
        print(f"  상한 {cap:5.0f}km  예측불가 {missing:>3}개 / {len(usable)}")

    _report_split(ctx, usable)


def _report_split(ctx: dict, usable: list[str]) -> None:
    """k를 train에서만 고르고 test에서만 보고한다 - 하이퍼파라미터 낙관편향 확인.

    **왜 필요한가**: 위 [1]~[3]은 LOOCV라 타깃 자기 값이 예측에 안 들어가므로 leakage는 없다.
    학습되는 파라미터도 없다(이웃 거리역수 가중평균은 fit이 아니다). 그런데 **k와 고도 허용폭을
    그 165개 지점의 LOOCV를 보고 골랐으므로** 보고값이 낙관적으로 편향될 수 있다. 그 크기를
    직접 재서 밝힌다.

    도너 풀은 양쪽 모두 "타깃 제외 전체"로 둔다 - 프로덕션에서 구역에 배정할 때 지점 전부가
    도너이므로 그게 실제 조건이다. 분할은 정렬 후 짝/홀로 결정론적으로 나눈다(재현 가능).
    """
    train = [s for i, s in enumerate(usable) if i % 2 == 0]
    test = [s for i, s in enumerate(usable) if i % 2 == 1]
    print(f"\n[4] train/test 분할 - train {len(train)} / test {len(test)}")

    best_k, best = None, float("inf")
    for k in (1, 2, 3, 5, 7, 10, 15, 20, 30):
        value, _ = mae(train, k=k, alt_tol=None, cap_km=60.0, **ctx)
        if value is not None and value < best:
            best, best_k = value, k
    print(f"  train이 고른 k = {best_k} (train MAE {best:.4f})")

    print("  k     전체 LOOCV     test만      차이")
    for k in (1, 5, 10, 15):
        full, _ = mae(usable, k=k, alt_tol=None, cap_km=60.0, **ctx)
        held, _ = mae(test, k=k, alt_tol=None, cap_km=60.0, **ctx)
        print(f"  {k:>3}     {full:.4f}       {held:.4f}     {(held - full) / full * 100:+.2f}%")

    print("  고도 필터 결론이 test에서도 유지되나 (k=10)")
    for tol, label in ((None, "무필터"), (100.0, "+-100m"), (200.0, "+-200m")):
        tr, _ = mae(train, k=10, alt_tol=tol, cap_km=60.0, **ctx)
        te, _ = mae(test, k=10, alt_tol=tol, cap_km=60.0, **ctx)
        print(f"    {label:>7}  train {tr:.4f}   test {te:.4f}")


if __name__ == "__main__":
    main()
