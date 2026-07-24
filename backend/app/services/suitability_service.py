"""DB 생육 지침을 적용하는 결정론적 적합도 룰 엔진."""
from collections.abc import Mapping, Sequence
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import CropGrowthGuide

ALLOWED_BOUNDARY_SCORE = 60.0  # [확인 필요] B등급 하한을 허용구간 끝점으로 사용.

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
