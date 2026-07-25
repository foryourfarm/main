"""농업기상 기본 관측데이터 클라이언트 (data.go.kr, 국립농업과학원).

[확인 필요] BASE_URL과 요청/응답 파라미터명은 활용신청 승인 후 받는 공식
기술명세서(HWP)로 아직 재검증 전이다 — 지금은 자리표시자(placeholder).
착수 전 실제 호출로 확인할 것(PRD.md §14 R2, CLAUDE.md §3.4 추측 금지).
"""

import time

import httpx
from pydantic import BaseModel, field_validator

from app.core.config import settings
from app.infra.public_api.base import PublicApiError, fetch_items

BASE_URL = "http://apis.data.go.kr/1390802/AgriWeather/WeatherObsrInfo/GnrlWeather/getWeatherDataList"  # [확인 필요]

MAX_RETRIES = 3


class WeatherObservation(BaseModel):
    point_code: str
    obs_date: str
    temp_avg: float | None
    rainfall: float | None

    @field_validator("rainfall")
    @classmethod
    def reject_negative_rainfall(cls, v: float | None) -> float | None:
        """음수 강수량은 이상치 → 결측(None) 취급, 산출이 죽지 않게(CLAUDE.md §12)."""
        return None if v is not None and v < 0 else v


def _to_float(raw: str | None) -> float | None:
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def get_daily_weather(point_code: str, year: str) -> list[WeatherObservation]:
    """관측지점×연도 단위 조회. 실패 시 지수 백오프로 재시도(CLAUDE.md §12)."""
    params = {
        "serviceKey": settings.weather_api,
        "Site": point_code,  # [확인 필요] 실제 파라미터명
        "Year": year,  # [확인 필요] 실제 파라미터명
    }

    for attempt in range(MAX_RETRIES):
        try:
            raw_items = fetch_items(BASE_URL, params)
            break
        except (httpx.HTTPError, PublicApiError):
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2**attempt)

    return [
        WeatherObservation(
            point_code=item.get("stnCode") or "",  # [확인 필요] 실제 필드명
            obs_date=item.get("obsDate") or "",  # [확인 필요] 실제 필드명
            temp_avg=_to_float(item.get("avgTemp")),  # [확인 필요] 실제 필드명
            rainfall=_to_float(item.get("sumRn")),  # [확인 필요] 실제 필드명
        )
        for item in raw_items
    ]
