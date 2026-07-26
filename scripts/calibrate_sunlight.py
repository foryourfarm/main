"""일조시간 환산 계수 보정·검증 (오프라인, 앱 밖).

농업기상 V3 실측(일사량 srqty + 일조시간 sun_Time)으로 역 Ångström–Prescott 계수를
회귀해 `docs/seed/sunlight_calibration.json`을 갱신하고, 홀드아웃 정확도를 재측정한다.
`backend/tests/fixtures/sunlight_validation.json`(테스트가 쓰는 검증 표본)도 함께 만든다.

**왜 스크립트로 두는가**: 계수는 마스터 데이터라 런타임에 만들지 않는다(CLAUDE.md §10).
API 호출량도 크다(월 1콜 × 4개월 = 전국 26,000행). 재보정이 필요할 때만 사람이 돌린다.

**홀짝 분할의 이유**: 계수를 맞춘 데이터로 정확도를 재면 과적합된 낙관치가 나온다.
train(짝수 인덱스)으로 계수를 뽑고 test(홀수 인덱스)로만 정확도를 보고한다. 테스트
fixture에도 test 절반만 담아, CI가 보정에 쓰이지 않은 데이터로 검증하게 한다.

실행:
    backend/.venv/Scripts/python.exe scripts/calibrate_sunlight.py
    backend/.venv/Scripts/python.exe scripts/calibrate_sunlight.py --write   # 시드/fixture 갱신
"""

import csv
import datetime
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.infra.public_api.kma_grid import grid_to_latlon  # noqa: E402
from app.infra.public_api.weather_client import get_monthly_daily_weather  # noqa: E402
from app.services.sunlight_calculation import (  # noqa: E402
    daylight_hours,
    day_of_year,
    extraterrestrial_radiation,
)

SEED_OUT = ROOT / "docs" / "seed" / "sunlight_calibration.json"
FIXTURE_OUT = ROOT / "backend" / "tests" / "fixtures" / "sunlight_validation.json"
REGION_GRID_SEED = ROOT / "docs" / "seed" / "region_grid_seed.csv"

# 계절을 고르게 덮는다 — 일사/일조 관계에 계절성이 있어 한 계절만 쓰면 계수가 치우친다.
SAMPLE_MONTHS = [("2024", "01"), ("2024", "04"), ("2024", "07"), ("2024", "10")]

CLEAR_SKY_MAX_RATIO = 0.80  # FAO-56 청천 Rso≈0.75·Ra. 초과는 센서 이상
MIN_RATIO = 0.03
MIN_DAYS_PER_MONTH = 10  # 월평균으로 쓸 최소 관측일수
MIN_DAYS_PER_STATION = 30  # 센서 품질 판정에 필요한 최소 표본
STATION_MIN_R2 = 0.60  # 지점별 (n/N)~(Rs/Ra) 상관이 이보다 낮으면 센서 불량
STATION_SLOPE_RANGE = (0.2, 1.0)  # 물리적으로 타당한 기울기 b


def latitude_by_sigungu() -> dict[str, float]:
    """시군구명 → 위도. 격자 시드에 위경도가 없어 격자좌표를 역변환한다."""
    out: dict[str, float] = {}
    with REGION_GRID_SEED.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                out[row["name"]] = grid_to_latlon(int(row["nx"]), int(row["ny"]))[0]
            except ValueError:
                continue  # 격자 범위 밖 — 건너뛴다
    return out


