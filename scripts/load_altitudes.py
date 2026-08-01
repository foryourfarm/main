"""구역·법정동 대표 고도 적재 ETL — docs/seed/{region,district}_altitude_seed.csv 기반.

시드 생성(외부 API 조회)은 `gen_altitude_seed.py`가 하고, 여기는 CSV → DB만 한다.
좌표원을 나중에 법정구역 SHP로 갈아끼워도 바뀌는 건 생성 쪽뿐이다.

멱등: PK 기준 UPDATE. 여러 번 돌려도 안전.

실행: backend/.venv/Scripts/python.exe scripts/load_altitudes.py
"""

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.db.session import SessionLocal  # noqa: E402
from app.models import District, Region  # noqa: E402

REGION_CSV = ROOT / "docs" / "seed" / "region_altitude_seed.csv"
DISTRICT_CSV = ROOT / "docs" / "seed" / "district_altitude_seed.csv"


def main() -> None:
    db = SessionLocal()
    try:
        regions = {r.id: r for r in db.query(Region)}
        n_region = 0
        for row in csv.DictReader(REGION_CSV.open(encoding="utf-8")):
            region = regions.get(int(row["region_id"]))
            if region is None:
                continue
            region.altitude_m = int(row["altitude_m"])
            n_region += 1

        districts = {d.bjd_code: d for d in db.query(District)}
        n_district = 0
        for row in csv.DictReader(DISTRICT_CSV.open(encoding="utf-8")):
            district = districts.get(row["bjd_code"])
            if district is None:
                continue
            district.altitude_m = int(row["altitude_m"])
            district.altitude_source = row["altitude_source"]
            n_district += 1

        db.commit()
        print(f"구역 고도 {n_region}/{len(regions)}행, 법정동 고도 {n_district}/{len(districts)}행 적재")
        missing_region = len(regions) - n_region
        missing_district = len(districts) - n_district
        if missing_region or missing_district:
            # 조용히 빠지면 그 구역만 고도 필터·감률 보정이 꺼진다 — 반드시 드러낸다.
            print(f"[확인 필요] 고도 없는 구역 {missing_region}개 / 법정동 {missing_district}개")
    finally:
        db.close()


if __name__ == "__main__":
    main()
