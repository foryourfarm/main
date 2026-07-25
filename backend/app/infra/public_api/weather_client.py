"""기상청 지상 및 AWS 일통계 자료 (지상 자료, 실측 기온/강수량).

KMA Open API Hub (apihub.kma.go.kr) — sfc_aws_day.php
- 기온 (ta_max, ta_min, ta_day) 및 강수량 (rn_day) 역사 조회.
- 510개 AWS 지점 + 지상관측 지점 커버.
- 조회 가능 기간: 과거 데이터부터 현재까지.
"""

import time

from pydantic import BaseModel, field_validator

from app.core.config import settings
from app.infra.public_api.base import PublicApiError, fetch_items

BASE_URL = "https://apihub.kma.go.kr/api/typ01/url/sfc_aws_day.php"

MAX_RETRIES = 3


class DailyWeatherObservation(BaseModel):
    """지점별 일일 기상 관측."""
    point_code: str  # STN
    obs_date: str  # TM (YYYYMMDD)
    obs_value: float | None  # VAL

    @field_validator("obs_value")
    @classmethod
    def value_sanity(cls, v: float | None) -> float | None:
        """음수값(강수량) 및 극단값(기온) 검증 — 산출 파이프라인의 후속 단계에서 세분화."""
        return None if v is not None and v < -100 else v


def _to_float(raw: str | None) -> float | None:
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def get_daily_weather(
    point_code: str,
    start_date: str,
    end_date: str,
    obs_element: str = "ta_max",
) -> list[DailyWeatherObservation]:
    """
    관측지점 × 기간 단위 조회.

    Args:
        point_code: 지점번호 (예: "108" = 서울)
        start_date: 시작일 (YYYYMMDD)
        end_date: 종료일 (YYYYMMDD)
        obs_element: 조회 요소 (ta_max, ta_min, ta_day, rn_day)

    Returns:
        list[DailyWeatherObservation]

    Raises:
        PublicApiError: API 호출 실패 시
    """
    params = {
        "tm1": start_date,
        "tm2": end_date,
        "obs": obs_element,
        "stn": point_code,
        "authKey": settings.weather_data_apikey,
    }

    for attempt in range(MAX_RETRIES):
        try:
            raw_items = fetch_items(
                BASE_URL,
                params,
                timeout=30.0,
                code_tag="errCode",  # KMA 고유 에러코드 태그
                msg_tag="errMsg",
                success="00",  # KMA 성공코드
            )
            break
        except (PublicApiError,) as e:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2**attempt)

    return [
        DailyWeatherObservation(
            point_code=item.get("STN") or "",
            obs_date=item.get("TM") or "",
            obs_value=_to_float(item.get("VAL")),
        )
        for item in raw_items
    ]
