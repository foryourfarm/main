"""region_grid 적재 ETL — docs/seed/region_grid_seed.csv 기반 (DB.md §3.3).

시드는 기상청 배포 격자 엑셀에서 생성한다(scripts/gen_region_grid_seed.py).
단기예보 API가 격자좌표만 받으므로 이 표가 없으면 단기 탭이 동작하지 않는다.

멱등: region_id PK 기준 upsert. 여러 번 돌려도 안전.

실행: backend/.venv/Scripts/python.exe scripts/load_region_grid.py
"""

import csv
import sys
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.db.session import SessionLocal  # noqa: E402
from app.models import Region, RegionGrid  # noqa: E402

SEED_CSV = ROOT / "docs" / "seed" / "region_grid_seed.csv"


def main() -> None:
    db = SessionLocal()
    try:
        known = {r.id for r in db.query(Region.id).all()}

        rows: list[dict[str, object]] = []
        unknown: list[str] = []
        with SEED_CSV.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                region_id = int(r["region_id"])
                if region_id not in known:
                    unknown.append(f"{r['sido']} {r['name']}(id={region_id})")
                    continue
                rows.append({"region_id": region_id, "nx": int(r["nx"]), "ny": int(r["ny"])})

        if rows:
            stmt = insert(RegionGrid).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["region_id"],
                set_={"nx": stmt.excluded.nx, "ny": stmt.excluded.ny},
            )
            db.execute(stmt)
            db.commit()

        print(f"적재 완료: region_grid {len(rows)}행 / region {len(known)}개")
        if unknown:
            print(f"[확인 필요] region에 없는 id {len(unknown)}건(건너뜀): {unknown[:10]}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
