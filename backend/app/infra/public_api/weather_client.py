"""농업기상 기본 관측데이터 V3 (data.go.kr 1390802, 농촌진흥청 국립농업과학원).

기술명세서: `농업기상-기본-관측데이터_API기술명세서.md`
- Base: `apis.data.go.kr/1390802/AgriWeather/WeatherObsrInfo/V3/GnrlWeather` (**V3**)
- 인증: `serviceKey` (config.weather_api)
- header: `result_Code` / `result_Msg`, 성공 = "200" (소문자 r — base.fetch_items가 대소문자
  무시로 흡수한다)

**실제 호출로 확인한 응답 필드**(2026-07-26, getWeatherMonDayList3):
    stn_Cd "230802A001" / stn_Name "영월군 영월읍" / date "2024-07-01"
    temp 25.6 / hghst_Artmp 31.7 / lowst_Artmp 20.6 / hum 79.4 / rn 0.0
    sun_Time "" / srqty 18.82 / condens_Time / gr_Temp / soil_Temp / soil_Wt

주의할 두 가지:
1. `sun_Time`(일조시간)과 `condens_Time`은 **분 단위**다. 실측 분포로 확인했다 —
   최대 793(=13.2h)으로 국내 최대 가조시간과 맞고, 시간 단위라면 불가능한 값이다.
2. `sun_Time`은 결측이 많고(26,071행 중 8,745행만 보유) `srqty`(일사량)가 더 잘 채워진다.
   그래서 일조시간은 실측이 없으면 일사량에서 환산한다(services/sunlight_calculation.py).
"""

import time

import httpx
from pydantic import BaseModel, field_validator

from app.core.config import settings
from app.infra.public_api.base import PublicApiError, fetch_items

BASE_URL = "https://apis.data.go.kr/1390802/AgriWeather/WeatherObsrInfo/V3/GnrlWeather"

MAX_RETRIES = 3
MINUTES_PER_HOUR = 60.0

# 한 페이지 크기. 전국 한 달이 약 6,500행이라 2,000이면 4페이지로 끝난다 —
# 너무 작으면 콜 수가 늘어 쿼터를 먹고, 너무 크면 타임아웃 위험이 커진다.
PAGE_SIZE = 2000
# 페이지 순회 상한(안전장치). 2000 × 50 = 10만행이면 어떤 정상 조회도 넘지 않는다.
MAX_PAGES = 50

# 이상치 컷. 국내 관측 가능 범위를 크게 벗어난 값은 센서 이상으로 보고 결측 처리한다(§12).
TEMP_MIN_C = -50.0
TEMP_MAX_C = 60.0


class WeatherObservation(BaseModel):
    """지점×일자 관측값. 결측은 None으로 두고 호출부가 제외한다(§12 결측 방어)."""

    point_code: str  # stn_Cd
    point_name: str  # stn_Name (예: "영월군 영월읍")
    obs_date: str  # date (YYYY-MM-DD)
    temp_avg: float | None  # temp (℃)
    temp_max: float | None  # hghst_Artmp (℃)
    temp_min: float | None  # lowst_Artmp (℃)
    humidity: float | None  # hum (%)
    rainfall: float | None  # rn (mm)
    sunlight_hours: float | None  # sun_Time (원본 분 → 시간으로 변환해 담는다)
    solar_radiation: float | None  # srqty (MJ/m²/day)

    @field_validator("rainfall")
    @classmethod
    def reject_negative_rainfall(cls, v: float | None) -> float | None:
        """음수 강수량은 이상치 → 결측 취급, 산출이 죽지 않게(§12)."""
        return None if v is not None and v < 0 else v

    @field_validator("temp_avg", "temp_max", "temp_min")
    @classmethod
    def reject_impossible_temp(cls, v: float | None) -> float | None:
        return None if v is not None and not (TEMP_MIN_C <= v <= TEMP_MAX_C) else v

    @field_validator("humidity")
    @classmethod
    def reject_impossible_humidity(cls, v: float | None) -> float | None:
        return None if v is not None and not (0 <= v <= 100) else v

    @field_validator("sunlight_hours", "solar_radiation")
    @classmethod
    def reject_negative(cls, v: float | None) -> float | None:
        return None if v is not None and v < 0 else v


def _to_float(raw: str | None) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _minutes_to_hours(raw: str | None) -> float | None:
    """sun_Time(분) → 시간. 명세서에 단위 표기가 없어 실측 분포로 확정했다(모듈 docstring)."""
    minutes = _to_float(raw)
    return None if minutes is None else minutes / MINUTES_PER_HOUR


def _parse(item: dict[str, str | None]) -> WeatherObservation:
    return WeatherObservation(
        point_code=item.get("stn_Cd") or "",
        point_name=item.get("stn_Name") or "",
        obs_date=item.get("date") or "",
        temp_avg=_to_float(item.get("temp")),
        temp_max=_to_float(item.get("hghst_Artmp")),
        temp_min=_to_float(item.get("lowst_Artmp")),
        humidity=_to_float(item.get("hum")),
        rainfall=_to_float(item.get("rn")),
        sunlight_hours=_minutes_to_hours(item.get("sun_Time")),
        solar_radiation=_to_float(item.get("srqty")),
    )


def _service_keys() -> list[str]:
    """사용할 인증키 순서. 쿼터 소진 시 예비 키로 넘어간다.

    쿼터가 **엔드포인트별로** 관리된다(실측: 같은 시각 `getWeatherYearMonList3`는 429인데
    `getWeatherMonDayList3`는 200). 그래서 한 엔드포인트가 막혀도 키를 바꾸면 살아날 수 있다.
    비어 있는 키는 넣지 않는다 — 빈 키로 호출하면 401이라 재시도만 낭비한다.
    """
    return [k for k in (settings.weather_api, settings.weather_api2) if k]


