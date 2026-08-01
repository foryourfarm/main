"""district(법정동 마스터) 적재 ETL — docs/seed/bjd_to_region.csv 기반.

행이 20,275개라 마이그레이션에 INSERT를 박지 않고 여기서 적재한다(기상 평년치 ETL과 같은 패턴).
소스 CSV는 리포에 있으므로 재현 가능하다.

리(里)도 넣는다. 흙토람 토양검정 조회 단위는 읍면동이 아니라 **법정동 말단**이다 — 리가 있는
읍·면은 면 코드(리 자리 `00`)로 물으면 데이터가 있어도 301이 온다(부여 장암면 4476042000 → 301,
점상리 4476042021 → 100건). 리 없는 동만 읍면동 코드가 곧 말단이다.
설계: docs/design/ri-level-district.md

리 행의 name에 면 이름을 붙이는 이유(`"공음면 구암리"`): 계층 컬럼(parent_bjd_code) 없이도
name 정렬만으로 같은 면의 리가 붙어 나오고, 화면에서 어느 면의 리인지 읽힌다.

리를 가진 읍·면 행(1,411개)도 그대로 남긴다 — 선택지에서 빼는 건 조회 계층의 일이고
(farm_service.list_districts), 기존 밭이 면 코드로 FK를 걸고 있다.

멱등: bjd_code PK 기준 upsert. 여러 번 돌려도 안전.

실행: backend/.venv/Scripts/python.exe scripts/load_districts.py
"""

import csv
import sys
from itertools import batched
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
        ri_count = 0
        with BJD_CSV.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                region_id = region_id_by_key.get((r["sido"], r["region_name"]))
                if region_id is None:
                    unmapped.add(f"{r['sido']} {r['region_name']}")
                    continue
                if r["ri"]:
                    ri_count += 1
                rows.append(
                    {
                        "bjd_code": r["bjd_code"],
                        "region_id": region_id,
                        # 리는 부모 면과 함께 적어 화면에서 구분되게 한다(위 docstring).
                        "name": f"{r['eupmyeondong']} {r['ri']}" if r["ri"] else r["eupmyeondong"],
                    }
                )

        # 나눠 넣는 이유: 20,275행 × 3컬럼 = 60,825 바인드 파라미터로 Postgres 한도
        # 65,535에 8% 여유밖에 없다. 컬럼이 하나 늘면 한 문장으로는 못 넣는다.
        for batch in batched(rows, 5_000):
            stmt = insert(District).values(list(batch))
            stmt = stmt.on_conflict_do_update(
                index_elements=["bjd_code"],
                set_={"region_id": stmt.excluded.region_id, "name": stmt.excluded.name},
            )
            db.execute(stmt)
        db.commit()

        print(f"적재 완료: {len(rows)}행 (읍면동 {len(rows) - ri_count} + 리 {ri_count})")
        if unmapped:
            print(f"region 매핑 실패 {len(unmapped)}건(건너뜀): {sorted(unmapped)[:10]}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
