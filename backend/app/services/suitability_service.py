"""DB 생육 지침을 적용하는 결정론적 적합도 룰 엔진 + 밭 단위 조회 오케스트레이션."""
from calendar import monthrange
from math import log1p
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import CropGrowthGuide, CropGrowthStage, SoilState, UserFarm, WeatherClimatology
from app.services.climatology_service import ClimatologySource, load_climatology, substitution_limitation
from app.services.growth_stage_service import pick_stage, resolve_growth_stage
from app.services.outlook_correction import apply_corrections, load_corrections

ALLOWED_BOUNDARY_SCORE = 60.0  # 승인됨: B등급 하한(60)을 허용구간 끝점 점수로 사용.
# 최적구간을 벗어나는 순간의 점수. 100에서 이어지지 않고 여기서 시작한다 — "최적 이탈" 자체에
# 붙는 고정 감점(5점)이라 경계를 넘었다는 사실이 점수에 바로 드러난다. 2026-07-27 사용자 지정.
OPTIMAL_EXIT_SCORE = 95.0
# 로그 감쇠 곡률. 9면 ln(1+9x)/ln(10) → x=1에서 1, x=0에서 0. 1 근처는 완만, 0 근처는 급하다.
# 허용구간(완만→급락)과 위험구간(급락→완만)에 같은 곡률을 반대로 걸어 전체가 정규분포
# 한쪽 날개 모양이 된다. 2026-07-27 사용자 선택(선형·이차·로그 중 로그).
DECAY_CURVATURE = 9.0

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
    # 강수는 단위별로 지표를 나눈다 — 월평년(mm/월)과 예보 일누적(mm/일)을 한 지표로
    # 묶었다가 "비 안 온 날(0mm)"이 위험으로 판정되는 버그가 있었다(0011 참조).
    "rainfall_monthly": "rainfall_normal",
    "rainfall_daily": None,  # 단기 탭 전용 — weather_snapshot.rainfall
    "sunlight": "sunlight_normal",
    "ph": "ph",
    "ec": "ec",
    "p2o5": "p2o5",
    "organic": "organic_matter",
    # 치환성 양이온(cmol+/kg, 0023). 지침이 있는 작물만 채점된다 — 현재는 상추뿐.
    "k": "k",
    "ca": "ca",
    "mg": "mg",
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


def _log_falloff(x: float) -> float:
    """x=1 → 1, x=0 → 0인 로그 계수. 1 근처는 평평하고 0 근처에서 가파르다."""
    return log1p(DECAY_CURVATURE * x) / log1p(DECAY_CURVATURE)


def _allowed_score(nearness: float) -> float:
    """허용구간 점수. `nearness`는 최적경계에 얼마나 가까운지(1=최적경계, 0=허용경계).

    최적 근처에서는 거의 안 깎이고 허용경계에 다가갈수록 가파르게 떨어진다 — 소폭 이탈은
    실제로 해가 적고 내성 한계에 가까울수록 위험이 커진다는 쪽에 맞춘 곡선.
    """
    return ALLOWED_BOUNDARY_SCORE + (OPTIMAL_EXIT_SCORE - ALLOWED_BOUNDARY_SCORE) * _log_falloff(
        nearness
    )


def _risk_score(overshoot: float, buffer: float, risk_width: float | None = None) -> float:
    """허용구간을 벗어난 뒤 60 → 0으로 떨어지는 로그 감쇠 점수.

    절벽(경계 넘자마자 0)은 "1도 초과"와 "10도 초과"를 똑같이 취급해 위험의 정도를 못 보여준다.
    허용구간과 곡률을 반대로 걸어(여기는 급락 후 완만) 전체가 정규분포 한쪽 날개처럼 이어진다.

    감쇠폭(2026-07-29 개정): 종전엔 완충폭(허용~최적 간격) 1배를 감쇠 거리로 썼다. 완충폭은
    `allowed = optimal 폭 ±50%` 휴리스틱에서 나오므로 optimal이 좁은 지표는 완충폭도, 위험
    구간도 함께 좁아졌다 — 3중 압축이라 채점이 사실상 이진이 됐다(outcomes 150지역 측정:
    상추 pH 0점 107건, 사과 기온 0점 92건). 이제 지침의 `risk_width`(그 지표의 전국 실측
    산포도 기반 절대폭, 마이그레이션 0020)가 있으면 그것을 감쇠 거리로 쓴다.
    없으면 종전대로 완충폭 1배로 폴백한다 — 산포도를 낼 수 없는 지표(temp_night_min,
    rainfall_daily)에서 척도를 지어내지 않는다. 둘 다 없으면 종전대로 0점.
    """
    width = risk_width if risk_width and risk_width > 0 else buffer
    if width <= 0:
        return 0.0
    t = overshoot / width
    if t >= 1:
        return 0.0
    return ALLOWED_BOUNDARY_SCORE * (1 - _log_falloff(t))


