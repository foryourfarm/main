"""AWS 관측망 평년치 적재 ETL (오프라인·재실행 가능, 앱 밖).

**왜 필요한가**: 지금 평년치는 농업기상 116개 구역만 있고 나머지 140개는 KNN으로 남의 동네
값을 빌려 쓴다(최근접 도너가 최대 138.7km인 곳도 있다). 게다가 `temp_night_min_normal`은
**전 행 NULL**이라 장기 탭이 야간 저온을 아예 채점하지 못한다 — 문제정의서가 지목한 A씨
실패 원인이 그 지표인데도 그렇다. AWS 관측망(534지점)이 둘 다 고친다.

**적재 우선순위** (2026-08-01 확정):
    1순위  농업기상 실측     — 일사량·일조가 여기에만 있어 대체 불가. **덮어쓰지 않는다.**
    2순위  AWS 실측         — 이 스크립트. 농업기상이 없는 구역만 채운다.
    3순위  지역간 KNN 대체   — 그래도 빈 곳(`climatology_service`가 read-time에 처리)

**지점 → 구역 방식**: 최근접 1개가 아니라 **k개 거리역수 가중평균**이다. 근거는 실측이다 —
지점 쌍 비교에서 0~2km 떨어진 지점끼리도 일평균이 MAE 0.912℃ 벌어진다. 즉 오차의 대부분은
거리가 아니라 지점 고유 특성(설치 환경·미기후)이고, 그래서 하나만 쓰면 그 잡음을 그대로
받는다. 지역간 KNN 검증에서도 같은 결론이 나왔다(nearest_1 MAE 0.961 → k=10 0.739).

**단위 주의**: 기온은 월평균, 강수는 **월합계**다(기존 적재값과 맞춘다 — 7월 약 303mm).
연도별로 월합계를 낸 뒤 연도끼리 평균한다. 순서를 바꾸면(전체 일수 평균) 값이 달라진다.

실행:
    backend/.venv/Scripts/python.exe scripts/load_aws_climatology.py            # 적재
    backend/.venv/Scripts/python.exe scripts/load_aws_climatology.py --dry-run  # 집계만
API 응답은 `data/aws_daily_cache/`에 캐시하므로 재실행 시 다시 받지 않는다(§18-1).
"""

import argparse
import json
import statistics
import sys
from calendar import monthrange
from collections import defaultdict
from decimal import Decimal
from math import cos, radians
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.infra.public_api.aws_daily_client import (  # noqa: E402
    OBS_RAIN,
    OBS_TEMP_MAX,
    OBS_TEMP_MIN,
    fetch_daily,
)
from app.db.session import SessionLocal  # noqa: E402
from app.models import Region, RegionGrid, WeatherClimatology  # noqa: E402

CACHE_DIR = ROOT / "data" / "aws_daily_cache"
CALIBRATION = ROOT / "docs" / "seed" / "aws_temp_calibration.json"

# 기존 농업기상 적재와 같은 기간을 쓴다 — 두 관측망 값이 다른 시기를 대표하면 섞을 수 없다.
YEARS = range(2021, 2026)
SOURCE = "aws_mean_2021_2025"

# 구역당 섞을 지점 수와 거리 상한. 상한 10km 근거: 지점쌍 실측에서 10km 이내 MAE 1.132℃,
# 20km 넘어가면 2.05℃로 튄다. 상한 밖 구역은 적재하지 않고 지역간 KNN에 맡긴다.
STATION_K = 5
MAX_DISTANCE_KM = 10.0
MIN_DISTANCE_KM = 0.001  # 거리역수 가중의 0 나눗셈 방지

