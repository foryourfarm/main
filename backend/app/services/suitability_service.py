"""DB 생육 지침을 적용하는 결정론적 적합도 룰 엔진 + 밭 단위 조회 오케스트레이션."""
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import CropGrowthGuide, SoilState, UserFarm, WeatherClimatology
from app.services.growth_stage_service import resolve_growth_stage

ALLOWED_BOUNDARY_SCORE = 60.0  # 승인됨: B등급 하한(60)을 허용구간 끝점 점수로 사용.

# 출력 명칭은 항상 이것 — ML 정확도 검증 완료가 아님(§13, 핸드오프 §5.2).
SUITABILITY_LABEL = "문헌 기반 예상 적합도"
# temp_day는 일 실측 컬럼이 없어 월평년으로 근사(승인됨). 조용한 대체 아님 — 응답/UI에 병기.
TEMP_DAY_LIMITATION = "일 기온(temp_day)은 실측이 아니라 월평년(temp_avg_normal) 근사입니다."
# 사과 착색/성숙은 문헌이 한 구간이라 근사 분리(품종 정보 부재 → 이론 추정).
APPLE_STAGE_LIMITATION = "사과 착색/성숙 단계 구분은 품종 정보 부재로 이론 추정입니다."

# DB.md §3.5 C3. temp_day는 현재 캐시에 대응 컬럼이 없어 호출자가 별도 공급해야 한다.
INDICATOR_SOURCE_FIELDS: dict[str, str | None] = {
    "temp_day": None,
    "temp_night_min": "temp_night_min_normal",
    "rainfall": "rainfall_normal",
    "sunlight": "sunlight_normal",
    "ph": "ph",
    "ec": "ec",
    "p2o5": "p2o5",
    "organic": "organic_matter",
}


def load_guides(db: Session, crop_id: int, growth_stage: str) -> list[CropGrowthGuide]:
    """요청 단계 지침과 전 기간 공통 지침을 함께 로드한다."""
    stmt = select(CropGrowthGuide).where(
        CropGrowthGuide.crop_id == crop_id,
        or_(
            CropGrowthGuide.growth_stage == growth_stage,
            CropGrowthGuide.growth_stage.is_(None),
        ),
    )
    return list(db.scalars(stmt))


def _indicator_score(value: float, guide: CropGrowthGuide) -> tuple[float, str]:
    lo, hi = float(guide.optimal_min), float(guide.optimal_max)
    if lo <= value <= hi:
        return 100.0, "optimal"
    if value < lo and guide.allowed_min is not None and value >= float(guide.allowed_min):
        edge = float(guide.allowed_min)
        return ALLOWED_BOUNDARY_SCORE + (100 - ALLOWED_BOUNDARY_SCORE) * (
            (value - edge) / (lo - edge)
        ), "allowed"
    if value > hi and guide.allowed_max is not None and value <= float(guide.allowed_max):
        edge = float(guide.allowed_max)
        return ALLOWED_BOUNDARY_SCORE + (100 - ALLOWED_BOUNDARY_SCORE) * (
            (edge - value) / (edge - hi)
        ), "allowed"
    return 0.0, "risk"


def _is_valid(indicator: str, value: float) -> bool:
    if indicator == "ph":
        return 0 <= value <= 14
    if indicator in {"rainfall", "p2o5", "organic"}:
        return value >= 0
    return True


def _grade(score: float) -> str:
    if score >= 90:
        return "S"
    if score >= 75:
        return "A"
    if score >= 60:
        return "B"
    return "C"


