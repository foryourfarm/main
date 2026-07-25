"""DB 생육 지침을 적용하는 결정론적 적합도 룰 엔진 + 밭 단위 조회 오케스트레이션."""
from calendar import monthrange
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import CropGrowthGuide, CropGrowthStage, SoilState, UserFarm, WeatherClimatology
from app.services.growth_stage_service import pick_stage, resolve_growth_stage
from app.services.outlook_correction import apply_corrections, load_corrections

ALLOWED_BOUNDARY_SCORE = 60.0  # 승인됨: B등급 하한(60)을 허용구간 끝점 점수로 사용.

# 출력 명칭은 항상 이것 — ML 정확도 검증 완료가 아님(§13, 핸드오프 §5.2).
SUITABILITY_LABEL = "문헌 기반 예상 적합도"
# temp_day는 일 실측 컬럼이 없어 월평년으로 근사(승인됨). 조용한 대체 아님 — 응답/UI에 병기.
TEMP_DAY_LIMITATION = "일 기온(temp_day)은 실측이 아니라 월평년(temp_avg_normal) 근사입니다."
# 사과 착색/성숙은 문헌이 한 구간이라 근사 분리(품종 정보 부재 → 이론 추정).
APPLE_STAGE_LIMITATION = "사과 착색/성숙 단계 구분은 품종 정보 부재로 이론 추정입니다."

MONTHLY_CLIMATOLOGY_LIMITATION = (
    "월별 전망은 평년치(월 단위 기상 평균) 기반 이론 추정이며 실제 예보가 아닙니다."
)
MONTHLY_STAGE_LIMITATION = (
    "각 월의 생육단계는 그 달에 가장 많은 날을 차지한 단계로 표기합니다 — "
    "한 달에 두 단계가 걸치면 짧은 쪽은 표기되지 않습니다."
)
MONTHLY_SOIL_LIMITATION = (
    "토양 지표는 12개월에 현재 추정값을 동일 적용합니다(월별 토양 변화는 반영하지 않음)."
)
OUTLOOK_APPLIED_LIMITATION = (
    "기온·강수는 평년치에 기상청 3개월전망(확률예보)을 반영해 보정했습니다. "
    "전망이 없는 월·지표(야간최저기온·일조 등)는 평년치를 그대로 씁니다."
)
OUTLOOK_MISSING_LIMITATION = (
    "기상청 3개월전망이 적재되지 않아 보정 없이 평년치만 사용했습니다."
)

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
    applied: Mapping[str, tuple[Decimal, Decimal]] | None = None,
) -> dict[str, object]:
    """결측/이상 지표는 제외하고 나머지 가중평균을 반환한다.

    `applied`는 장기예보 보정 내역 {지표: (baseline, 보정치)} — 넘기면 breakdown에
    평년치·보정치를 분해해 기록한다(근거 제시, DB.md §8.1-5).
    """
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
        entry: dict[str, object] = {
            "value": value,
            "score": round(score, 1),
            "weight": weight,
            "status": status,
        }
        if applied and indicator in applied:
            baseline, correction = applied[indicator]
            entry["baseline"] = float(baseline)
            entry["correction"] = float(correction)
        breakdown[indicator] = entry
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

    # 장기예보 보정은 read-time에만 얹는다(캐시 금지 — §3.13 B1).
    corrections = load_corrections(db, farm.region_id, [on_date.month], on_date.year)
    values, applied = apply_corrections(
        gather_indicator_values(soil, clim), corrections, on_date.month
    )
    result = calculate_suitability(guides, values, applied)
    status = derive_status(bool(guides), result["score"])

    limitations = [TEMP_DAY_LIMITATION]
    limitations.append(OUTLOOK_APPLIED_LIMITATION if applied else OUTLOOK_MISSING_LIMITATION)
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


def _guides_for_stage(
    all_guides: Sequence[CropGrowthGuide], stage: str | None
) -> list[CropGrowthGuide]:
    """단계 지침 + 전 기간 공통(NULL) 지침. load_guides의 SQL 필터를 메모리에서 재현한다."""
    return [g for g in all_guides if g.growth_stage == stage or g.growth_stage is None]


