from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class ShortTermDay(BaseModel):
    """하루치 예보 + 위험 판정. 위험 임계는 장기 탭과 같은 crop_growth_guide 허용구간이다."""

    target_date: date
    growth_stage: str | None
    status: Literal["ok", "dormant", "out_of_season", "insufficient_data"]
    score: float | None
    grade: str | None
    temp_avg: Decimal | None
    temp_night_min: Decimal | None
    rainfall: Decimal | None
    risk_flags: list[str]


class PersistentRisk(BaseModel):
    """연속 지속되는 위험. 하루짜리 노이즈와 구분해 선제 안내에 쓴다(PRD 철학 3)."""

    flag: str
    days: int
    dates: list[str]


class FarmShortTerm(BaseModel):
    """단기 탭(오늘~3일). 예보이므로 발표마다 바뀐다 — limitations를 UI에 병기한다."""

    farm_id: int
    crop_id: int
    region_id: int
    as_of: date
    base_at: datetime | None
    """예보 발표시각. None이면 예보를 아직 확보하지 못한 상태."""
    is_stale: bool
    """true면 조회 실패로 직전 캐시를 쓴 것 — 화면에 '최신 아님'을 표시해야 한다(§12)."""
    label: str
    days: list[ShortTermDay]
    persistent_risks: list[PersistentRisk]
    limitations: list[str]