def calculate_suitability(
    guides: Sequence[CropGrowthGuide],
    values: Mapping[str, float | Decimal | None],
) -> dict[str, object]:
    """결측/이상 지표는 제외하고 나머지 가중평균을 반환한다."""
    breakdown: dict[str, dict[str, object]] = {}
    risk_flags: list[str] = []
    weighted_sum = 0.0
    weight_sum = 0.0

    for guide in guides:
        indicator = guide.indicator
        raw = values.get(indicator)
        if raw is None:
            breakdown[indicator] = {"status": "missing"}
            risk_flags.append(f"{indicator}:missing")
            continue
        value = float(raw)
        if not _is_valid(indicator, value):
            breakdown[indicator] = {"value": value, "status": "invalid"}
            risk_flags.append(f"{indicator}:invalid")
            continue
        if guide.optimal_min is None or guide.optimal_max is None:
            breakdown[indicator] = {"value": value, "status": "invalid_guide"}
            risk_flags.append(f"{indicator}:invalid_guide")
            continue

        score, status = _indicator_score(value, guide)
        weight = float(guide.weight)
        breakdown[indicator] = {
            "value": value,
            "score": round(score, 1),
            "weight": weight,
            "status": status,
        }
        if status == "risk":
            risk_flags.append(f"{indicator}:outside_allowed")
        weighted_sum += score * weight
        weight_sum += weight

    if weight_sum == 0:
        return {"score": None, "grade": None, "breakdown": breakdown, "risk_flags": risk_flags}
    score = round(weighted_sum / weight_sum, 1)
    return {
        "score": score,
        "grade": _grade(score),
        "breakdown": breakdown,
        "risk_flags": risk_flags,
    }


def gather_indicator_values(
    soil: SoilState | None, clim: WeatherClimatology | None
) -> dict[str, float | Decimal | None]:
    """지표 값을 데이터원에서 모은다. 토양은 밭 실측 추정, 기상은 지역 월평년.

    temp_day는 월평년 근사(승인됨). 결측은 None으로 두고 룰 엔진이 제외한다(§12 결측 방어).
    """
    return {
        "temp_day": clim.temp_avg_normal if clim else None,  # 월평년 근사
        "temp_night_min": clim.temp_night_min_normal if clim else None,
        "rainfall": clim.rainfall_normal if clim else None,
        "sunlight": clim.sunlight_normal if clim else None,
        "ph": soil.ph if soil else None,
        "ec": soil.ec if soil else None,
        "p2o5": soil.p2o5 if soil else None,
        "organic": soil.organic_matter if soil else None,
    }


def derive_status(has_guides: bool, score: float | None) -> str:
    """적합도 결과의 상태. 지침 없음=out_of_season(예: 배 겨울), 점수 없음=insufficient_data."""
    if not has_guides:
        return "out_of_season"
    if score is None:
        return "insufficient_data"
    return "ok"


def compute_farm_suitability(
    db: Session, user_id: int, farm_id: int, on_date: date
) -> dict[str, object]:
    """밭 단위 '문헌 기반 예상 적합도'. 소유권 스코프 → 단계 resolve → 값 수집 → 룰 계산.

    소유권: user_id로 스코프해 없으면 404(남의 밭 존재를 노출하지 않음, §11).
    캐시(suitability_result)는 (지역,작물,단계) baseline 전용이라 밭 고유 토양 결과를 넣지 않는다
    (지역 baseline은 region_soil_profile+기상 적재 후 별도 upsert, §17).
    """
    farm = (
        db.query(UserFarm)
        .filter(UserFarm.user_id == user_id, UserFarm.id == farm_id)
        .first()
    )
    if farm is None:
        raise AppError(404, "FARM_NOT_FOUND", "밭을 찾을 수 없습니다.")

    stage = resolve_growth_stage(db, farm.crop_id, farm.planting_date, on_date)
    guides = load_guides(db, farm.crop_id, stage or "")
    soil = db.query(SoilState).filter(SoilState.user_farm_id == farm.id).first()
    clim = (
        db.query(WeatherClimatology)
        .filter(
            WeatherClimatology.region_id == farm.region_id,
            WeatherClimatology.month == on_date.month,
        )
        .first()
    )

    result = calculate_suitability(guides, gather_indicator_values(soil, clim))
    status = derive_status(bool(guides), result["score"])

    limitations = [TEMP_DAY_LIMITATION]
    if stage in ("coloring", "maturity"):
        limitations.append(APPLE_STAGE_LIMITATION)

    return {
        "farm_id": farm.id,
        "crop_id": farm.crop_id,
        "region_id": farm.region_id,
        "growth_stage": stage,
        "as_of": on_date,
        "status": status,
        "score": result["score"],
        "grade": result["grade"],
        "label": SUITABILITY_LABEL,
        "breakdown": result["breakdown"],
        "risk_flags": result["risk_flags"],
        "limitations": limitations,
    }
