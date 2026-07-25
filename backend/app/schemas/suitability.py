from datetime import date
from typing import Literal

from pydantic import BaseModel


class IndicatorBreakdown(BaseModel):
    """지표 하나의 채점 내역. 결측/이상은 status로만 표기(value/score 없음)."""

    value: float | None = None
    score: float | None = None
    weight: float | None = None
    status: str  # optimal | allowed | risk | missing | invalid | invalid_guide


class FarmSuitability(BaseModel):
    """밭 단위 '문헌 기반 예상 적합도'(장기 탭). ML 정확도 검증 완료 아님 — 명칭 고정(§13, 핸드오프 §5).

    status: ok(정상) | out_of_season(해당 단계 지침 없음 — 예: 배 겨울) | insufficient_data(지표 전부 결측/이상).
    """

    farm_id: int
    crop_id: int
    region_id: int
    growth_stage: str | None
    as_of: date
    status: Literal["ok", "out_of_season", "insufficient_data"]
    score: float | None
    grade: str | None  # S | A | B | C | null
    label: str
    breakdown: dict[str, IndicatorBreakdown]
    risk_flags: list[str]
    limitations: list[str]
