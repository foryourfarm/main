"""토양도 기반 토양특성 단면정보 (data.go.kr 15098809, 국립농업과학원 SoilEnviron/SoilCharacSctnn).

심토토성 · 심토자갈함량 · 경사도 3종을 PNU(지번코드) 단위로 조회.
스펙 확인 완료(OPEN API 기술명세서 ver1.0) — placeholder 없음.
"""

from pydantic import BaseModel

from app.core.config import settings
from app.infra.public_api.base import fetch_items

BASE_URL = "https://apis.data.go.kr/1390802/SoilEnviron/SoilCharacSctnn/getSoilCharacterSctnn"

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


# DEEPSOIL_TEXTURE 코드북 키("01"~"06","99")를 정수로 정규화한 화이트리스트.
# `crop_growth_guide.code_scores`(마이그레이션 0038)의 배점표 키가 "1"~"6"/"99"(선행 0 없음)
# 라 DB 저장 시점에 자료형을 맞춰 둔다(마이그레이션 0040 subsoil_texture_code).
_TEXTURE_CODE_WHITELIST = {1, 2, 3, 4, 5, 6, 99}


def _normalize_texture_code(raw: str | None) -> int | None:
    """API 원본 코드("01"~"06"/"99", 선행 0 있음)를 정수로 정규화(선행 0 제거).

    목록 밖 값·파싱 실패는 추측하지 않고 None으로 둔다(§4 추측 금지)."""
    if not raw:
        return None
    try:
        code = int(raw)
    except ValueError:
        return None
    return code if code in _TEXTURE_CODE_WHITELIST else None


class SoilProfile(BaseModel):
    pnu_code: str
    deepsoil_texture: str | None  # 심토토성 (코드북 매핑 후 텍스트, chat_service가 씀 — 유지)
    deepsoil_texture_code: int | None  # 심토토성 원본 등급코드(정규화됨). soil_state.subsoil_texture_code 저장용
    deepsoil_gravel: str | None  # 심토자갈함량
    soil_slope: str | None  # 경사도


def get_soil_profile(pnu_code: str) -> SoilProfile | None:
    """PNU(19자리 지번코드) 단위 조회. 결과 없으면 None(§8.5 결측 방어는 호출부에서).

    ⚠️ 호출자가 아직 0건이다(PNU를 요구하는데 `user_farm`엔 `bjd_code`만 있다) — 이 함수가
    반환하는 `deepsoil_texture_code`도 지금은 어디에도 적재되지 않는다. 새 호출 경로를 만드는
    것은 이 함수의 범위 밖이다."""
    # 응답 필드명은 기술명세서(ver1.0) 예제 기준 "*_Code"(PNU_Code, Deepsoil_Qlt_Code 등).
    # 요청 파라미터는 명세 요청부 기준 "PNU_CD"(요청/응답 표기가 다름 — 응답 필드로 단정 금지).
    items = fetch_items(BASE_URL, {"serviceKey": settings.soil_api, "PNU_CD": pnu_code})
    if not items:
        return None
    item = items[0]
    return SoilProfile(
        pnu_code=item.get("PNU_Code") or pnu_code,
        deepsoil_texture=DEEPSOIL_TEXTURE.get(item.get("Deepsoil_Qlt_Code") or ""),
        deepsoil_texture_code=_normalize_texture_code(item.get("Deepsoil_Qlt_Code")),
        deepsoil_gravel=DEEPSOIL_GRAVEL.get(item.get("Deepsoil_Ston_Code") or ""),
        soil_slope=SOIL_SLOPE.get(item.get("Soilslope_Code") or ""),
    )
