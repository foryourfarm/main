"""3개월전망(장기 탭 tercile 보정) 적재 — CLI와 스케줄러가 공유하는 단일 경로.

종전엔 이 로직이 `scripts/load_weather_outlook.py` 본문에만 있었다. scripts/는 배포
이미지(backend/)에 들어가지 않아 런타임에서 부를 수 없었고, 그래서 자동 갱신을 붙일
자리가 없었다. 여기로 옮겨 CLI와 `POST /api/v1/admin/weather-outlooks`가 같은 함수를
부른다 — 경로가 둘로 갈리면 한쪽만 고쳐지는 사고가 난다.

**왜 자동 갱신이 필요한가**: 발표는 매월 23일 전후 1회인데, 안 받으면 장기 탭이
**에러 없이 조용히** 낡은 전망으로 남는다. 3개월 창이 전망에 묶인 뒤로는 화면이
조용히 틀려지는 경로다(nexttodo.md 인프라 §6).

멱등: `uq_outlook(region_id, target_month, indicator, published_at)` upsert라 같은
발표분을 몇 번 넣어도 안전하다. 그래서 매일 돌려도 무해하다.
"""

from datetime import date

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.infra.public_api.outlook_client import fetch_latest_outlook
from app.models import RegionOutlookZone, WeatherOutlook
from app.schemas.admin import OutlookIngestResult


def ingest_latest_outlook(db: Session, today: date) -> OutlookIngestResult:
    """최신 발표분을 받아 시/군 단위로 펼쳐 upsert.

    상류에서 유효한 XML을 못 찾으면 `OutlookFetchError`가 그대로 올라간다 — 호출자가
    CLI냐 HTTP냐에 따라 종료코드/상태코드가 달라야 해서 여기서 삼키지 않는다.
    """
    records, published = fetch_latest_outlook(today)

    # zone_name → [region_id...]. 권역 13개가 시/군 256개로 펼쳐진다(1:N).
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

    return OutlookIngestResult(
        published_at=published,
        rows=len(rows),
        target_months=sorted({r["target_month"] for r in rows}),  # type: ignore[misc]
        unmapped_zones=sorted(unmapped),
    )
