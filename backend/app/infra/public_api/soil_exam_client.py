"""토양검정 화학성 상세정보 (data.go.kr 15144647, 국립농업과학원 SoilEnviron/SoilExam).

필지(PNU) 또는 법정동코드(동/리) 단위 조회 — 최근 3년 이내 최신 검정 결과 1건뿐,
시계열 아님(DB.md soil_state 초기화용 스냅샷으로만 사용).
스펙 확인 완료(OPEN API 기술명세서 ver1.0) — placeholder 없음.
"""

from pydantic import BaseModel, field_validator

from app.core.config import settings
from app.infra.public_api.base import fetch_items

BASE_URL = "http://apis.data.go.kr/1390802/SoilEnviron/SoilExam"

# 경지구분 코드표 (기술명세서 3.1)
FIELD_TYPE = {
    "1": "논", "2": "밭", "3": "시설", "4": "과수",
    "5": "간척지(논)", "6": "간척지(밭)", "7": "임야", "8": "기타",
}


class SoilExam(BaseModel):
    pnu_code: str
    sample_year: str  # Any_Year
    exam_day: str  # Exam_Day (YYYYMMDD)
    field_type: str | None  # Exam_Type 코드북 매핑
    address: str  # Pnu_Nm
    ph: float | None  # ACID
    avail_p: float | None  # VLDPHA (mg/kg)
    avail_silica: float | None  # VLDSIA (mg/kg)
    organic_matter: float | None  # OM (g/kg)
    mg: float | None  # POSIFERT_MG
    k: float | None  # POSIFERT_K
    ca: float | None  # POSIFERT_CA
    ec: float | None  # SELC (dS/m)

    @field_validator("ph")
    @classmethod
    def ph_in_range(cls, v: float | None) -> float | None:
        """pH 0~14 밖은 이상치 → 결측 취급(CLAUDE.md §12)."""
        return None if v is not None and not (0 <= v <= 14) else v

    @field_validator("avail_p", "avail_silica", "organic_matter", "mg", "k", "ca", "ec")
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


def _parse(item: dict[str, str | None]) -> SoilExam:
    return SoilExam(
        pnu_code=item.get("PNU_Code") or "",
        sample_year=item.get("Any_Year") or "",
        exam_day=item.get("Exam_Day") or "",
        field_type=FIELD_TYPE.get(item.get("Exam_Type") or ""),
        address=item.get("Pnu_Nm") or "",
        ph=_to_float(item.get("ACID")),
        avail_p=_to_float(item.get("VLDPHA")),
        avail_silica=_to_float(item.get("VLDSIA")),
        organic_matter=_to_float(item.get("OM")),
        mg=_to_float(item.get("POSIFERT_MG")),
        k=_to_float(item.get("POSIFERT_K")),
        ca=_to_float(item.get("POSIFERT_CA")),
        ec=_to_float(item.get("SELC")),
    )


def get_soil_exam(pnu_code: str) -> SoilExam | None:
    """지번코드(PNU) 단위 최신 검정 결과 1건 조회."""
    items = fetch_items(f"{BASE_URL}/getSoilExam", {"serviceKey": settings.soil_api_key, "PNU_Code": pnu_code})
    return _parse(items[0]) if items else None


def get_soil_exam_list(bjd_code: str, page_no: int = 1, page_size: int = 10) -> list[SoilExam]:
    """법정동코드(동/리, 10자리) 단위 목록 조회. 지역 기준값 산출 시 사용."""
    items = fetch_items(
        f"{BASE_URL}/getSoilExamList",
        {
            "serviceKey": settings.soil_api_key,
            "BJD_Code": bjd_code,
            "Page_No": str(page_no),
            "Page_Size": str(page_size),
        },
    )
    return [_parse(item) for item in items]