def _indicator_score(value: float, guide: CropGrowthGuide) -> tuple[float, str]:
    lo, hi = float(guide.optimal_min), float(guide.optimal_max)
    # 지침에 감쇠폭이 있으면 위험구간 척도로 쓴다(없으면 _risk_score가 완충폭으로 폴백).
    risk_width = None if guide.risk_width is None else float(guide.risk_width)
    if lo <= value <= hi:
        return 100.0, "optimal"
    if value < lo:
        if guide.allowed_min is None:
            return 0.0, "risk"
        edge = float(guide.allowed_min)
        if value >= edge:
            return _allowed_score((value - edge) / (lo - edge)), "allowed"
        return _risk_score(edge - value, lo - edge, risk_width), "risk"
    if guide.allowed_max is None:
        return 0.0, "risk"
    edge = float(guide.allowed_max)
    if value <= edge:
        return _allowed_score((edge - value) / (edge - hi)), "allowed"
    return _risk_score(value - edge, edge - hi, risk_width), "risk"


def _is_valid(indicator: str, value: float) -> bool:
    if indicator == "ph":
        return 0 <= value <= 14
    if indicator in {"rainfall_monthly", "rainfall_daily", "p2o5", "organic", "k", "ca", "mg"}:
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
        # 근거·신뢰도를 함께 내려 UI가 표현 강도를 조절할 수 있게 한다(§18-4).
        if guide.confidence is not None:
            entry["confidence"] = guide.confidence
        if guide.source_ref is not None:
            entry["source_ref"] = guide.source_ref
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
    soil: SoilState | None,
    clim: WeatherClimatology | None,
    clim_source: ClimatologySource | None = None,
    month: int | None = None,
) -> dict[str, float | Decimal | None]:
    """지표 값을 데이터원에서 모은다. 토양은 밭 실측 추정, 기상은 지역 월평년.

    temp_day는 월평년 근사(승인됨). 결측은 None으로 두고 룰 엔진이 제외한다(§12 결측 방어).
    일조시간은 clim_source에서 계산된 값을 우선 사용한다(실측/계산, 정확도 >= 0.90만).
    """
    # 일조시간: 계산된 값 우선 (정확도 >= 0.90만), 없으면 DB 값
    sunlight_value = None
    if clim_source and month and clim_source.sunlight_by_month:
        sunlight_result = clim_source.sunlight_by_month.get(month)
        if sunlight_result:
            sunlight_value = sunlight_result.value
    if sunlight_value is None and clim:
        sunlight_value = clim.sunlight_normal

    return {
        "temp_day": clim.temp_avg_normal if clim else None,  # 월평년 근사
        "temp_night_min": clim.temp_night_min_normal if clim else None,
        "rainfall_monthly": clim.rainfall_normal if clim else None,
        "sunlight": sunlight_value,
        "ph": soil.ph if soil else None,
        "ec": soil.ec if soil else None,
        "p2o5": soil.p2o5 if soil else None,
        "organic": soil.organic_matter if soil else None,
    }


# 기상 기반 지표. 이 중 하나도 채점되지 않았다면 그 달 점수는 계절 적합도가 아니라
# 토양 점수일 뿐이다(§8.4 판정 대상이 없음).
WEATHER_INDICATORS = frozenset(
    {"temp_day", "temp_night_min", "rainfall_monthly", "rainfall_daily", "sunlight"}
)


