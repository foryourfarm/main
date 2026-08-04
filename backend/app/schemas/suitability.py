from datetime import date, datetime
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

    year: int
    """창이 해를 넘기므로(11월 조회 → 11·12·1월) 칸마다 연도를 갖는다. 응답 최상위에 하나로
    두면 걸친 창에서 반드시 한쪽이 틀린다."""
    month: int  # 1~12
    growth_stage: str | None
    status: Literal["ok", "dormant", "out_of_season", "insufficient_data"]
    score: float | None
    grade: str | None
    risk_flags: list[str]
    # 그 달 기온·강수에 3개월전망 보정이 반영됐는지. false면 평년치만 쓴 칸이다.
    outlook_applied: bool = False
    outlook_published_at: datetime | None = None
    """이 칸에 쓰인 전망의 발표일. 보정이 없으면 None.

    칸마다 다른 발표분에서 올 수 있어(8/25 기준: 8월은 7/23 발표, 9·10월은 8/23 발표)
    연도와 마찬가지로 칸이 갖는다."""


class FarmMonthlyOutlook(BaseModel):
    """밭의 **다가오는 3개월** 전망(장기 탭 히트맵, `PRD.md` §4.4).

    평년치 기반 이론 추정이며 예보가 아니다 — 한계는 limitations로 함께 내려 UI에 병기한다.

    창 범위는 `months[0]`·`months[-1]`에서 나오므로 별도 필드를 두지 않는다 — 중복 필드는
    실제 값과 어긋날 여지만 만든다.
    """

    farm_id: int
    crop_id: int
    region_id: int
    label: str
    months: list[MonthlyOutlookEntry]
    limitations: list[str]


class LongTermAdvice(BaseModel):
    """장기 탭 추천 문구(PRD §10-2). 히트맵과 **별도 요청**이라 탭 렌더를 막지 않는다.

    위험 판정·수치는 백엔드 룰 엔진이 끝냈고 LLM은 문장만 다듬는다 — 히트맵 점수와 같은
    근거에서 나오므로 둘이 어긋나지 않는다.
    """

    text: str
    """항상 채워진다. LLM이 죽어도 규칙 문구가 나가고, 생육기가 아닌 창에서도 그 사실을
    문장으로 알린다 — 프론트가 "없음" 상태를 따로 처리할 필요가 없다."""

    is_llm: bool
    """false면 규칙 기반 문구 — LLM 실패·미도달이거나, 생육기가 아니라 다듬지 않은 경우다.
    다듬어진 것처럼 보이게 하지 않는다(§18-4)."""
