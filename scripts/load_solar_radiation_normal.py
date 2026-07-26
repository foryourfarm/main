"""일사량 월평년값 ETL — weather_climatology.solar_radiation_normal 적재.

**왜 필요한가**: 장기 탭 일조 지표가 어느 지역에서도 채점되지 않고 있었다. 기존 평년치 ETL
소스에 일조·일사 컬럼이 없어 `sunlight_normal`이 전 지역 NULL이기 때문이다
(`load_weather_climatology.py` docstring). 농업기상 V3가 일사량(`srqty`)을 주고,
일사량 → 일조시간 환산은 실측 홀드아웃에서 R²=0.903/MAE 0.845h로 검증됐다
(`docs/seed/sunlight_calibration.json`). 그래서 일사량을 평년값으로 적재해 두고
읽을 때 환산한다(환산값을 저장하지 않는 이유: 보정계수가 바뀌면 저장값이 낡는다).

**파이프라인**

    getWeatherMonDayList3(연·월)        전국 일별 관측 1콜/월
        └─ 품질 필터 (Rs/Ra 물리범위)     센서 이상 제거 — 이게 정확도의 전제다
            └─ 지점×월 평균              여러 해를 함께 평균 = 평년 근사
                └─ 지점 → 구역 (시드)     observation_point_seed.csv, 좌표 기반
                    └─ 구역 → 최근접 지점  확정 규칙: 최근접 1개, 1차(농업기상) 우선
                        └─ UPDATE weather_climatology

**한계(반드시 인지)**: 기상청 공식 30년 평년값이 아니라 **관측 3년 평균 근사**다.
`source` 컬럼에 기록하지 않는 이유는 기존 행의 source(온도·강수 출처)를 덮어쓰면 안 되기
때문이다 — 대신 이 파일과 `solar_radiation_normal` 컬럼 주석에 근거를 남긴다(§1-4).
구역에 관측소가 없어 최근접 지점 값을 빌린 경우가 있고, 그 거리는 런타임에
`station_service.resolve_station()`이 다시 계산해 UI에 표기한다.

**호출량**: 12개월 × 연수. 월 1콜로 전국이 오므로 지점별 반복 호출은 하지 않는다(§18-1).
API 쿼터가 있어(`429 API token quota exceeded` 실측) `--years`로 조절한다.

실행:
    backend/.venv/Scripts/python.exe scripts/load_solar_radiation_normal.py --dry-run
    backend/.venv/Scripts/python.exe scripts/load_solar_radiation_normal.py
"""

import argparse
import json
import statistics
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.db.session import SessionLocal  # noqa: E402
from app.infra.public_api.weather_client import get_monthly_daily_weather  # noqa: E402
from app.services.station_service import AGRI, resolve_station  # noqa: E402
from app.services.sunlight_calculation import (  # noqa: E402
    calibration,
    extraterrestrial_radiation,
)

DEFAULT_YEARS = ("2022", "2023", "2024")
MIN_DAYS_PER_MONTH = 10  # 월평균으로 인정할 최소 관측일수
CACHE = ROOT / "docs" / "seed" / "solar_radiation_station_monthly.json"
"""지점×월 일사량 평균 캐시. API 쿼터가 유한하므로(엔드포인트별 429 실측) 수집 결과를
커밋해 두고 재실행 시 재사용한다. 갱신은 `--refresh`."""


def _quality_bounds() -> tuple[float, float]:
    """Rs/Ra 허용범위. 일조 보정 시드와 같은 값을 쓴다 — 두 곳이 어긋나면 정확도가 깨진다."""
    bounds = calibration()["quality_bounds"]
    return bounds["min_ratio"], bounds["clear_sky_max_ratio"]


def collect_station_monthly(years: tuple[str, ...]) -> tuple[dict[tuple[str, int], float], dict]:
    """(지점코드, 월) → 일사량 평균(MJ/m²/day). 품질 필터 통과분만."""
    min_ratio, max_ratio = _quality_bounds()
    # 지점 위도는 시드에서 읽는다(관측 응답에 위경도가 없다). 좌표 기반 시드라 정확하다.
    lat_by_code: dict[str, float] = {}
    db = SessionLocal()
    try:
        for code, lat in db.execute(
            text("SELECT point_code, lat FROM kma_observation_point WHERE network = :n"),
            {"n": AGRI},
        ):
            if lat:
                lat_by_code[code] = float(lat)
    finally:
        db.close()

    samples: dict[tuple[str, int], list[float]] = defaultdict(list)
    stats: dict[str, int] = defaultdict(int)
    for year in years:
        for month in range(1, 13):
            observations = get_monthly_daily_weather(year, f"{month:02d}")
            stats["행"] += len(observations)
            for obs in observations:
                if obs.solar_radiation is None or obs.solar_radiation <= 0:
                    stats["일사량 결측"] += 1
                    continue
                lat = lat_by_code.get(obs.point_code)
                if lat is None:
                    stats["지점 위도 없음"] += 1
                    continue
                try:
                    y, m, d = (int(p) for p in obs.obs_date.split("-"))
                    doy = (date(y, m, d) - date(y, 1, 1)).days + 1
                except ValueError:
                    stats["날짜 파싱 실패"] += 1
                    continue
                ra = extraterrestrial_radiation(lat, doy)
                if ra <= 0 or not (min_ratio <= obs.solar_radiation / ra <= max_ratio):
                    # 청천 상한을 넘는 값은 센서 이상이다. 남겨두면 일조 환산 R²가
                    # 0.904 → 0.742로 떨어진다(sunlight_calibration.json).
                    stats["물리범위 밖"] += 1
                    continue
                samples[(obs.point_code, m)].append(obs.solar_radiation)
            print(f"  {year}-{month:02d}: 누적 표본 {sum(len(v) for v in samples.values())}")

    monthly = {
        key: statistics.mean(values)
        for key, values in samples.items()
        if len(values) >= MIN_DAYS_PER_MONTH
    }
    stats["지점×월 채택"] = len(monthly)
    stats["지점×월 표본부족"] = len(samples) - len(monthly)
    return monthly, stats


