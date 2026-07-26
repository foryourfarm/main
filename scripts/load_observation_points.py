"""관측지점 적재 ETL — docs/seed/observation_point_seed.csv 기반 (MappingReport.md).

두 관측망을 한 테이블에 넣고 `network`로 구분한다:
- `agri`   농업기상 215지점 — 1차. 일사량(srqty)·일조시간(sun_Time) 보유
- `kma_aws` 기상청 AWS 533지점 — 2차. 1차 결측 보완 + 농업기상 지점 없는 구역

시드는 `scripts/gen_observation_point_seed.py`가 만든다(API 조회 + 구역 배정).
이 스크립트는 CSV를 읽어 넣기만 한다 — 런타임에 문자열 파싱/API 호출을 하지 않는다(§10).

멱등: point_code PK 기준 upsert. 여러 번 돌려도 안전.

실행: backend/.venv/Scripts/python.exe scripts/load_observation_points.py
"""

import csv
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.db.session import SessionLocal  # noqa: E402
from app.models import KmaObservationPoint, Region  # noqa: E402

SEED_CSV = ROOT / "docs" / "seed" / "observation_point_seed.csv"


def _int_or_none(raw: str) -> int | None:
    return int(raw) if raw not in ("", None) else None


def _float_or_zero(raw: str) -> float:
    """농업기상 지점은 위경도가 없다(빈 값) — 0.0으로 넣고 격자(nx, ny)로 위치를 판단한다."""
    return float(raw) if raw not in ("", None) else 0.0


def main() -> None:
    db = SessionLocal()
    try:
        known_regions = {r.id for r in db.query(Region.id).all()}

        rows: list[dict[str, object]] = []
        unknown_region: list[str] = []
        with SEED_CSV.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                region_id = _int_or_none(r["region_id"])
                if region_id is not None and region_id not in known_regions:
                    # 시드가 region_seed보다 앞서갔다는 뜻 — 조용히 넣으면 FK 위반으로 죽는다.
                    unknown_region.append(f"{r['name']}(region_id={region_id})")
                    region_id = None
                rows.append(
                    {
                        "point_code": r["point_code"],
                        "name": r["name"],
                        "lat": _float_or_zero(r["lat"]),
                        "lon": _float_or_zero(r["lon"]),
                        "altitude": int(r["altitude"] or 0),
                        "nx": _int_or_none(r["nx"]),
                        "ny": _int_or_none(r["ny"]),
                        "region_id": region_id,
                        "network": r["network"],
                    }
                )

        if rows:
            stmt = insert(KmaObservationPoint).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["point_code"],
                set_={
                    "name": stmt.excluded.name,
                    "lat": stmt.excluded.lat,
                    "lon": stmt.excluded.lon,
                    "altitude": stmt.excluded.altitude,
                    "nx": stmt.excluded.nx,
                    "ny": stmt.excluded.ny,
                    "region_id": stmt.excluded.region_id,
                    "network": stmt.excluded.network,
                },
            )
            db.execute(stmt)
            db.commit()

        by_network = Counter(str(r["network"]) for r in rows)
        assigned = sum(1 for r in rows if r["region_id"] is not None)
        regions_inside = len({r["region_id"] for r in rows if r["region_id"] is not None})
        print(f"적재 완료: kma_observation_point {len(rows)}행")
        print(f"  관측망별: {dict(by_network)}")
        print(f"  구역 배정됨: {assigned}/{len(rows)}  (구역 안에 지점이 있는 구역 {regions_inside}개)")
        print(f"  미배정 {len(rows) - assigned}건 — 격자 밖 도서(독도 등). 조회에서 제외된다.")
        if unknown_region:
            print(f"[확인 필요] region에 없는 id {len(unknown_region)}건(NULL 처리): {unknown_region[:5]}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
