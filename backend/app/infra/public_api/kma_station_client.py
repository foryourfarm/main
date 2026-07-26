"""기상청 AWS 관측지점 일람표 (apihub.kma.go.kr).

명세: `기상청_API-Guide.md` §방재기상연보 - 방재기상 관측지점 일람표 조회
- URL: `https://apihub.kma.go.kr/api/typ02/openApi/AwsYearlyInfoService/getAwsStnLstTbl`
- 인증: `authKey` (config.weather_apihub_key) — **data.go.kr 키와 별개 체계다.**
  data.go.kr 키를 넣으면 `401 유효한 인증키가 아닙니다`가 온다.
- 응답: `stn_id`(지점번호), `stn_ko`/`stn_en`(지점명), `lat`(북위), `lon`(동경), `ht`(해발고도)

**역할**: 이 지점들은 1차 데이터원(농업기상 216지점)의 **결측을 보완하는 2차 계층**이다.
농업기상 지점이 없는 구역(서울 25구·부산 16구 등)을 덮는 것도 이쪽이다.
두 관측망의 지점코드는 조인되지 않으므로(`230802A001` vs `108`) 계층을 잇는 키는
`region_id`다 — 상세 설계는 `MappingReport.md`.

AWS 지점은 **위경도가 있어서** 이름 매칭의 행정계층 문제를 겪지 않는다:
lat/lon → `kma_grid.latlon_to_grid()` → `region_grid` 조회 → region_id.

응답 래퍼가 data.go.kr과 달라 `base.fetch_items`를 쓰지 않는다(header/body/items 구조가
아니라 `<info>` 반복이다 — 실제 응답으로 확인).
"""

import time
from xml.etree import ElementTree

import httpx
from pydantic import BaseModel, field_validator

from app.core.config import settings
from app.infra.public_api.base import PublicApiError

BASE_URL = "https://apihub.kma.go.kr/api/typ02/openApi/AwsYearlyInfoService/getAwsStnLstTbl"

MAX_RETRIES = 3
PAGE_SIZE = 999

# 국내 좌표 범위. 벗어난 값은 센서/입력 오류로 보고 버린다(§12 경계 방어).
LAT_RANGE = (32.0, 39.5)
LON_RANGE = (124.0, 132.5)


class KmaStation(BaseModel):
    """AWS 관측지점 1건."""

    point_code: str  # stn_id
    name: str  # stn_ko
    latitude: float  # lat
    longitude: float  # lon
    altitude: int  # ht (m)

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
    return None if child is None or child.text is None else child.text.strip()


def _to_float(raw: str | None) -> float | None:
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def get_aws_stations(year: str, month: str, timeout: float = 30.0) -> list[KmaStation]:
    """AWS 지점 일람표 조회. 발표년월 기준으로 그 시점의 운영 지점 목록이 온다.

    좌표가 결측이거나 국내 범위를 벗어난 지점은 조용히 건너뛴다 — 잘못된 좌표가 엉뚱한
    구역에 배정되면 그 구역이 다른 지역 날씨를 받는다(§12).

    Raises:
        PublicApiError: 인증 실패(401) 등 호출 실패. 재시도 후에도 실패하면 올린다.
    """
    params = {
        "pageNo": "1",
        "numOfRows": str(PAGE_SIZE),
        "dataType": "XML",
        "year": year,
        "month": month,
        "authKey": settings.weather_apihub_key,
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

    # 인증 실패는 <result><status>401</status><message>…</message></result>로 온다.
    status = root.findtext(".//status")
    if status and status != "200":
        raise PublicApiError(status, root.findtext(".//message") or "알 수 없는 오류")

    stations: list[KmaStation] = []
    for node in root.iter("info"):
        lat, lon = _to_float(_text(node, "lat")), _to_float(_text(node, "lon"))
        code, name = _text(node, "stn_id"), _text(node, "stn_ko")
        if not code or lat is None or lon is None:
            continue  # 좌표 없는 지점은 구역 배정을 못 하므로 제외
        try:
            stations.append(
                KmaStation(
                    point_code=code,
                    name=name or code,
                    latitude=lat,
                    longitude=lon,
                    altitude=int(_to_float(_text(node, "ht")) or 0),
                )
            )
        except ValueError:
            continue  # 국내 범위 밖 좌표 — 검증기가 걸렀다
    return stations
