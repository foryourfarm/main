"""weather_climatology 적재 ETL (오프라인·1회성, 앱 밖).

data/03_weather_monthly_modified.csv(읍면동/시군 관측 월값, 2021~2025)를 시군 단위 월별
평균으로 집계해 weather_climatology에 넣는다. 매핑: bjd_to_region 롤업 + region_seed 직접.

한계(반드시 인지): 이는 기상청 공식 30년 평년값이 아니라 **관측 5년 평균 근사**이며
temp_avg/precipitation 2개 지표만 있다(temp_night_min/sunlight는 소스 없음 → NULL).
source='obs_mean_2021_2025'로 출처를 기록한다(재현성·정직 표기, CLAUDE.md §12).

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
from app.models import Region, WeatherClimatology  # noqa: E402

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

        # (region_id, month) -> {"temp": [...], "precip": [...]}
        buckets: dict[tuple[int, int], dict[str, list[float]]] = defaultdict(
            lambda: {"temp": [], "precip": []}
        )
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