def _save_cache(monthly: dict[tuple[str, int], float], years: tuple[str, ...]) -> None:
    CACHE.write_text(
        json.dumps(
            {
                "years": list(years),
                "_comment": (
                    "지점×월 일사량 평균(MJ/m2/day). 키는 '지점코드|월'. "
                    "갱신: scripts/load_solar_radiation_normal.py --refresh"
                ),
                "monthly": {f"{c}|{m}": round(v, 3) for (c, m), v in sorted(monthly.items())},
            },
            ensure_ascii=False,
            indent=0,
        ),
        encoding="utf-8",
    )


def _load_cache() -> tuple[dict[tuple[str, int], float], list[str]]:
    cached = json.loads(CACHE.read_text(encoding="utf-8"))
    monthly = {
        (key.split("|")[0], int(key.split("|")[1])): value
        for key, value in cached["monthly"].items()
    }
    return monthly, cached.get("years", [])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", nargs="+", default=list(DEFAULT_YEARS))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--refresh", action="store_true", help="캐시를 무시하고 API 재조회")
    args = parser.parse_args()

    # 캐시를 먼저 본다: API 쿼터가 유한하고(엔드포인트별 429 실측) 3년치 수집은 36콜이다.
    # 배정 규칙만 바꿔 다시 돌리는 경우가 많아 재조회는 순수 낭비다.
    if CACHE.exists() and not args.refresh:
        monthly, cached_years = _load_cache()
        print(f"캐시 사용: {CACHE.name} ({len(monthly)} 지점×월, 수집연도 {cached_years})")
        print("  API를 호출하지 않았다 (--refresh 로 재조회)")
    else:
        print(f"농업기상 일사량 조회 ({', '.join(args.years)} × 12개월 = {len(args.years) * 12}콜)")
        monthly, stats = collect_station_monthly(tuple(args.years))
        print("\n수집 통계:")
        for key in sorted(stats):
            print(f"  {key:18s} {stats[key]:8d}")
        _save_cache(monthly, tuple(args.years))
        print(f"  캐시 저장: {CACHE.name}")

    db = SessionLocal()
    try:
        # 평년치 행이 있는 구역만 대상이다 — 일사량은 기존 행에 붙는 값이라
        # 행이 없는 구역은 애초에 장기 탭에서 인접 구역 값으로 대체된다(§8.5).
        regions = [
            r[0]
            for r in db.execute(
                text("SELECT DISTINCT region_id FROM weather_climatology ORDER BY region_id")
            )
        ]
        print(f"\n평년치 보유 구역 {len(regions)}개에 일사량 배정")

        # **데이터가 있는 지점만 후보로 둔다.** 단순 최근접을 쓰면 마스터에는 있으나 일사량
        # 관측이 없는 지점이 뽑혀 그 구역이 조용히 비어 버린다 — 실측으로 116개 중 20개가
        # 그렇게 비었다(완도군·파주시·가평군 등). station_service의 allowed_codes로 제한한다.
        codes_with_data = {code for code, _month in monthly}
        print(f"  일사량 데이터 보유 지점: {len(codes_with_data)}개")

        updates: list[dict] = []
        no_station = 0
        borrowed: list[tuple[int, float]] = []
        for region_id in regions:
            match = resolve_station(db, region_id, prefer=AGRI, allowed_codes=codes_with_data)
            if match is None or match.network != AGRI:
                # 일사량은 1차(농업기상)에만 있다. AWS로 내려간 구역은 값이 없다.
                no_station += 1
                continue
            if not match.is_inside_region:
                borrowed.append((region_id, match.distance_km))
            for month in range(1, 13):
                value = monthly.get((match.point_code, month))
                if value is not None:
                    updates.append(
                        {"region_id": region_id, "month": month, "value": Decimal(f"{value:.2f}")}
                    )

        print(f"  배정 완료 {len(updates)}행 (구역×월)")
        print(f"  일사량 관측소 없음: {no_station}개 구역 — 일조 지표는 계속 비어 있다")
        if borrowed:
            worst = max(d for _, d in borrowed)
            print(f"  인접 관측소 차용: {len(borrowed)}개 구역 (최대 {worst:.1f}km) — UI 표기 필요")

        if args.dry_run:
            print("\n(--dry-run — DB를 바꾸지 않았다)")
            return

        db.execute(
            text(
                """
                UPDATE weather_climatology
                   SET solar_radiation_normal = :value
                 WHERE region_id = :region_id AND month = :month
                """
            ),
            updates,
        )
        db.commit()

        filled = db.execute(
            text("SELECT count(*) FROM weather_climatology WHERE solar_radiation_normal IS NOT NULL")
        ).scalar()
        total = db.execute(text("SELECT count(*) FROM weather_climatology")).scalar()
        covered = db.execute(
            text(
                "SELECT count(DISTINCT region_id) FROM weather_climatology "
                "WHERE solar_radiation_normal IS NOT NULL"
            )
        ).scalar()
        print(f"\n적재 완료: {filled}/{total}행에 일사량 (구역 {covered}개)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