# **고도 필터** — 거리만으로 도너를 뽑으면 안 된다. 기온은 고도에 직접 지배되기 때문이다
# (환경감률 약 0.65℃/100m). 실측(10km 이내 지점쌍, 7월 일최고기온):
#     고도차 0~50m   MAE 0.98℃      200~500m  MAE 2.29℃
#     고도차 50~100m MAE 1.07℃      500m+     MAE 5.07℃
# 거리를 좁혀도 이건 안 잡힌다. 실제로 적재 대상 139개 중 19개가 도너 고도 산포 200m를
# 넘었고 서귀포시는 1,524m였다(한라산 지점과 해안 지점이 같은 후보에 든다). 그대로 두면
# 그 구역 평년치가 3℃ 넘게 틀린다.
#
# 기준은 **구역 대표 고도**(`region.altitude_m`)다. 종전엔 최근접 지점의 고도를 대표로
# 삼았는데 그건 근사였다 — 최근접 지점이 산 중턱이면 필터가 거꾸로 저지대 도너를 걸러낸다.
# 100m 허용폭은 위 실측에서 0~100m 구간 MAE(0.98~1.07℃)가 지점 고유 잡음과 구분되지
# 않는다는 근거에서 왔다. 그 안쪽 고도차는 추가 오차가 잡음에 묻힌다.
ALTITUDE_TOLERANCE_M = 100.0

# 한 달에 이만큼은 관측이 있어야 그 달 값을 인정한다. 며칠짜리로 월평균을 내지 않는다(§12).
MIN_DAYS_PER_MONTH = 20
# 한 지점이 이 연수 이상 있어야 평년치 표본으로 쓴다.
MIN_YEARS = 3

_KX, _KY = 111.32 * cos(radians(36.5)), 110.57  # 위도 36.5° 기준 1도당 km


def _bias() -> float:
    """(max+min)/2 → 일평균 보정값. 코드가 아니라 시드에서 읽는다(§18-2)."""
    data = json.loads(CALIBRATION.read_text(encoding="utf-8"))
    return float(data["daily_mean_from_extremes"]["bias"])


def station_altitudes() -> dict[str, float]:
    """지점 → 해발고도(m). 고도는 지점 속성이라 하루치 응답 한 번이면 전부 얻는다."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / "_station_altitude.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    rows = fetch_daily(OBS_TEMP_MAX, "20250701", "20250701")
    out = {r.point_code: r.altitude for r in rows if r.altitude is not None}
    path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def pick_donors(
    near: list[tuple[str, float]], altitudes: dict[str, float], base: float | None
) -> tuple[list[tuple[str, float]], float]:
    """거리로 고른 후보에서 고도가 동떨어진 지점을 걷어낸다. (남은 도너, 버려진 최대 고도차).

    `base`는 구역 대표 고도다. 없으면(고도 미적재 구역) 최근접 지점 고도로 폴백한다 —
    근사지만 필터를 통째로 끄는 것보다 낫다. 고도를 모르는 지점은 판정할 수 없으므로
    남긴다: 없는 정보로 지점을 버리면 그 구역이 통째로 비어버린다.

    필터가 도너를 다 걷어내면 필터를 포기한다 — 근사 평년치가 없는 것보다는 낫고,
    그 사실은 호출부가 로그로 드러낸다.
    """
    if not near:
        return [], 0.0
    if base is None:
        base = altitudes.get(near[0][0])
    if base is None:
        return near, 0.0

    kept, dropped = [], 0.0
    for stn, dist in near:
        height = altitudes.get(stn)
        if height is None or abs(height - base) <= ALTITUDE_TOLERANCE_M:
            kept.append((stn, dist))
        else:
            dropped = max(dropped, abs(height - base))
    return (kept or near), dropped


def reference_altitude(
    near: list[tuple[str, float]], altitudes: dict[str, float]
) -> int | None:
    """이 구역 평년치가 대표하는 고도 = 실제 섞인 도너 고도의 거리역수 가중평균.

    값을 만든 방식과 같은 가중을 써야 감률 보정의 기준선이 맞는다(§18-4).
    """
    pairs = [
        (altitudes[stn], 1.0 / max(dist, MIN_DISTANCE_KM))
        for stn, dist in near
        if stn in altitudes
    ]
    if not pairs:
        return None
    return round(sum(v * w for v, w in pairs) / sum(w for _, w in pairs))


def _fetch_month(obs: str, year: int, month: int) -> list:
    """전 지점 한 달. 응답을 캐시해 재실행 시 API를 다시 부르지 않는다."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{obs}_{year}{month:02d}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    # 2월을 29일로 고정하면 평년(2021·2022·2023·2025)에 없는 날짜를 요청해 응답이 빈다.
    # 실제 말일을 쓴다 — 이걸 틀려서 139개 구역이 전부 2월만 비었던 적이 있다.
    last = monthrange(year, month)[1]
    rows = fetch_daily(obs, f"{year}{month:02d}01", f"{year}{month:02d}{last}")
    payload = [
        {"stn": r.point_code, "date": r.obs_date, "v": r.value,
         "lat": r.lat, "lon": r.lon, "name": r.point_name}
        for r in rows
    ]
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


