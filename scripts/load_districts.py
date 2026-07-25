"""district(읍면동 마스터) 적재 ETL — docs/seed/bjd_to_region.csv 기반.

행이 5,066개라 마이그레이션에 INSERT를 박지 않고 여기서 적재한다(기상 평년치 ETL과 같은 패턴).
소스 CSV는 리포에 있으므로 재현 가능하다.

리(里) 레벨은 넣지 않는다 — 흙토람 토양검정 조회 단위가 읍면동이고, 드롭다운도 읍면동까지면
충분하다(PRD.md §5).

멱등: bjd_code PK 기준 upsert. 여러 번 돌려도 안전.

실행: backend/.venv/Scripts/python.exe scripts/load_districts.py
"""

import csv
import sys
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.db.session import SessionLocal  # noqa: E402
from app.models import District, Region  # noqa: E402

BJD_CSV = ROOT / "docs" / "seed" / "bjd_to_region.csv"


def main() -> None:
    db = SessionLocal()
    try:
        region_id_by_key = {(r.sido, r.name): r.id for r in db.query(Region).all()}

        rows: list[dict[str, object]] = []
        unmapped: set[str] = set()
        with BJD_CSV.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["ri"]:
                    continue  # 리 레벨 제외 — 조회 단위가 읍면동
                region_id = region_id_by_key.get((r["sido"], r["region_name"]))
                if region_id is None:
                    unmapped.add(f"{r['sido']} {r['region_name']}")
                    continue
                rows.append(
                    {
                        "bjd_code": r["bjd_code"],
                        "region_id": region_id,
                        "name": r["eupmyeondong"],
                    }
                )

        if rows:
            stmt = insert(District).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["bjd_code"],
                set_={"region_id": stmt.excluded.region_id, "name": stmt.excluded.name},
            )
            db.execute(stmt)
            db.commit()

        print(f"적재 완료: 읍면동 {len(rows)}행")
        if unmapped:
            print(f"region 매핑 실패 {len(unmapped)}건(건너뜀): {sorted(unmapped)[:10]}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