def linreg(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """단순 최소제곱 (절편, 기울기). numpy 없이 — 의존성 추가할 이유가 없다."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    return my - slope * mx, slope


def metrics(pred: list[float], obs: list[float]) -> dict[str, float]:
    n = len(pred)
    err = [p - o for p, o in zip(pred, obs)]
    mo = sum(obs) / n
    ss_res = sum(e * e for e in err)
    ss_tot = sum((o - mo) ** 2 for o in obs)
    mp = sum(pred) / n
    cov = sum((p - mp) * (o - mo) for p, o in zip(pred, obs))
    sp = math.sqrt(sum((p - mp) ** 2 for p in pred))
    so = math.sqrt(sum((o - mo) ** 2 for o in obs))
    return {
        "n": n,
        "mae_hours": sum(abs(e) for e in err) / n,
        "rmse_hours": math.sqrt(ss_res / n),
        "bias_hours": sum(err) / n,
        "r2": 1 - ss_res / ss_tot,
        "pearson_r": cov / (sp * so) if sp and so else 0.0,
        "within_0_5h": sum(1 for e in err if abs(e) <= 0.5) / n,
        "within_1h": sum(1 for e in err if abs(e) <= 1.0) / n,
    }


def collect() -> tuple[list[dict], int]:
    """API 조회 → 품질 필터 → 센서 불량 지점 제외. (정제표본, 원본행수)"""
    lat_by = latitude_by_sigungu()
    raw_count = 0
    records: list[dict] = []

    for year, month in SAMPLE_MONTHS:
        observations = get_monthly_daily_weather(year, month)
        raw_count += len(observations)
        print(f"  {year}-{month}: {len(observations)}행")
        for obs in observations:
            if obs.sunlight_hours is None or obs.solar_radiation is None:
                continue
            lat = lat_by.get(obs.point_name.split()[0] if obs.point_name else "")
            if lat is None:
                continue  # 지점의 시군구를 격자 시드에서 못 찾음
            try:
                y, m, d = (int(p) for p in obs.obs_date.split("-"))
                doy = (datetime.date(y, m, d) - datetime.date(y, 1, 1)).days + 1
            except ValueError:
                continue
            ra = extraterrestrial_radiation(lat, doy)
            n_max = daylight_hours(lat, doy)
            if ra <= 0 or n_max <= 0:
                continue
            ratio = obs.solar_radiation / ra
            if not (MIN_RATIO <= ratio <= CLEAR_SKY_MAX_RATIO):
                continue  # 물리적으로 불가능한 일사량
            if not (0 <= obs.sunlight_hours <= n_max * 1.02):
                continue  # 가조시간 초과 일조 — 센서 이상
            records.append(
                {
                    "station": obs.point_code,
                    "name": obs.point_name,
                    "latitude": lat,
                    "month": m,
                    "n_obs": obs.sunlight_hours,
                    "rs": obs.solar_radiation,
                    "ra": ra,
                    "n_max": n_max,
                }
            )

    # 지점별 상관으로 센서 불량을 걸러낸다. 이 필터를 빼면 일별 R²가 0.904 → 0.742로 떨어진다.
    by_station: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_station[r["station"]].append(r)
    good = set()
    for station, rows in by_station.items():
        if len(rows) < MIN_DAYS_PER_STATION:
            continue
        xs = [r["n_obs"] / r["n_max"] for r in rows]
        ys = [r["rs"] / r["ra"] for r in rows]
        a, b = linreg(xs, ys)
        if metrics([a + b * x for x in xs], ys)["r2"] >= STATION_MIN_R2 and (
            STATION_SLOPE_RANGE[0] <= b <= STATION_SLOPE_RANGE[1]
        ):
            good.add(station)
    print(f"  센서 정상 지점 {len(good)} / 판정대상 "
          f"{sum(1 for v in by_station.values() if len(v) >= MIN_DAYS_PER_STATION)}")
    return [r for r in records if r["station"] in good], raw_count


def main() -> None:
    write = "--write" in sys.argv
    print("농업기상 V3 조회 중...")
    records, raw_count = collect()
    print(f"원본 {raw_count}행 → 정제 {len(records)}행")

    train = [r for i, r in enumerate(records) if i % 2 == 0]
    test = [r for i, r in enumerate(records) if i % 2 == 1]
    a, b = linreg([r["n_obs"] / r["n_max"] for r in train], [r["rs"] / r["ra"] for r in train])
    print(f"\n보정계수: a={a:.4f} b={b:.4f}  (FAO-56 기본 0.25/0.50)")

    def predict(r: dict, a: float, b: float) -> float:
        return max(0.0, min(r["n_max"], r["n_max"] * ((r["rs"] / r["ra"]) - a) / b))

    daily = metrics([predict(r, a, b) for r in test], [r["n_obs"] for r in test])
    print(f"일별  R²={daily['r2']:.4f} MAE={daily['mae_hours']:.3f}h "
          f"RMSE={daily['rmse_hours']:.3f}h ±1h={daily['within_1h']:.1%}")

    grouped: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for r in test:
        grouped[(r["station"], r["month"])].append(r)
    fixture_rows = []
    for (station, month), rows in sorted(grouped.items()):
        if len(rows) < MIN_DAYS_PER_MONTH:
            continue
        fixture_rows.append(
            {
                "station": station,
                "name": rows[0]["name"],
                "month": month,
                "days": len(rows),
                "latitude": round(rows[0]["latitude"], 4),
                "solar_radiation": round(statistics.mean(r["rs"] for r in rows), 3),
                "sunlight_observed": round(statistics.mean(r["n_obs"] for r in rows), 4),
            }
        )
    monthly = metrics(
        [
            max(0.0, min(daylight_hours(f["latitude"], day_of_year(f["month"])),
                         daylight_hours(f["latitude"], day_of_year(f["month"]))
                         * ((f["solar_radiation"]
                             / extraterrestrial_radiation(f["latitude"], day_of_year(f["month"]))) - a)
                         / b))
            for f in fixture_rows
        ],
        [f["sunlight_observed"] for f in fixture_rows],
    )
    print(f"월평균({len(fixture_rows)}건) MAE={monthly['mae_hours']:.3f}h "
          f"RMSE={monthly['rmse_hours']:.3f}h r={monthly['pearson_r']:.3f} "
          f"±1h={monthly['within_1h']:.1%} bias={monthly['bias_hours']:+.3f}h")

    if not write:
        print("\n(--write 를 주면 시드와 fixture를 갱신한다)")
        return

    seed = json.loads(SEED_OUT.read_text(encoding="utf-8"))
    seed["angstrom_prescott"]["a"] = round(a, 4)
    seed["angstrom_prescott"]["b"] = round(b, 4)
    seed["validation"]["rows_fetched"] = raw_count
    seed["validation"]["rows_after_quality_filter"] = len(records)
    seed["validation"]["daily"] = {k: round(v, 4) for k, v in daily.items() if k != "n"}
    seed["validation"]["monthly_mean"] = {
        **{k: round(v, 4) for k, v in monthly.items() if k != "n"},
        "_comment": seed["validation"]["monthly_mean"].get("_comment", ""),
    }
    SEED_OUT.write_text(json.dumps(seed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    FIXTURE_OUT.write_text(
        json.dumps(
            {
                "_comment": [
                    "농업기상 V3(data.go.kr 1390802) 실측 (지점,월) 집계 — 일조시간 환산 정확도 검증용.",
                    "보정에 쓰지 않은 홀드아웃 절반만 담았다(과적합 방지). 재생성: scripts/calibrate_sunlight.py --write",
                    "sunlight_observed = 실측 일조시간 월평균(hr), solar_radiation = 실측 일사량 월평균(MJ/m2/day).",
                    "latitude는 관측지점 시군구의 기상청 격자 중심 위도(약 +-0.023도 오차).",
                ],
                "period": " / ".join(f"{y}-{m}" for y, m in SAMPLE_MONTHS),
                "rows": fixture_rows,
            },
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\n갱신: {SEED_OUT.name}, {FIXTURE_OUT.name}({len(fixture_rows)}건)")


if __name__ == "__main__":
    main()
