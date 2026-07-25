"""weather_outlook 적재 ETL — 기상청 3개월전망 RSS (DB.md §3.12).

권역 13개 × 대상월 3개 × 지표 2개 = 78레코드를 받아, region_outlook_zone 매핑으로
시/군 256개에 펼쳐 넣는다(권역 하나가 여러 시/군을 커버).

멱등: uq_outlook(region_id, target_month, indicator, published_at) 기준 upsert이므로
같은 발표분을 몇 번 돌려도 안전하다. 그래서 스케줄러가 매일 돌려도 무해하다
(발표일은 매월 23일 전후 1회뿐 — 새 발표분이 없으면 기존 행을 갱신만 한다).

실행(수동): backend/.venv/Scripts/python.exe scripts/load_weather_outlook.py
자동화: 위 명령을 스케줄러에 걸면 된다. 별도 '업데이트 버튼'은 불필요.
"""

import sys
from datetime import date
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.infra.public_api.outlook_client import (  # noqa: E402
    OutlookFetchError,
    fetch_latest_outlook,
)
from app.db.session import SessionLocal  # noqa: E402
from app.models import RegionOutlookZone, WeatherOutlook  # noqa: E402


def main() -> None:
    try:
        records, published = fetch_latest_outlook(date.today())
    except OutlookFetchError as exc:
        # 발표분을 못 찾는 것은 정상 실패 경로(스케줄러가 매일 돌아도 신규가 없을 수 있음).
        print(f"적재 생략: {exc}")
        raise SystemExit(1) from exc

    print(f"발표일 {published} · RSS 레코드 {len(records)}건")

    db = SessionLocal()
    try:
        # zone_name → [region_id...]. 권역 하나가 여러 시/군으로 펼쳐진다.
        regions_by_zone: dict[str, list[int]] = {}
        for row in db.query(RegionOutlookZone).all():
            regions_by_zone.setdefault(row.zone_name, []).append(row.region_id)

        rows: list[dict[str, object]] = []
        unmapped: set[str] = set()
        for rec in records:
            region_ids = regions_by_zone.get(rec.zone_name)
            if not region_ids:
                unmapped.add(rec.zone_name)  # 북한 권역 등 — 매핑 대상 아님
                continue
            for region_id in region_ids:
                rows.append(
                    {
                        "region_id": region_id,
                        "target_month": rec.target_month,
                        "indicator": rec.indicator,
                        "category": rec.category,
                        "prob_below": rec.prob_below,
                        "prob_normal": rec.prob_normal,
                        "prob_above": rec.prob_above,
                        "normal_value": rec.normal_value,
                        "similar_low": rec.similar_low,
                        "similar_high": rec.similar_high,
                        "published_at": rec.published_at,
                    }
                )

        if rows:
            stmt = insert(WeatherOutlook).values(rows)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_outlook",
                set_={
                    "category": stmt.excluded.category,
                    "prob_below": stmt.excluded.prob_below,
                    "prob_normal": stmt.excluded.prob_normal,
                    "prob_above": stmt.excluded.prob_above,
                    "normal_value": stmt.excluded.normal_value,
                    "similar_low": stmt.excluded.similar_low,
                    "similar_high": stmt.excluded.similar_high,
                },
            )
            db.execute(stmt)
            db.commit()

        months = sorted({str(r["target_month"]) for r in rows})
        print(f"적재 완료: {len(rows)}행 (대상월 {months})")
        if unmapped:
            print(f"매핑 없는 권역 {len(unmapped)}개(의도적 제외): {sorted(unmapped)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