def _fetch_page(
    endpoint: str, params: dict[str, str], timeout: float
) -> list[WeatherObservation]:
    """한 페이지 호출. 지수 백오프 재시도 + 쿼터 소진 시 예비 키 전환(§12).

    `429 API token quota exceeded`는 재시도해도 풀리지 않는다(쿼터는 시간이 지나야 회복된다).
    그래서 백오프로 버티지 않고 **즉시 다음 키로 넘어간다** — 기다리는 것은 낭비다.
    """
    keys = _service_keys()
    if not keys:
        raise PublicApiError("NO_KEY", "농업기상 인증키가 설정되지 않았다(.env의 weather_API)")

    last_error: Exception | None = None
    for key in keys:
        for attempt in range(MAX_RETRIES):
            try:
                items = fetch_items(
                    f"{BASE_URL}/{endpoint}",
                    {"serviceKey": key, **params},
                    timeout=timeout,
                    code_tag="result_Code",
                    msg_tag="result_Msg",
                    success="200",
                )
                return [_parse(item) for item in items]
            except PublicApiError as e:
                if e.code == "301":  # 요청 데이터 없음 — 장애가 아니다
                    return []
                last_error = e
                if e.code == "101":  # 서비스키 인증 실패 — 재시도해도 같다
                    break
                if attempt == MAX_RETRIES - 1:
                    break
                time.sleep(2**attempt)
            except httpx.HTTPStatusError as e:
                last_error = e
                status = e.response.status_code
                if status in (401, 403):
                    break  # 키가 무효 — 이 키로는 더 시도하지 않고 다음 키로
                if status == 429:
                    break  # 쿼터 소진 — 백오프로 풀리지 않는다. 다음 키로
                if attempt == MAX_RETRIES - 1:
                    break
                time.sleep(2**attempt)
            except httpx.HTTPError as e:
                last_error = e
                if attempt == MAX_RETRIES - 1:
                    break
                time.sleep(2**attempt)

    assert last_error is not None
    raise last_error


def _fetch_all(
    endpoint: str, params: dict[str, str], page_size: int, timeout: float
) -> list[WeatherObservation]:
    """모든 페이지를 이어 받는다.

    왜 필요한가: 이 API는 `Page_Size`를 넘는 결과를 **조용히 자른다**. 실측 확인 —
    `Page_Size=100`으로 요청하면 `rcdcnt=100`인데 `total_Count=6551`이다. 큰 값 하나로
    때우면(과거 구현은 9999) 어느 날 전국 지점이 늘거나 기간이 길어질 때 데이터가 말없이
    사라진다. 짧은 페이지가 오면 끝난 것으로 보고 멈춘다.

    상한(MAX_PAGES)을 두는 이유: 응답이 늘 가득 차 오는 이상 상황에서 무한 루프로 쿼터를
    소진하는 것을 막는다(§12·§18-1).
    """
    collected: list[WeatherObservation] = []
    for page in range(1, MAX_PAGES + 1):
        rows = _fetch_page(
            endpoint, {**params, "Page_No": str(page), "Page_Size": str(page_size)}, timeout
        )
        collected.extend(rows)
        if len(rows) < page_size:
            return collected
    return collected


def _hyphenate(date_str: str) -> str:
    """`YYYYMMDD` → `YYYY-MM-DD`.

    기간 조회는 하이픈 형식만 받는다 — 하이픈 없이 보내면 `201 요청변수 형식이 일치하지 않은
    경우`가 온다(실측). 기술명세서는 `YYYYMMDD`로 적혀 있으나 **틀렸다**. 호출부가 어느
    형식을 주든 통하게 여기서 흡수한다.
    """
    digits = date_str.replace("-", "")
    if len(digits) != 8:
        raise ValueError(f"날짜 형식이 YYYYMMDD 또는 YYYY-MM-DD여야 한다: {date_str}")
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"


def get_monthly_daily_weather(
    year: str, month: str, page_size: int = PAGE_SIZE, timeout: float = 60.0
) -> list[WeatherObservation]:
    """명세 §3 getWeatherMonDayList3 — 해당 연·월의 **전 지점** 일별 관측.

    한 번에 전국이 오므로 평년치 ETL·보정에 이걸 쓴다(지점별 반복 호출 금지 — §18-1).
    전국 한 달이 약 6,500행이라 페이지네이션으로 나눠 받는다.
    """
    return _fetch_all(
        "getWeatherMonDayList3",
        {"search_Year": year, "search_Month": f"{int(month):02d}"},
        page_size,
        timeout,
    )


def get_period_daily_weather(
    point_code: str,
    begin_date: str,
    end_date: str,
    page_size: int = PAGE_SIZE,
    timeout: float = 60.0,
) -> list[WeatherObservation]:
    """명세 §8 getWeatherTermDayList3 — **지점×기간**(최대 365일) 일별 관측.

    지점 하나의 시계열이 필요할 때 쓴다(예: 특정 밭 지역의 최근 실측 추이).
    `obsr_Spot_Cd`는 필수다 — 빼면 `204 필수 요청변수 미입력`이 온다(실측).

    Args:
        point_code: 농업기상 관측지점코드(`stn_Cd` / `Obsr_Spot_Code`, 예 "336812A001")
        begin_date / end_date: `YYYYMMDD` 또는 `YYYY-MM-DD` (내부에서 하이픈 형식으로 변환)
    """
    return _fetch_all(
        "getWeatherTermDayList3",
        {
            "begin_Date": _hyphenate(begin_date),
            "end_Date": _hyphenate(end_date),
            "obsr_Spot_Cd": point_code,
        },
        page_size,
        timeout,
    )