def derive_status(
    has_guides: bool,
    score: float | None,
    breakdown: Mapping[str, Mapping[str, object]] | None = None,
) -> str:
    """적합도 결과의 상태.

    - `out_of_season`: 해당 단계 지침이 아예 없음(예: 배 겨울).
    - `insufficient_data`: 지침은 있으나 지표가 전부 결측/이상.
    - `dormant`: 기상 지표가 하나도 채점되지 않음 — 토양 지침만 걸린 달(예: 사과 1월).
      점수를 그대로 노출하면 "1월이 사과에 최적(100점 S)"으로 읽혀 근사를 확정값처럼
      보이게 한다(§18-4). 계절 판정 근거가 없으므로 점수를 내보내지 않는다.
    - `ok`: 기상 판정이 포함된 정상 산출.
    """
    if not has_guides:
        return "out_of_season"
    if score is None:
        return "insufficient_data"
    if breakdown is not None:
        scored_weather = [
            ind
            for ind, entry in breakdown.items()
            if ind in WEATHER_INDICATORS and entry.get("score") is not None
        ]
        if not scored_weather:
            return "dormant"
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
    # 평년치가 없는 지역은 격자상 최근접 지역 값으로 대체하고 그 사실을 표기한다(§8.5).
    clim_source = load_climatology(db, farm.region_id)
    clim = clim_source.by_month.get(on_date.month)

    # 장기예보 보정은 read-time에만 얹는다(캐시 금지 — §3.13 B1).
    corrections = load_corrections(db, farm.region_id, [on_date.month], on_date.year)
    values, applied = apply_corrections(
        gather_indicator_values(soil, clim, clim_source, on_date.month),
        corrections,
        on_date.month,
    )
    result = calculate_suitability(guides, values, applied)
    status = derive_status(bool(guides), result["score"], result["breakdown"])

    # 일조시간 메타데이터 추가 (계산값인 경우 FE에서 작게 표시)
    # `clim` 여부는 여기서 볼 게 아니다 — 일조 메타는 sunlight_by_month에만 달려 있다.
    if on_date.month in clim_source.sunlight_by_month:
        sunlight_result = clim_source.sunlight_by_month[on_date.month]
        if "sunlight" in result["breakdown"] and result["breakdown"]["sunlight"].get("score") is not None:
            result["breakdown"]["sunlight"]["method"] = sunlight_result.method
            result["breakdown"]["sunlight"]["is_calculated"] = sunlight_result.is_calculated
            if sunlight_result.is_calculated:
                result["breakdown"]["sunlight"]["confidence"] = sunlight_result.confidence

    limitations = [TEMP_DAY_LIMITATION]
    substitution = substitution_limitation(clim_source)
    if substitution is not None:
        limitations.insert(0, substitution)
    limitations.append(OUTLOOK_APPLIED_LIMITATION if applied else OUTLOOK_MISSING_LIMITATION)
    if stage in ("coloring", "maturity"):
        limitations.append(APPLE_STAGE_LIMITATION)

    # 휴면기는 기상 판정 근거가 없어 점수를 내보내지 않는다(§18-4). breakdown은 남겨
    # 토양 지표가 어떻게 평가됐는지는 확인할 수 있게 한다.
    is_dormant = status == "dormant"

    return {
        "farm_id": farm.id,
        "crop_id": farm.crop_id,
        "region_id": farm.region_id,
        "growth_stage": stage,
        "as_of": on_date,
        "status": status,
        "score": None if is_dormant else result["score"],
        "grade": None if is_dormant else result["grade"],
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
    clim_source: ClimatologySource | None = None,
) -> list[dict[str, object]]:
    """1~12월 각 월의 적합도를 계산한다. 순수 함수(DB 무관) — 결정론 검증 대상.

    토양은 월과 무관하게 밭의 현재 추정값을 12개월에 동일 적용한다. 월별 토양 변화 예측은
    P0 shadow 단계라 사용자 노출이 금지돼 있어 여기에 끌어오지 않는다(핸드오프 §12).

    clim_source를 받는 이유: 일조시간은 clim_source에서만 나온다. 이걸 빼면 히트맵(월별)과
    일별 적합도가 같은 달의 일조를 서로 다르게 채점한다 — 두 화면이 어긋난다.
    """
    rows: list[dict[str, object]] = []
    stages = list(stage_rows)
    corr = dict(corrections or {})
    for month in range(1, 13):
        stage = dominant_stage(stages, planting_date, year, month)
        guides = _guides_for_stage(all_guides, stage)
        values, applied = apply_corrections(
            gather_indicator_values(soil, clim_by_month.get(month), clim_source, month),
            corr,
            month,
        )
        result = calculate_suitability(guides, values, applied)
        status = derive_status(bool(guides), result["score"], result["breakdown"])
        # 휴면기(기상 판정 근거 없음)는 점수·등급을 내보내지 않는다 — §18-4.
        is_dormant = status == "dormant"
        rows.append(
            {
                "month": month,
                "growth_stage": stage,
                "status": status,
                "score": None if is_dormant else result["score"],
                "grade": None if is_dormant else result["grade"],
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
    clim_source = load_climatology(db, farm.region_id)
    clim_by_month = clim_source.by_month

    # 12개월 보정치를 1회 조회(월별 재조회 금지). read-time 적용이라 캐시하지 않는다.
    corrections = load_corrections(db, farm.region_id, list(range(1, 13)), year)
    months = build_monthly_rows(
        stage_rows,
        all_guides,
        clim_by_month,
        soil,
        farm.planting_date,
        year,
        corrections,
        clim_source,
    )

    limitations = [
        TEMP_DAY_LIMITATION,
        MONTHLY_CLIMATOLOGY_LIMITATION,
        MONTHLY_STAGE_LIMITATION,
        MONTHLY_SOIL_LIMITATION,
    ]
    substitution = substitution_limitation(clim_source)
    if substitution is not None:
        limitations.insert(0, substitution)
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
