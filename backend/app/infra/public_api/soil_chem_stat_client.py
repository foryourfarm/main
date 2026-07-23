"""농경지화학성 통계정보 V2 (data.go.kr 15144685, 국립농업과학원 SoilEnviron/SoilExamStat).

시도/시군구/읍면동 단위 pH·유기물·유효인산 통계(면적 기준). 지역(soil_state) 기준값
산출용 — 필지 실측(soil_exam_client)과 달리 지역 평균.

[확인 필요] 엔드포인트(getFarmExamOmInfo)만 검색으로 확인됨 — 요청/응답 필드명은
활용신청 승인 후 실제 기술명세서로 재검증 전까지 placeholder다. "Om"이 API명에 붙어
있어 유기물 전용 엔드포인트이고 pH·유효인산은 별도 엔드포인트(getFarmExamPhInfo 등)일
가능성도 있음 — 승인 후 데이터셋 목록(data.go.kr 15144685)에서 상세기능 목록 확인 필요.
CLAUDE.md §3.4 추측 금지 — 아래 필드명으로 코드 짜지 말고 실제 호출로 먼저 확인할 것.
"""

from pydantic import BaseModel, field_validator

from app.core.config import settings
from app.infra.public_api.base import fetch_items

BASE_URL = "http://apis.data.go.kr/1390802/SoilEnviron/SoilExamStat/getFarmExamOmInfo"  # [확인 필요]


class RegionSoilChemStat(BaseModel):
    bjd_code: str
    survey_year: str  # [확인 필요] 실제 필드명(조사연도)
    ph_avg: float | None  # [확인 필요] 실제 필드명
    organic_matter_avg: float | None  # [확인 필요] 실제 필드명
    avail_p_avg: float | None  # [확인 필요] 실제 필드명

    @field_validator("ph_avg")
    @classmethod
    def ph_in_range(cls, v: float | None) -> float | None:
        return None if v is not None and not (0 <= v <= 14) else v

    @field_validator("organic_matter_avg", "avail_p_avg")
    @classmethod
    def non_negative(cls, v: float | None) -> float | None:
        return None if v is not None and v < 0 else v


def _to_float(raw: str | None) -> float | None:
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def get_region_soil_chem_stat(bjd_code: str) -> list[RegionSoilChemStat]:
    """법정동코드(읍면동, 10자리) 단위 화학성 통계 조회. [확인 필요] 파라미터명은 아래가 확정 전 추정치."""
    items = fetch_items(BASE_URL, {"serviceKey": settings.soil_api_key, "BJD_Code": bjd_code})  # [확인 필요]
    return [
        RegionSoilChemStat(
            bjd_code=item.get("BJD_Code") or bjd_code,  # [확인 필요]
            survey_year=item.get("Exam_Year") or "",  # [확인 필요]
            ph_avg=_to_float(item.get("Acid_Avg")),  # [확인 필요]
            organic_matter_avg=_to_float(item.get("Om_Avg")),  # [확인 필요]
            avail_p_avg=_to_float(item.get("Vldpha_Avg")),  # [확인 필요]
        )
        for item in items
    ]
