"""농경지화학성 통계정보 V2 (data.go.kr 15144685, 국립농업과학원 SoilEnviron/SoilExamStat).

법정동코드(읍면동, 10자리) 단위 pH·유기물·유효인산 통계(면적 기준). 지역 기준값 산출용.
— 필지 실측(soil_exam_client)과 달리 지역 평균(경지구분별 면적 가중).

기술명세서: 농경지화학성-통계정보_V2_API기술명세서.md
- Base URL: https://apis.data.go.kr/1390802/SoilEnviron/SoilExamStat/V2
- 엔드포인트: getFarmExamPhInfo, getFarmExamOmInfo, getFarmExamApInfo
- 응답: 논/밭/시설/과수 경지구분별 면적 구간통계
"""

from pydantic import BaseModel, field_validator

from app.core.config import settings
from app.infra.public_api.base import PublicApiError, fetch_items

BASE_URL = "https://apis.data.go.kr/1390802/SoilEnviron/SoilExamStat/V2"


class RegionSoilChemStat(BaseModel):
    """읍면동 단위 토양 화학성 통계 (면적 기준 평균)."""

    bjd_code: str  # 법정동코드 (10자리)
    bjd_name: str  # 법정동명
    ph_avg: float | None  # pH 평균 (구간통계 가중평균)
    organic_matter_avg: float | None  # 유기물 평균 (%, 구간통계 가중평균)
    avail_p_avg: float | None  # 유효인산 평균 (mg/kg, 구간통계 가중평균)

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


def _weighted_avg_from_bins(
    bin_data: dict[str, str], bin_ranges: list[tuple[float, float]]
) -> float | None:
    """구간통계(bin_1~bin_6 면적)에서 가중평균 산출.

    예: pH 논 4.5이하, 4.6~5.0, 5.1~5.5, ... 면적이 주어질 때
    각 구간의 중점값으로 면적 가중평균을 계산한다.

    Args:
        bin_data: {field_name: area_value} 예) {"acid_Rfld1_Area": "79", ...}
        bin_ranges: [(4.5, 4.5), (4.6, 5.0), (5.1, 5.5), ...] 구간 리스트

    Returns:
        가중평균값 또는 None(모든 면적이 0 또는 결측)
    """
    total_area = 0.0
    weighted_sum = 0.0

    for i, (lo, hi) in enumerate(bin_ranges, 1):
        area_str = bin_data.get(f"_Area", None)
        if not area_str:
            continue
        try:
            area = float(area_str)
        except (ValueError, TypeError):
            continue

        if area <= 0:
            continue

        mid = (lo + hi) / 2
        weighted_sum += area * mid
        total_area += area

    return weighted_sum / total_area if total_area > 0 else None


