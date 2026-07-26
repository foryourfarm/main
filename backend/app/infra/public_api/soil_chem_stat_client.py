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
    """읍면동 단위 토양 화학성 통계 (면적 기준 평균).

    [한계 표기 필수] 이 API V2 응답에는 조사연도 필드가 없다(응답 항목이 stdg_Cd, bjd_Nm,
    구간별 면적뿐 — 기술명세서 §응답 항목). 따라서 이 값이 몇 년도 조사인지 알 수 없다.
    없는 연도를 채워 넣지 않고 비워 두며, 이 값을 쓰는 화면은 "조사연도 미상 · 읍면동 평균"
    임을 병기해야 한다(§1-4, §18-4). 또한 필지 실측이 아니라 읍면동 면적가중 평균이다.
    """

    bjd_code: str  # 법정동코드 (10자리)
    bjd_name: str  # 법정동명
    ph_avg: float | None  # pH 평균 (구간통계 가중평균)
    organic_matter_avg: float | None  # 유기물 평균 (g/kg, 구간통계 가중평균) — OM_RANGES 참고
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


# 구간통계의 구간 경계. 기술명세서 응답 필드명(§응답 항목)에 적힌 구간을 그대로 옮긴 것 —
# 농업 기준값이 아니라 API 스키마의 일부라 시드가 아닌 여기 두는 것이 맞다(§4 매직넘버 금지).
#
# **개방구간(최상단 "N이상", 최하단 "N이하") 처리** — 이론상 상한(pH 14, 인산 9999)을 그대로
# 쓰면 중점이 폭주한다. 실측 확인: 고창군 밭 유효인산 최상단 구간(601이상)이 6,765ha로 가장
# 넓은데 상한 9999를 쓰면 중점 5300이 되어 지역 평균이 2008 mg/kg으로 나왔다(한국 밭 실제
# 평균은 400~600). 그래서 개방구간은 **직전 구간과 같은 폭**을 가정해 대표값을 잡는다 —
# 구간자료(grouped data) 평균 산출의 통상적 관례이며, 이론 상한보다 실측 분포에 가깝다.
# 이 가정 때문에 결과는 지역 근사이고 확정 실측이 아니다(§18-4 — UI에 표기 필요).
PH_RANGES = [(4.0, 4.5), (4.6, 5.0), (5.1, 5.5), (5.6, 6.0), (6.1, 6.5), (6.6, 7.1)]

# 유기물 단위는 g/kg다(docs/data/Data-Guideline.md "유기물 평균 (g/kg)"). 명세서 구간이
# 10/20/30/40/50 이하로 끊기는 것도 g/kg 기준과 맞는다(% 라면 논밭 대부분이 첫 구간).
# 실측 확인: 고창군 19.7 g/kg — 한국 농경지 통상 범위(15~30 g/kg)와 일치.
OM_RANGES = [(0, 10), (11, 20), (21, 30), (31, 40), (41, 50), (51, 61)]

# 유효인산(mg/kg). 논은 50 단위, 밭은 100 단위로 구간이 다르다.
# 5번째 구간에 주의: 명세서 표기가 "논251~250이하"인데 4번째가 151~200, 6번째가 251이상이라
# 251은 명세서 오타이고 실제 구간은 201~250이다. 명세서를 그대로 베끼면 중점이 225.5 대신
# 250.5가 되어 그 구간 면적만큼 평균이 위로 밀린다.
AP_RANGES_PADDY = [(0, 50), (51, 100), (101, 150), (151, 200), (201, 250), (251, 301)]
AP_RANGES_FIELD = [(0, 200), (201, 300), (301, 400), (401, 500), (501, 600), (601, 701)]


def _weighted_avg(
    areas: list[float | None], ranges: list[tuple[float, float]]
) -> float | None:
    """구간통계(구간별 면적 6개)의 구간중점 면적가중평균. 면적이 전부 0/결측이면 None.

    한계: 구간 대표값으로 중점을 쓴다 — 원 데이터가 구간별 면적만 주므로 구간 내 분포는
    알 수 없다. 특히 양끝 열린 구간(예: pH 6.6이상, 유효인산 601이상)은 중점이 임의값에
    가깝다. 확정 실측이 아니라 지역 근사임을 UI에 표기해야 한다(§18-4).
    """
    total = sum(a for a in areas if a and a > 0)
    if total <= 0:
        return None
    return sum((lo + hi) / 2 * a for a, (lo, hi) in zip(areas, ranges) if a and a > 0) / total


def _mean_of_field_types(
    item: dict[str, str],
    prefix: str,
    paddy_ranges: list[tuple[float, float]],
    field_ranges: list[tuple[float, float]],
) -> float | None:
    """논(Rfld)·밭(Pfld) 구간통계를 각각 가중평균한 뒤 둘의 단순평균.

    한계: 논/밭을 면적이 아니라 1:1로 섞는다 — 원 응답에 경지구분별 총면적이 따로 없어
    (구간 면적 합으로 유추는 가능하나 결측 구간이 있으면 어긋난다) 단순평균으로 둔다.
    한쪽만 있으면 그쪽 값을 쓴다. 시설·과수(Vnyl/Orch)는 명세서 구간이 달라 제외한다.
    """
    paddy = _weighted_avg(
        [_to_float(item.get(f"{prefix}_Rfld{i}_Area")) for i in range(1, 7)], paddy_ranges
    )
    field = _weighted_avg(
        [_to_float(item.get(f"{prefix}_Pfld{i}_Area")) for i in range(1, 7)], field_ranges
    )
    if paddy is not None and field is not None:
        return (paddy + field) / 2
    return paddy if paddy is not None else field


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

    ph_final = _mean_of_field_types(ph_item, "acid", PH_RANGES, PH_RANGES)

    # 2. 유기물 조회 (getFarmExamOmInfo)
    try:
        om_items = fetch_items(f"{BASE_URL}/getFarmExamOmInfo", params_base)
    except PublicApiError:
        om_items = []

    om_avg = _mean_of_field_types(om_items[0], "om", OM_RANGES, OM_RANGES) if om_items else None

    # 3. 유효인산 조회 (getFarmExamApInfo)
    try:
        ap_items = fetch_items(f"{BASE_URL}/getFarmExamApInfo", params_base)
    except PublicApiError:
        ap_items = []

    # 유효인산은 논/밭 구간 경계가 서로 다르다(논 50 단위, 밭 100 단위) — 표를 따로 준다.
    ap_avg = (
        _mean_of_field_types(ap_items[0], "vldpha", AP_RANGES_PADDY, AP_RANGES_FIELD)
        if ap_items
        else None
    )

    return RegionSoilChemStat(
        bjd_code=stdg_cd,
        bjd_name=bjd_name,
        ph_avg=ph_final,
        organic_matter_avg=om_avg,
        avail_p_avg=ap_avg,
    )
