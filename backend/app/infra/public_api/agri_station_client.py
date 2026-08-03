"""농업기상 관측지점 상세정보 (data.go.kr 1390802, 농촌진흥청).

**엔드포인트 출처**: `Sample-code.py`(제공된 샘플 코드). 기술명세서가 없어 엔드포인트를
추측했다가 404를 맞았는데, 실제 경로는 `WeatherObsrInfo/V3/` 하위가 **아니라** 최상위다:

    https://apis.data.go.kr/1390802/AgriWeather/getObsrSpotList

인증: `serviceKey` (config.weather_observatory_api — 관측데이터 키와 다른 키다).

**실호출로 확인한 응답**(2026-07-26, total_Count=218):
    Obsr_Spot_Code "336812A001" / Obsr_Spot_Nm "아산시 염치읍"
    Instl_La 36.8257331962636 / Instl_Lo 126.9679648119612 / Instl_Al 10.0
    Instl_Adres "충남 아산시 염치읍 염치1길 40" / Obsr_Begin_Datetm "2012-08-16"
    Do_Se_Code / Mgc_Code / Clmt_Zone_Code / Comm_Mthd_Code

**왜 중요한가**: 관측데이터 API(`weather_client`)는 지점 위경도를 주지 않아서, 지점을
구역에 배정할 때 지점명 문자열을 파싱해야 했다(광역시·통합시에서 깨졌다). 이 API가 좌표를
주므로 **기상청 AWS와 똑같이 좌표 기반으로 배정**할 수 있다 — 행정계층 불일치 문제가
아예 사라진다. 상세 경위는 `MappingReport.md`.
"""

import time
from xml.etree import ElementTree

import httpx
from pydantic import BaseModel, field_validator

from app.core.config import settings
from app.infra.public_api.base import PublicApiError

BASE_URL = "https://apis.data.go.kr/1390802/AgriWeather/getObsrSpotList"

MAX_RETRIES = 3
PAGE_SIZE = 500  # 전체 218개라 1페이지로 충분하다(지점별 반복 호출 금지 — §18-1)

# 국내 좌표 범위. 벗어난 값은 입력 오류로 보고 버린다(§12 경계 방어).
LAT_RANGE = (32.0, 39.5)
LON_RANGE = (124.0, 132.5)


class AgriStation(BaseModel):
    """농업기상 관측지점 1건."""

    point_code: str  # Obsr_Spot_Code
    name: str  # Obsr_Spot_Nm (예: "아산시 염치읍")
    latitude: float  # Instl_La
    longitude: float  # Instl_Lo
    altitude: int  # Instl_Al (m)
    address: str | None  # Instl_Adres — 행정주소. 좌표 배정 결과 교차검증에 쓸 수 있다
    begin_date: str | None  # Obsr_Begin_Datetm

    @field_validator("latitude")
    @classmethod
    def lat_in_korea(cls, v: float) -> float:
        if not (LAT_RANGE[0] <= v <= LAT_RANGE[1]):
            raise ValueError(f"위도가 국내 범위 밖: {v}")
        return v

    @field_validator("longitude")
    @classmethod
    def lon_in_korea(cls, v: float) -> float:
        if not (LON_RANGE[0] <= v <= LON_RANGE[1]):
            raise ValueError(f"경도가 국내 범위 밖: {v}")
        return v


def _text(node: ElementTree.Element, tag: str) -> str | None:
    child = node.find(tag)
    if child is None or child.text is None:
        return None
    value = child.text.strip()
    return value or None


def _to_float(raw: str | None) -> float | None:
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def get_agri_stations(timeout: float = 30.0) -> list[AgriStation]:
    """농업기상 관측지점 전체 목록(좌표 포함).

    좌표가 없거나 국내 범위를 벗어난 지점은 건너뛴다 — 잘못된 좌표로 구역에 배정하면
    그 구역이 엉뚱한 지역 날씨를 받는다(§12).

    Raises:
        PublicApiError: result_Code != 200 (인증 실패 등)
    """
    params = {
        "serviceKey": settings.weather_observatory_api,
        "Page_No": "1",
        "Page_Size": str(PAGE_SIZE),
    }

    for attempt in range(MAX_RETRIES):
        try:
            resp = httpx.get(BASE_URL, params=params, timeout=timeout)
            resp.raise_for_status()
            break
        except httpx.HTTPError:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2**attempt)

    text = resp.text
    if text.lstrip().startswith("<?xml"):
        text = text.split("?>", 1)[1]
    root = ElementTree.fromstring(text)

    # 헤더 태그는 소문자 result_Code다(농업기상 계열 공통).
    code = root.findtext(".//result_Code") or root.findtext(".//Result_Code")
    if code != "200":
        raise PublicApiError(
            code or "UNKNOWN",
            root.findtext(".//result_Msg") or root.findtext(".//Result_Msg") or "알 수 없는 오류",
        )

    stations: list[AgriStation] = []
    for node in root.iter("item"):
        point_code = _text(node, "Obsr_Spot_Code")
        lat = _to_float(_text(node, "Instl_La"))
        lon = _to_float(_text(node, "Instl_Lo"))
        if not point_code or lat is None or lon is None:
            continue  # 좌표 없는 지점은 구역 배정 불가
        try:
            stations.append(
                AgriStation(
                    point_code=point_code,
                    name=_text(node, "Obsr_Spot_Nm") or point_code,
                    latitude=lat,
                    longitude=lon,
                    altitude=int(_to_float(_text(node, "Instl_Al")) or 0),
                    address=_text(node, "Instl_Adres"),
                    begin_date=_text(node, "Obsr_Begin_Datetm"),
                )
            )
        except ValueError:
            continue  # 국내 범위 밖 좌표 — 검증기가 걸렀다
    return stations
