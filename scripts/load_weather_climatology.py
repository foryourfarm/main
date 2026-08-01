"""weather_climatology 적재 ETL (오프라인·1회성, 앱 밖).

data/03_weather_monthly_modified.csv(읍면동/시군 관측 월값, 2021~2025)를 시군 단위 월별
평균으로 집계해 weather_climatology에 넣는다. 매핑: bjd_to_region 롤업 + region_seed 직접.

한계(반드시 인지): 이는 기상청 공식 30년 평년값이 아니라 **관측 5년 평균 근사**이며
temp_avg/precipitation 2개 지표만 있다(temp_night_min/sunlight는 소스 없음 → NULL).
source='obs_mean_2021_2025'로 출처를 기록한다(재현성·정직 표기, CLAUDE.md §12).

**재실행 순서 주의**: 이 스크립트는 `source='obs_mean_2021_2025'` 행을 **지우고 다시 넣는다**.
`solar_radiation_normal`은 별도 ETL이 나중에 UPDATE로 채우는 값이라 여기서 함께 날아간다.
재실행하면 반드시 이어서 돌릴 것:
  scripts/load_solar_radiation_normal.py   (일사량 → 일조 환산의 원자료)
`reference_altitude_m`은 이 스크립트가 채우므로 `load_altitudes.py`가 **먼저** 돌아야 한다.

실행: backend 가상환경으로
  backend/.venv/Scripts/python.exe scripts/load_weather_climatology.py
"""
import csv
import statistics
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.db.session import SessionLocal  # noqa: E402
from app.models import District, Region, WeatherClimatology  # noqa: E402

WEATHER_CSV = ROOT / "data" / "03_weather_monthly_modified.csv"
BJD_TO_REGION = ROOT / "docs" / "seed" / "bjd_to_region.csv"
REGION_SEED = ROOT / "docs" / "seed" / "region_seed.csv"
SOURCE = "obs_mean_2021_2025"


def _load_code_to_region_key() -> dict[str, tuple[str, str]]:
    """weather region_code → (sido, region_name). 읍면동 롤업 + 시군 직접 둘 다."""
    mapping: dict[str, tuple[str, str]] = {}
    with BJD_TO_REGION.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            mapping[r["bjd_code"]] = (r["sido"], r["region_name"])
    with REGION_SEED.open(encoding="utf-8") as f:  # 시군 코드 직접(00000) 보강
        for r in csv.DictReader(f):
            mapping.setdefault(r["bjd_code"], (r["sido"], r["name"]))
    return mapping


def main() -> None:
    code_to_key = _load_code_to_region_key()
    db = SessionLocal()
    try:
        region_id_by_key = {
            (r.sido, r.name): r.id for r in db.query(Region).all()
        }

        # 기준 고도용. 이 평년치는 아래 region_code들의 관측을 평균한 값이므로, 그 값이
        # 대표하는 고도도 같은 코드들의 고도 평균이다(감률 보정 기준선 — DB.md §3.11).
        district_altitude = {
            d.bjd_code: d.altitude_m
            for d in db.query(District).filter(District.altitude_m.isnot(None))
        }
        # weather CSV엔 시군구 코드(끝 00000)로 들어온 행도 있다 — district에 없으므로
        # 그 행의 기준 고도는 시군 대표점이다(관측 자체가 시군 집계라 그게 맞는 대표값).
        region_altitude = {
            r.id: r.altitude_m
            for r in db.query(Region).filter(Region.altitude_m.isnot(None))
        }

        # (region_id, month) -> {"temp": [...], "precip": [...]}
        buckets: dict[tuple[int, int], dict[str, list[float]]] = defaultdict(
            lambda: {"temp": [], "precip": []}
        )
        altitudes: dict[int, list[int]] = defaultdict(list)
        unmapped: set[str] = set()
        with WEATHER_CSV.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                key = code_to_key.get(row["region_code"])
                region_id = region_id_by_key.get(key) if key else None
                if region_id is None:
                    unmapped.add(row["region_code"])
                    continue
                b = buckets[(region_id, int(row["month"]))]
                for col, bucket in (("avg_temp", "temp"), ("precipitation", "precip")):
                    raw = (row[col] or "").strip()
                    if raw and raw.upper() != "NA":  # 결측(NA/빈값)은 평균에서 제외(§12)
                        b[bucket].append(float(raw))
                        if bucket == "temp":
                            # 기온 평균에 실제로 기여한 행만 센다 — 기준 고도의 가중이
                            # 기온 평균의 가중과 같아야 감률 기준선이 맞는다.
                            # 고도 0m(해수면)을 결측으로 떨구면 안 되므로 `or`가 아니라
                            # `is None`으로 판정한다.
                            altitude = district_altitude.get(row["region_code"])
                            if altitude is None:
                                altitude = region_altitude.get(region_id)
                            if altitude is not None:
                                altitudes[region_id].append(altitude)

        db.query(WeatherClimatology).filter(
            WeatherClimatology.source == SOURCE
        ).delete()  # 재실행 idempotent

        inserted = 0
        for (region_id, month), b in buckets.items():
            db.add(
                WeatherClimatology(
                    region_id=region_id,
                    month=month,
                    temp_avg_normal=Decimal(str(round(statistics.mean(b["temp"]), 1)))
                    if b["temp"] else None,
                    temp_night_min_normal=None,  # 소스 없음
                    rainfall_normal=Decimal(str(round(statistics.mean(b["precip"]), 1)))
                    if b["precip"] else None,
                    sunlight_normal=None,  # 소스 없음
                    reference_altitude_m=round(statistics.mean(altitudes[region_id]))
                    if altitudes.get(region_id) else None,
                    source=SOURCE,
                )
            )
            inserted += 1
        db.commit()

        regions = {rid for (rid, _m) in buckets}
        print(f"적재 완료: {inserted}행 / 지역 {len(regions)}개 / 월별 집계")
        print(f"매핑 실패 weather code {len(unmapped)}개(건너뜀): {sorted(unmapped)[:10]}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