def collect_station_monthly(bias: float) -> tuple[dict, dict]:
    """(지점, 월) → {temp_avg, temp_night_min, rainfall} 평년값, 그리고 지점 좌표.

    연도별로 먼저 월값을 만든 뒤 연도끼리 평균한다 — 강수 월합계를 연도 구분 없이
    합치면 5년치 총합이 되어버린다.
    """
    # (stn, year, month) -> {"tmax": {date: v}, "tmin": {...}, "rain": {...}}
    daily: dict = defaultdict(lambda: defaultdict(dict))
    coords: dict[str, tuple[float, float]] = {}

    for year in YEARS:
        for month in range(1, 13):
            for obs, key in ((OBS_TEMP_MAX, "tmax"), (OBS_TEMP_MIN, "tmin"), (OBS_RAIN, "rain")):
                for row in _fetch_month(obs, year, month):
                    daily[(row["stn"], year, month)][key][row["date"]] = row["v"]
                    coords[row["stn"]] = (row["lat"], row["lon"])
            print(f"  수집 {year}-{month:02d} 완료", flush=True)

    # 연도별 월값
    per_year: dict = defaultdict(lambda: defaultdict(list))
    for (stn, _year, month), buckets in daily.items():
        tmax, tmin, rain = buckets["tmax"], buckets["tmin"], buckets["rain"]

        both = [d for d in tmax if d in tmin]  # 최고·최저가 다 있는 날만 평균을 낸다
        if len(both) >= MIN_DAYS_PER_MONTH:
            avgs = [(tmax[d] + tmin[d]) / 2 - bias for d in both]
            per_year[(stn, month)]["temp_avg"].append(statistics.mean(avgs))
            per_year[(stn, month)]["temp_night_min"].append(
                statistics.mean([tmin[d] for d in both])
            )
        if len(rain) >= MIN_DAYS_PER_MONTH:
            per_year[(stn, month)]["rainfall"].append(sum(rain.values()))  # 월합계

    monthly = {}
    for key, fields in per_year.items():
        out = {f: statistics.mean(v) for f, v in fields.items() if len(v) >= MIN_YEARS}
        if out:
            monthly[key] = out
    return monthly, coords


