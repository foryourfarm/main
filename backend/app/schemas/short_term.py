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


class DailyAdvice(BaseModel):
    """오늘의 행동추천. 위험 판정은 룰 엔진이 하고 LLM은 문장만 다듬는다(PRD §10-1)."""

    text: str
    """기상 기반 오늘의 행동. 매일 바뀌므로 LLM이 다듬는다."""
    is_llm: bool
    """false면 규칙 기반 문구다 — LLM 실패·미도달. 화면에 구분 표기한다(§18-4).
    토양 문단(`soil_text`)에는 해당하지 않는다 — 그쪽은 항상 규칙 문구다."""
    soil_text: str | None = None
    """이 밭이 속한 법정동의 토양 특성. 상시 상태라 LLM을 태우지 않고, 위험 지표가
    없으면 None이다. 별도 문단으로 렌더해 매일 바뀌는 기상 문구와 구분한다."""


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
