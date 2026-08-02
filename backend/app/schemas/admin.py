"""운영 작업 응답 DTO."""

from datetime import date

from pydantic import BaseModel


class OutlookIngestResult(BaseModel):
    """3개월전망 적재 1회 결과. 스케줄러 로그에서 "돌긴 했는데 뭘 넣었나"를 볼 수 있어야 한다."""

    published_at: date
    rows: int
    target_months: list[date]
    # 북한 권역 등 region 매핑이 없는 권역. 의도적 제외라 실패가 아니지만, 목록이 갑자기
    # 늘면 RSS 권역명이 바뀐 것이므로 응답에 실어 눈에 띄게 한다.
    unmapped_zones: list[str]