def _distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    return (((a[1] - b[1]) * _KX) ** 2 + ((a[0] - b[0]) * _KY) ** 2) ** 0.5


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="집계만 하고 DB에 쓰지 않는다")
    args = ap.parse_args()

    bias = _bias()
    print(f"보정값 {bias}℃ (docs/seed/aws_temp_calibration.json)")
    monthly, coords = collect_station_monthly(bias)
    print(f"지점 월평년: {len(monthly)}건 / 좌표 있는 지점 {len(coords)}개\n")

    db = SessionLocal()
    try:
        # 농업기상이 이미 있는 구역은 건드리지 않는다(1순위 보호).
        agri_regions = {
            r[0] for r in db.query(WeatherClimatology.region_id)
            .filter(WeatherClimatology.source != SOURCE).distinct()
        }
        grids = db.query(RegionGrid).all()
        from app.infra.public_api.kma_grid import grid_to_latlon

        altitudes = station_altitudes()
        region_altitude = {
            r.id: float(r.altitude_m)
            for r in db.query(Region).filter(Region.altitude_m.isnot(None))
        }
        rows_by_region: dict[int, dict[int, dict[str, float]]] = {}
        ref_altitude: dict[int, int | None] = {}
        skipped_far: list[int] = []
        altitude_filtered: list[tuple[int, float, int]] = []
        for grid in grids:
            if grid.region_id in agri_regions:
                continue
            here = grid_to_latlon(grid.nx, grid.ny)
            near = sorted(
                ((stn, _distance_km(here, xy)) for stn, xy in coords.items()),
                key=lambda t: t[1],
            )[:STATION_K]
            near = [(s, d) for s, d in near if d <= MAX_DISTANCE_KM]
            if not near:
                skipped_far.append(grid.region_id)
                continue

            near, dropped_m = pick_donors(
                near, altitudes, region_altitude.get(grid.region_id)
            )
            if dropped_m:
                altitude_filtered.append((grid.region_id, dropped_m, len(near)))
            ref_altitude[grid.region_id] = reference_altitude(near, altitudes)

            per_month: dict[int, dict[str, float]] = {}
            for month in range(1, 13):
                acc: dict[str, list[tuple[float, float]]] = defaultdict(list)
                for stn, dist in near:
                    vals = monthly.get((stn, month))
                    if not vals:
                        continue
                    w = 1.0 / max(dist, MIN_DISTANCE_KM)
                    for f, v in vals.items():
                        acc[f].append((v, w))
                merged = {
                    f: sum(v * w for v, w in pairs) / sum(w for _, w in pairs)
                    for f, pairs in acc.items()
                }
                if merged:
                    per_month[month] = merged
            if per_month:
                rows_by_region[grid.region_id] = per_month

        total_rows = sum(len(m) for m in rows_by_region.values())
        print(f"적재 대상 구역 {len(rows_by_region)}개 / {total_rows}행")
        print(f"  농업기상 보유라 건너뜀: {len(agri_regions)}개")
        print(f"  {MAX_DISTANCE_KM}km 안에 지점 없어 제외: {len(skipped_far)}개 → 지역간 KNN이 담당")
        if altitude_filtered:
            worst = sorted(altitude_filtered, key=lambda t: -t[1])[:5]
            print(f"  고도 필터로 도너 걷어낸 구역: {len(altitude_filtered)}개 "
                  f"(허용 ±{ALTITUDE_TOLERANCE_M:.0f}m)")
            for region_id, dropped, left in worst:
                print(f"     region {region_id}: 최대 {dropped:.0f}m 차이 제외, 남은 도너 {left}개")
        if args.dry_run:
            print("\n--dry-run: DB에 쓰지 않고 종료")
            return

        db.query(WeatherClimatology).filter(
            WeatherClimatology.source == SOURCE
        ).delete()  # 재실행 idempotent
        for region_id, per_month in rows_by_region.items():
            for month, v in per_month.items():
                db.add(
                    WeatherClimatology(
                        region_id=region_id,
                        month=month,
                        temp_avg_normal=_dec(v.get("temp_avg")),
                        temp_night_min_normal=_dec(v.get("temp_night_min")),
                        rainfall_normal=_dec(v.get("rainfall")),
                        sunlight_normal=None,  # AWS엔 일조 관측이 없다(농업기상 전용)
                        solar_radiation_normal=None,
                        reference_altitude_m=ref_altitude.get(region_id),
                        source=SOURCE,
                    )
                )
        db.commit()
        print(f"\n적재 완료: {total_rows}행 / 구역 {len(rows_by_region)}개 (source={SOURCE})")
    finally:
        db.close()


def _dec(value: float | None) -> Decimal | None:
    return None if value is None else Decimal(str(round(value, 1)))


if __name__ == "__main__":
    main()
