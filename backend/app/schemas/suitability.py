from datetime import date
from typing import Literal

from pydantic import BaseModel


class IndicatorBreakdown(BaseModel):
    """지표 하나의 채점 내역. 결측/이상은 status로만 표기(value/score 없음)."""

    value: float | None = None
    score: float | None = None
    weight: float | None = None
    status: str  # optimal | allowed | risk | missing | invalid | invalid_guide
    # 장기예보 보정이 적용된 지표만 채워진다(value = baseline + correction). 근거 제시용.
    baseline: float | None = None
    correction: float | None = None
    # 기준값의 근거와 신뢰도. domestic_measured면 국내 실측, foreign_literature/provisional은
    # 잠정치라 UI가 표현을 약하게 해야 한다(§18-4).
    confidence: str | None = None
    source_ref: str | None = None


class FarmSuitability(BaseModel):
    """밭 단위 '문헌 기반 예상 적합도'(장기 탭). ML 정확도 검증 완료 아님 — 명칭 고정(§13, 핸드오프 §5).

    status: ok(정상) | dormant(기상 판정 근거 없는 달 — 토양 지침만 걸림, 점수 미노출)
    | out_of_season(해당 단계 지침 없음 — 예: 배 겨울) | insufficient_data(지표 전부 결측/이상).
    """

    farm_id: int
    crop_id: int
    region_id: int
    growth_stage: str | None
    as_of: date
    status: Literal["ok", "dormant", "out_of_season", "insufficient_data"]
    score: float | None
    grade: str | None  # S | A | B | C | null
    label: str
    breakdown: dict[str, IndicatorBreakdown]
    risk_flags: list[str]
    limitations: list[str]


class MonthlyOutlookEntry(BaseModel):
    """한 달의 전망 한 칸(히트맵 셀). 지표별 breakdown은 응답 비대를 피해 생략 — 상세는 일자 조회로."""

    month: int  # 1~12
    growth_stage: str | None
    status: Literal["ok", "dormant", "out_of_season", "insufficient_data"]
    score: float | None
    grade: str | None
    risk_flags: list[str]
    # 그 달 기온·강수에 3개월전망 보정이 반영됐는지. false면 평년치만 쓴 칸이다.
    outlook_applied: bool = False


class FarmMonthlyOutlook(BaseModel):
    """밭의 1~12월 전망(장기 탭 히트맵, `PRD.md` §4.4).

    평년치 기반 이론 추정이며 예보가 아니다 — 한계는 limitations로 함께 내려 UI에 병기한다.
    """

    farm_id: int
    crop_id: int
    region_id: int
    year: int
    label: str
    months: list[MonthlyOutlookEntry]
    limitations: list[str]
