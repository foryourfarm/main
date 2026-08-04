from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel


class HourlyTemp(BaseModel):
    """시간별 기온 한 점. 날짜 상세 모달의 기온 곡선용(0031)."""

    h: int
    """시각(0~23)."""
    t: Decimal
    """그 시각 예보 기온(℃)."""


class ShortTermDay(BaseModel):
    """하루치 예보 + 위험 판정. 위험 임계는 장기 탭과 같은 crop_growth_guide 허용구간이다.

    **기온 필드 3개의 쓰임이 다르다.** `temp_max`는 카드에 "낮 최고기온"으로 보여주는 값이고,
    `temp_avg`는 점수를 매긴 근거(지표 `temp_day`)다. 둘을 함께 내보내야 모달이 "표시값과
    채점값이 다르다"를 설명할 수 있다 — 종전엔 `temp_avg` 하나가 두 역할을 겸해 일평균을
    "낮 기온"이라 부르고 있었다.
    """

    target_date: date
    growth_stage: str | None
    status: Literal["ok", "dormant", "out_of_season", "insufficient_data"]
    score: float | None
    grade: str | None
    temp_avg: Decimal | None
    """일평균기온 — **점수의 근거**. 카드의 낮 최고기온이 아니다."""
    temp_max: Decimal | None
    """일최고기온 — 카드 표시값. 0031 이전 캐시에는 없어 null일 수 있다."""
    temp_night_min: Decimal | None
    rainfall: Decimal | None
    hourly_temp: list[HourlyTemp] | None
    """시각 오름차순. 0031 이전 캐시에는 없어 null일 수 있다."""
    is_imputed: bool
    """그날 예보 표본이 하루를 온전히 덮지 못함 — 집계값이 편향돼 있다(첫날·지평 끝날)."""
    risk_flags: list[str]
    breakdown: dict[str, dict[str, Any]] | None = None
    """지표별 채점 내역(값·점수·상태·밴드). 모달에서 점수 근거를 보여주고 그래프에 적정·허용
    구간을 음영으로 얹는 데 쓴다 — 종전엔 `compute_short_term`이 계산해두고도 이 스키마에
    필드가 없어 응답에서 탈락했다.

    `/advice`가 `compute_short_term`을 다시 부르는 것은 이것과 무관하다 — 별도 HTTP 요청이라
    응답을 재사용할 수 없고, 위험 판정 로직을 한 곳에 두려고 일부러 그렇게 한 것이다
    (`api/farms.py:get_farm_advice` 독스트링)."""


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