def dominant_stage(
    stage_rows: list[CropGrowthStage], planting_date: date, year: int, month: int
) -> str | None:
    """그 달에 가장 많은 날을 차지한 생육단계. 단계가 하루도 안 걸치면 None.

    대표일 1개(예: 매월 15일)로 판정하면 월 경계에 걸친 짧은 단계가 12칸 어디에도 안 나타난다
    (사과 성숙 DOY 294~314 → 10/15=288, 11/15=319 둘 다 빗나감 → 수확 단계 소실). 그래서 일수
    우세로 판정한다. 단계가 없는 날은 경쟁에서 제외한다 — 월 대부분이 비어 있어도 그 달에 실제로
    존재하는 단계는 표기해야 하므로.
    """
    counts: dict[str, int] = {}  # 삽입순 유지 → 일수 동률이면 먼저 등장한 단계(결정론)
    for day in range(1, monthrange(year, month)[1] + 1):
        on_date = date(year, month, day)
        stage = pick_stage(
            stage_rows, on_date.timetuple().tm_yday, (on_date - planting_date).days
        )
        if stage is not None:
            counts[stage] = counts.get(stage, 0) + 1
    return max(counts, key=counts.__getitem__) if counts else None


def build_monthly_rows(
    stage_rows: Sequence[CropGrowthStage],
    all_guides: Sequence[CropGrowthGuide],
    clim_by_month: Mapping[int, WeatherClimatology],
    soil: SoilState | None,
    planting_date: date,
    year: int,
    corrections: Mapping[tuple[int, str], Decimal] | None = None,
) -> list[dict[str, object]]:
    """1~12월 각 월의 적합도를 계산한다. 순수 함수(DB 무관) — 결정론 검증 대상.

    토양은 월과 무관하게 밭의 현재 추정값을 12개월에 동일 적용한다. 월별 토양 변화 예측은
    P0 shadow 단계라 사용자 노출이 금지돼 있어 여기에 끌어오지 않는다(핸드오프 §12).
    """
    rows: list[dict[str, object]] = []
    stages = list(stage_rows)
    corr = dict(corrections or {})
    for month in range(1, 13):
        stage = dominant_stage(stages, planting_date, year, month)
        guides = _guides_for_stage(all_guides, stage)
        values, applied = apply_corrections(
            gather_indicator_values(soil, clim_by_month.get(month)), corr, month
        )
        result = calculate_suitability(guides, values, applied)
        rows.append(
            {
                "month": month,
                "growth_stage": stage,
                "status": derive_status(bool(guides), result["score"]),
                "score": result["score"],
                "grade": result["grade"],
                "risk_flags": result["risk_flags"],
                "outlook_applied": bool(applied),
            }
        )
    return rows


def compute_monthly_outlook(
    db: Session, user_id: int, farm_id: int, year: int
) -> dict[str, object]:
    """밭의 1~12월 '문헌 기반 예상 적합도' 전망(장기 탭 히트맵, `PRD.md` §4.4).

    단계·지침·평년치를 각각 1회만 읽고 12개월을 메모리에서 돌린다 — 월별 재조회 방지(§17).
    소유권은 compute_farm_suitability와 동일하게 user_id 스코프 404(§11).
    """
    farm = (
        db.query(UserFarm)
        .filter(UserFarm.user_id == user_id, UserFarm.id == farm_id)
        .first()
    )
    if farm is None:
        raise AppError(404, "FARM_NOT_FOUND", "밭을 찾을 수 없습니다.")

    stage_rows = list(
        db.query(CropGrowthStage).filter(CropGrowthStage.crop_id == farm.crop_id)
    )
    all_guides = list(
        db.scalars(select(CropGrowthGuide).where(CropGrowthGuide.crop_id == farm.crop_id))
    )
    soil = db.query(SoilState).filter(SoilState.user_farm_id == farm.id).first()
    clim_by_month = {
        c.month: c
        for c in db.query(WeatherClimatology).filter(
            WeatherClimatology.region_id == farm.region_id
        )
    }

    # 12개월 보정치를 1회 조회(월별 재조회 금지). read-time 적용이라 캐시하지 않는다.
    corrections = load_corrections(db, farm.region_id, list(range(1, 13)), year)
    months = build_monthly_rows(
        stage_rows, all_guides, clim_by_month, soil, farm.planting_date, year, corrections
    )

    limitations = [
        TEMP_DAY_LIMITATION,
        MONTHLY_CLIMATOLOGY_LIMITATION,
        MONTHLY_STAGE_LIMITATION,
        MONTHLY_SOIL_LIMITATION,
    ]
    limitations.append(
        OUTLOOK_APPLIED_LIMITATION
        if any(m["outlook_applied"] for m in months)
        else OUTLOOK_MISSING_LIMITATION
    )
    if any(m["growth_stage"] in ("coloring", "maturity") for m in months):
        limitations.append(APPLE_STAGE_LIMITATION)

    return {
        "farm_id": farm.id,
        "crop_id": farm.crop_id,
        "region_id": farm.region_id,
        "year": year,
        "label": SUITABILITY_LABEL,
        "months": months,
        "limitations": limitations,
    }
