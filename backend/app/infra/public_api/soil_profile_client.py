"""토양도 기반 토양특성 단면정보 (data.go.kr 15098809, 국립농업과학원 SoilEnviron/SoilCharacSctnn).

심토토성 · 심토자갈함량 · 경사도 3종을 PNU(지번코드) 단위로 조회.

🔴 **2026-08-05 실호출 검증으로 결함 2건을 고쳤다. 그 전까지 이 클라이언트는 전 호출이 실패했고
(항상 None), 심토토성·자갈·경사가 전 필지 결측으로 들어오고 있었다.**

1. **URL에 `/V2`가 빠져 있었다** — 버전 없는 경로는 `NO_OPENAPI_SERVICE_ERROR`(HTTP 400)다.
2. **응답 필드가 `*_Code`가 아니라 `*_Cd`다** — 기술명세서 응답 예제(`PNU_Cd`·`Deepsoil_Qlt_Cd`)가
   맞고 종전 코드가 틀렸다. URL만 고쳤다면 파싱이 전부 None으로 조용히 새는 2차 결함이었다.

기술명세서(`soilV3_API-Guide.md`)는 경로를 `/V3`로 적지만 **`/V3`는 응답하지 않는다** — 실제로 200을
주는 것은 `/V2`뿐이다. 명세서 표기와 실제가 다르므로 명세서를 근거로 되돌리지 말 것.
인증키는 `soil_API`·`soilV3_API` 둘 다 통과한다(같은 승인 세트).

배수등급은 **이 API에 없다**. 응답은 위 3필드가 전부다 — 배수·유효토심은 별개 데이터셋인
「토양특성 **상세**정보」(data.go.kr 15144225, 27종, `settings.soil_detail_api`)에 있고 그쪽은
서비스 경로가 아직 확인되지 않았다.
"""

from pydantic import BaseModel

from app.core.config import settings
from app.infra.public_api.base import fetch_items

BASE_URL = "https://apis.data.go.kr/1390802/SoilEnviron/SoilCharacSctnn/V2/getSoilCharacterSctnn"

# 코드표 (기술명세서 3.1.1~3.1.3)
DEEPSOIL_TEXTURE = {
    "01": "사질", "02": "사양질", "03": "미사사양질",
    "04": "식양질", "05": "미사식양질", "06": "식질", "99": "기타",
}
DEEPSOIL_GRAVEL = {"01": "없음_0-15%", "02": "있음_15-35%", "03": "심함_35%이상", "99": "기타"}
SOIL_SLOPE = {
    "01": "경사_0-2%", "02": "경사_2-7%", "03": "경사_7-15%",
    "04": "경사_15-30%", "05": "경사_30-60%", "06": "경사_60-100%", "99": "기타",
}


class SoilProfile(BaseModel):
    pnu_code: str
    deepsoil_texture: str | None  # 심토토성 (코드북 매핑 후 텍스트)
    deepsoil_gravel: str | None  # 심토자갈함량
    soil_slope: str | None  # 경사도


def get_soil_profile(pnu_code: str) -> SoilProfile | None:
    """PNU(19자리 지번코드) 단위 조회. 결과 없으면 None(§8.5 결측 방어는 호출부에서)."""
    # 요청 파라미터는 `PNU_CD`, 응답 필드는 `PNU_Cd` — 표기가 다르다(실호출 확인, 2026-08-05).
    items = fetch_items(BASE_URL, {"serviceKey": settings.soil_api, "PNU_CD": pnu_code})
    if not items:
        return None
    return parse_soil_profile(items[0], pnu_code)


def parse_soil_profile(item: dict[str, str | None], pnu_code: str = "") -> SoilProfile:
    """응답 item 1건 → SoilProfile. 필드명이 다시 어긋나는 것을 테스트로 잡기 위해 분리했다."""
    return SoilProfile(
        pnu_code=item.get("PNU_Cd") or pnu_code,
        deepsoil_texture=DEEPSOIL_TEXTURE.get(item.get("Deepsoil_Qlt_Cd") or ""),
        deepsoil_gravel=DEEPSOIL_GRAVEL.get(item.get("Deepsoil_Ston_Cd") or ""),
        soil_slope=SOIL_SLOPE.get(item.get("Soilslope_Cd") or ""),
    )