def get_region_soil_chem_stat(bjd_code: str) -> RegionSoilChemStat | None:
    """법정동코드(10자리) 단위 화학성 통계 조회.

    3개 엔드포인트(pH, 유기물, 유효인산)를 호출해 통계를 가중평균으로 산출한다.

    Args:
        bjd_code: 법정동코드 (10자리)

    Returns:
        RegionSoilChemStat 또는 None(데이터 없음)

    Raises:
        PublicApiError: API 호출 실패
    """
    params_base = {
        "serviceKey": settings.chemical_status_api,
        "STDG_CD": bjd_code,
    }

    # 1. pH 조회 (getFarmExamPhInfo)
    try:
        ph_items = fetch_items(f"{BASE_URL}/getFarmExamPhInfo", params_base)
    except PublicApiError as e:
        if e.code == "301":  # 데이터 없음
            return None
        raise

    if not ph_items:
        return None

    ph_item = ph_items[0]
    bjd_name = ph_item.get("bjd_Nm", "")
    stdg_cd = ph_item.get("stdg_Cd", bjd_code)

    # pH 평균 = 논 + 밭 + 시설 + 과수 가중평균
    # ponytail: 단순화 — 구간중점 가중 (실측 구간통계 구조상 이상적)
    ph_bins_rfld = [_to_float(ph_item.get(f"acid_Rfld{i}_Area")) for i in range(1, 7)]
    ph_bins_pfld = [_to_float(ph_item.get(f"acid_Pfld{i}_Area")) for i in range(1, 7)]
    ph_ranges = [(4.5, 4.5), (4.6, 5.0), (5.1, 5.5), (5.6, 6.0), (6.1, 6.5), (6.6, 14.0)]

    ph_avg_rfld = None
    ph_avg_pfld = None
    if any(b and b > 0 for b in ph_bins_rfld):
        ph_avg_rfld = sum(
            (lo + hi) / 2 * area for area, (lo, hi) in zip(ph_bins_rfld, ph_ranges) if area
        ) / sum(b for b in ph_bins_rfld if b)
    if any(b and b > 0 for b in ph_bins_pfld):
        ph_avg_pfld = sum(
            (lo + hi) / 2 * area for area, (lo, hi) in zip(ph_bins_pfld, ph_ranges) if area
        ) / sum(b for b in ph_bins_pfld if b)

    ph_final = None
    if ph_avg_rfld is not None and ph_avg_pfld is not None:
        ph_final = (ph_avg_rfld + ph_avg_pfld) / 2
    elif ph_avg_rfld is not None:
        ph_final = ph_avg_rfld
    elif ph_avg_pfld is not None:
        ph_final = ph_avg_pfld

    # 2. 유기물 조회 (getFarmExamOmInfo)
    try:
        om_items = fetch_items(f"{BASE_URL}/getFarmExamOmInfo", params_base)
    except PublicApiError:
        om_items = []

    om_avg = None
    if om_items:
        om_item = om_items[0]
        om_bins_rfld = [_to_float(om_item.get(f"om_Rfld{i}_Area")) for i in range(1, 7)]
        om_bins_pfld = [_to_float(om_item.get(f"om_Pfld{i}_Area")) for i in range(1, 7)]
        om_ranges = [(0, 10), (11, 20), (21, 30), (31, 40), (41, 50), (51, 100)]

        om_avg_rfld = None
        om_avg_pfld = None
        if any(b and b > 0 for b in om_bins_rfld):
            om_avg_rfld = sum(
                (lo + hi) / 2 * area for area, (lo, hi) in zip(om_bins_rfld, om_ranges) if area
            ) / sum(b for b in om_bins_rfld if b)
        if any(b and b > 0 for b in om_bins_pfld):
            om_avg_pfld = sum(
                (lo + hi) / 2 * area for area, (lo, hi) in zip(om_bins_pfld, om_ranges) if area
            ) / sum(b for b in om_bins_pfld if b)

        if om_avg_rfld is not None and om_avg_pfld is not None:
            om_avg = (om_avg_rfld + om_avg_pfld) / 2
        elif om_avg_rfld is not None:
            om_avg = om_avg_rfld
        elif om_avg_pfld is not None:
            om_avg = om_avg_pfld

    # 3. 유효인산 조회 (getFarmExamApInfo)
    try:
        ap_items = fetch_items(f"{BASE_URL}/getFarmExamApInfo", params_base)
    except PublicApiError:
        ap_items = []

    ap_avg = None
    if ap_items:
        ap_item = ap_items[0]
        ap_bins_rfld = [_to_float(ap_item.get(f"vldpha_Rfld{i}_Area")) for i in range(1, 7)]
        ap_bins_pfld = [_to_float(ap_item.get(f"vldpha_Pfld{i}_Area")) for i in range(1, 7)]
        ap_ranges_rfld = [(0, 50), (51, 100), (101, 150), (151, 200), (251, 250), (251, 9999)]
        ap_ranges_pfld = [(0, 200), (201, 300), (301, 400), (401, 500), (501, 600), (601, 9999)]

        ap_avg_rfld = None
        ap_avg_pfld = None
        if any(b and b > 0 for b in ap_bins_rfld):
            ap_avg_rfld = sum(
                (lo + hi) / 2 * area
                for area, (lo, hi) in zip(ap_bins_rfld, ap_ranges_rfld)
                if area
            ) / sum(b for b in ap_bins_rfld if b)
        if any(b and b > 0 for b in ap_bins_pfld):
            ap_avg_pfld = sum(
                (lo + hi) / 2 * area
                for area, (lo, hi) in zip(ap_bins_pfld, ap_ranges_pfld)
                if area
            ) / sum(b for b in ap_bins_pfld if b)

        if ap_avg_rfld is not None and ap_avg_pfld is not None:
            ap_avg = (ap_avg_rfld + ap_avg_pfld) / 2
        elif ap_avg_rfld is not None:
            ap_avg = ap_avg_rfld
        elif ap_avg_pfld is not None:
            ap_avg = ap_avg_pfld

    return RegionSoilChemStat(
        bjd_code=stdg_cd,
        bjd_name=bjd_name,
        ph_avg=ph_final,
        organic_matter_avg=om_avg,
        avail_p_avg=ap_avg,
    )
