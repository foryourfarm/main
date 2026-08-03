"""DB 생육 지침을 적용하는 결정론적 적합도 룰 엔진 + 밭 단위 조회 오케스트레이션."""
from calendar import monthrange
from math import log1p
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import CropGrowthGuide, CropGrowthStage, SoilState, UserFarm
from app.services.climatology_service import (
    ClimatologyMonth,
    ClimatologySource,
    lapse_limitation,
    load_climatology,
    substitution_limitation,
)
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
TEMP_DAY_LIMITATION = "일 기온(temp_day)은 실측이 아니라 월 평균기온 근사입니다."
# 사과 착색/성숙은 문헌이 한 구간이라 근사 분리(품종 정보 부재 → 이론 추정).
APPLE_STAGE_LIMITATION = "사과 착색/성숙 단계 구분은 품종 정보 부재로 이론 추정입니다."
# 상추 작기(0025)는 문헌이 아니라 일반적 노지 재배 시기에서 잡은 범위다. 숨기면 작기 밖
# "생육기 아님"이 문헌이 정한 사실처럼 읽힌다(§18-4).
LETTUCE_SEASON_LIMITATION = (
    "상추 봄(3~6월)·가을(8~11월) 작기 구분은 일반적인 노지 재배 시기 기준이며 "
    "문헌으로 확정된 범위가 아닙니다."
)

MONTHLY_CLIMATOLOGY_LIMITATION = (
    "월별 전망은 과거 기상 평균 기반 이론 추정이며 실제 예보가 아닙니다."
)
# 우리가 코드·DB에서 "평년치"(`*_normal`)라고 부르는 값은 기상청이 말하는 평년값이 아니다.
# 기상청 평년값은 30년(1991~2020) 통계인데 우리 것은 5년 관측 평균이다
# (`obs_mean_2021_2025`·`aws_mean_2021_2025` — scripts/load_weather_climatology.py,
# load_aws_climatology.py). 이름만 보고 30년 평년값으로 오해하기 쉬워 화면에 밝힌다(§18-4).
#
# 편차는 2026-08-02에 실측했다 — 같은 219지점끼리 `sfc_norm1.php`(tmst=2021)와 우리 관측을
# 월별로 맞대니 12개월 평균 +0.95℃, 월별로 −0.30(5월) ~ +2.04℃(9월)였다. 달마다 크게
# 다르므로 단일 상수로 뭉개지 않고 범위를 함께 적는다. 산출 근거는
# `docs/temperature-open-decisions.md` §① 참고.
CLIMATOLOGY_PERIOD_LIMITATION = (
    "기상값은 기상청 30년 평년값(1991~2020)이 아니라 최근 5년(2021~2025) 관측 평균입니다. "
    "30년 평년값보다 연평균 약 1℃ 따뜻하며 그 차이는 달마다 다릅니다(-0.3 ~ +2.0℃)."
)
MONTHLY_STAGE_LIMITATION = (
    "각 월의 생육단계는 그 달에 가장 많은 날을 차지한 단계로 표기합니다 — "
    "한 달에 두 단계가 걸치면 짧은 쪽은 표기되지 않습니다."
)
MONTHLY_SOIL_LIMITATION = (
    "토양 지표는 3개월 전체에 현재 추정값을 동일 적용합니다(월별 토양 변화는 반영하지 않음)."
)
OUTLOOK_APPLIED_LIMITATION = (
    "기온·강수는 과거 평균에 기상청 3개월전망(확률예보)을 반영해 보정했습니다. "
    "전망이 없는 월·지표(야간최저기온·일조 등)는 과거 평균을 그대로 씁니다."
)
OUTLOOK_MISSING_LIMITATION = (
    "기상청 3개월전망이 적재되지 않아 보정 없이 과거 평균만 사용했습니다."
)

# 지표 한글명. `risk_flags`의 `<지표>:missing`을 사람 말로 옮길 때 쓴다.
# 프론트 `types/farm.ts:INDICATOR_NAMES`와 같은 표기를 유지한다.
INDICATOR_NAMES: dict[str, str] = {
    "temp_day": "낮 기온",
    "temp_night_min": "야간 최저기온",
    "rainfall_monthly": "월 강수량",
    "rainfall_daily": "일 강수량",
    "sunlight": "일조",
    "ph": "토양 산도(pH)",
    "ec": "토양 염류(EC)",
    "p2o5": "유효인산",
    "organic": "유기물",
}


def coverage_limitation(breakdowns: Iterable[Mapping[str, Mapping[str, object]]]) -> str | None:
    """채점되지 않은 지표가 있으면 그 사실을 알린다(§18-4).

    점수는 채점된 지표만으로 가중평균한다. 지침 3개 중 1개만 값이 있으면 그 1개가 곧
    총점이 되어 "100점 S"가 나오는데, 화면에는 등급만 크게 보이고 나머지 2개가 빠졌다는
    사실은 어디에도 없었다 — 근사를 확정값처럼 보이게 하는 금지사항이다.
    `risk_flags`에 `<지표>:missing`이 이미 있지만 프론트는 `:outside_allowed`만 렌더한다.
    `limitations`는 모든 탭이 그대로 노출하므로 여기에 실어 한 곳에서 끝낸다.
    """
    missing: set[str] = set()
    scored: set[str] = set()
    for breakdown in breakdowns:
        for indicator, entry in breakdown.items():
            (scored if entry.get("score") is not None else missing).add(indicator)
    missing -= scored  # 어느 달에든 채점됐으면 결측이 아니다
    if not missing:
        return None
    names = "·".join(INDICATOR_NAMES.get(i, i) for i in sorted(missing))
    total = len(missing) + len(scored)
    # 지표명을 조사 앞에 두면 받침에 따라 은/는이 갈린다 — 목록을 문장 끝에 둬서 피한다.
    return (
        f"지침 지표 {total}개 중 {len(scored)}개로만 채점한 점수입니다. "
        f"데이터가 없어 반영되지 않은 지표: {names}."
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


# 장기 탭에 데이터원이 없는 지표. 평년치는 월 단위라 일 강수량이 채워질 길이 없는데
# 지침에는 전기간 공통으로 들어 있어, 전 작물이 `rainfall_daily:missing`을 영구히 달고
# 다녔다. 단기 탭은 반대 방향(`DAILY_UNAVAILABLE_INDICATORS`)을 이미 걸러내고 있다.
SEASONAL_UNAVAILABLE_INDICATORS = frozenset({"rainfall_daily"})


def usable_seasonal(guide: CropGrowthGuide) -> bool:
    """장기(평년치) 채점에 쓸 수 있는 지침인지. `_usable_daily`의 대칭."""
    return guide.indicator not in SEASONAL_UNAVAILABLE_INDICATORS


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
    # 단측 밴드(outcomes/scripts/ml/scoring.py band_score()와 같은 계약, 2026-08-03):
    # optimal_min/optimal_max 중 하나가 None이면 그 방향엔 감점을 두지 않는다. 문헌이
    # 한쪽 경계만 주는 지표(예: 사과 치환성 Ca "5~6cmol/kg 이상")를 위한 것 — 없는 상한을
    # 휴리스틱으로 만들면 정상 토양을 근거 없이 감점하게 된다(추측 금지, CLAUDE.md §2).
    lo = None if guide.optimal_min is None else float(guide.optimal_min)
    hi = None if guide.optimal_max is None else float(guide.optimal_max)
    # 지침에 감쇠폭이 있으면 위험구간 척도로 쓴다(없으면 _risk_score가 완충폭으로 폴백).
    risk_width = None if guide.risk_width is None else float(guide.risk_width)
    if (lo is None or lo <= value) and (hi is None or value <= hi):
        return 100.0, "optimal"
    if lo is not None and value < lo:
        if guide.allowed_min is None:
            return 0.0, "risk"
        edge = float(guide.allowed_min)
        if value >= edge:
            return _allowed_score((value - edge) / (lo - edge)), "allowed"
        return _risk_score(edge - value, lo - edge, risk_width), "risk"
    # 여기 도달했다는 건 hi가 None이 아니고 value > hi라는 뜻이다(위 optimal 체크 참고).
    if guide.allowed_max is None:
        return 0.0, "risk"
    edge = float(guide.allowed_max)
    if value <= edge:
        return _allowed_score((edge - value) / (edge - hi)), "allowed"
    return _risk_score(value - edge, edge - hi, risk_width), "risk"


def _is_valid(indicator: str, value: float) -> bool:
    if indicator == "ph":
        return 0 <= value <= 14
    # ec·k·ca·mg는 물리적으로 음수가 될 수 없다. 0024·0028로 채점 대상이 되면서
    # 다른 토양 지표와 같은 하한 검증이 필요해졌다(§12 경계에서 방어).
    if indicator in {
        "rainfall_monthly",
        "rainfall_daily",
        "p2o5",
        "organic",
        "ec",
        "k",
        "ca",
        "mg",
    }:
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
        # 단측 밴드(2026-08-03)에서 optimal_min·optimal_max 중 하나만 None인 건 정상
        # 계약이다 — 둘 다 없을 때만 채점 불가(outcomes/scripts/ml/scoring.py band_score()와
        # 같은 기준). 예전엔 하나만 없어도 여기서 걸러 사과 Ca 같은 단측 지표를 통째로
        # 스킵시켰다.
        if guide.optimal_min is None and guide.optimal_max is None:
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
            # 허용구간을 함께 싣는다 — "왜 위험인가"를 값만으로는 말할 수 없다. 행동추천이
            # "야간 최저 2.1℃(허용 5℃ 밖)"처럼 기준과 함께 서술하려면 이 값이 필요하고,
            # 지침을 두 곳에서 각자 읽으면 어긋난다(§18-2는 기준값 하드코딩 금지).
            "allowed_min": float(guide.allowed_min) if guide.allowed_min is not None else None,
            "allowed_max": float(guide.allowed_max) if guide.allowed_max is not None else None,
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
    clim: ClimatologyMonth | None,
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
        # 치환성 양이온(cmol/kg, 0024). 사과·배·상추만 지침이 있고 나머지 작물은
        # 지침이 없어 룰 엔진이 알아서 제외한다 — 값을 넣어도 채점 대상이 되지 않는다.
        "k": soil.k if soil else None,
        "ca": soil.ca if soil else None,
        "mg": soil.mg if soil else None,
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
    guides = [g for g in load_guides(db, farm.crop_id, stage or "") if usable_seasonal(g)]
    soil = db.query(SoilState).filter(SoilState.user_farm_id == farm.id).first()
    # 평년치가 없는 지역은 격자상 최근접 지역 값으로 대체하고 그 사실을 표기한다(§8.5).
    # 밭의 읍면동을 넘겨 기온을 고도 감률 보정한다 — 평년치는 시군구 단위인데 밭 위치는
    # 읍면동까지 안다(토양 때문에 이미 그 해상도로 받고 있다).
    clim_source = load_climatology(db, farm.region_id, farm.bjd_code)
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

    limitations = [TEMP_DAY_LIMITATION, CLIMATOLOGY_PERIOD_LIMITATION]
    coverage = coverage_limitation([result["breakdown"]])
    if coverage is not None:
        limitations.insert(0, coverage)
    substitution = substitution_limitation(clim_source)
    if substitution is not None:
        limitations.insert(0, substitution)
    lapse = lapse_limitation(clim_source)
    if lapse is not None:
        limitations.insert(0, lapse)
    limitations.append(OUTLOOK_APPLIED_LIMITATION if applied else OUTLOOK_MISSING_LIMITATION)
    if stage in ("coloring", "maturity"):
        limitations.append(APPLE_STAGE_LIMITATION)
    if stage in ("spring", "fall"):
        limitations.append(LETTUCE_SEASON_LIMITATION)

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
    return [
        g
        for g in all_guides
        if (g.growth_stage == stage or g.growth_stage is None) and usable_seasonal(g)
    ]


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


# 장기 탭이 보여주는 달 수. 3개월전망(tercile)이 평년치를 넘어서는 유일한 신호라 그 지평에
# 맞춘다 — 더 멀리 계산하면 평년치만으로 낸 값이 전망 반영 칸과 같은 등급으로 보인다(§18-4).
# 명세: PRD.md §4.4.
OUTLOOK_WINDOW_MONTHS = 3

# 창이 전부 휴면기일 때 다음 생육기를 찾아 앞으로 훑는 최대 개월 수. 12면 연중 어느 시점에서
# 조회해도 반드시 한 바퀴를 돌아 답을 준다.
NEXT_SEASON_SEARCH_MONTHS = 12


def outlook_window(today: date, size: int = OUTLOOK_WINDOW_MONTHS) -> list[tuple[int, int]]:
    """오늘이 속한 달부터 size개월 `[(연도, 월), ...]`.

    **달력이 창을 정하고 전망은 그 위에 얹는다**(PRD §4.4). 전망이 커버하는 달을 그대로
    쓰면 매월 23일 발표 때 창이 한 칸 점프해 **지금 농사 중인 이번 달이 사라진다**
    (8/22엔 8·9·10월, 8/24엔 9·10·11월). 그래서 오늘에 고정한다.

    이번 달도 전망을 잃지 않는다 — `load_corrections`가 대상월마다 따로 최신 발표분을
    고르므로 이번 달은 직전 발표분에서 온다.
    """
    out: list[tuple[int, int]] = []
    for step in range(size):
        total = today.month - 1 + step
        out.append((today.year + total // 12, total % 12 + 1))
    return out


def next_season_month(
    stage_rows: Sequence[CropGrowthStage],
    planting_date: date,
    after: tuple[int, int],
    limit: int = NEXT_SEASON_SEARCH_MONTHS,
) -> tuple[int, int] | None:
    """`after` 다음 달부터 생육 단계가 잡히는 첫 달. 못 찾으면 None.

    창이 전부 휴면기일 때 "다음 생육기는 언제인가"를 알려주기 위한 것이다. 창 자체를 늘려
    생육기까지 당겨오지는 않는다 — 전망 없는 달을 채우게 되기 때문이다(PRD §4.4).
    """
    stages = list(stage_rows)
    year, month = after
    for _ in range(limit):
        total = month  # 다음 달부터 본다(month는 1-based라 그대로 더하면 +1)
        year, month = year + total // 12, total % 12 + 1
        if dominant_stage(stages, planting_date, year, month) is not None:
            return (year, month)
    return None


def build_monthly_rows(
    stage_rows: Sequence[CropGrowthStage],
    all_guides: Sequence[CropGrowthGuide],
    clim_by_month: Mapping[int, ClimatologyMonth],
    soil: SoilState | None,
    planting_date: date,
    window: Sequence[tuple[int, int]],
    corrections: Mapping[tuple[int, int, str], Decimal] | None = None,
    clim_source: ClimatologySource | None = None,
    published_by_month: Mapping[tuple[int, int], datetime] | None = None,
) -> list[dict[str, object]]:
    """창의 각 달 적합도를 계산한다. 순수 함수(DB 무관) — 결정론 검증 대상.

    `window`는 `[(연도, 월), ...]`다. **연도를 월과 함께 다루는 이유**: 창이 해를 넘기므로
    (11월 조회 → 11·12·1월) 월만으로는 평년치·보정치를 짚을 수 없다. 평년치(`clim_by_month`)는
    연도와 무관한 월별 값이라 월로 조회하지만, 보정치는 연도까지 키로 쓴다.

    토양은 월과 무관하게 밭의 현재 추정값을 창 전체에 동일 적용한다. 월별 토양 변화 예측은
    P0 shadow 단계라 사용자 노출이 금지돼 있어 여기에 끌어오지 않는다(핸드오프 §12).

    clim_source를 받는 이유: 일조시간은 clim_source에서만 나온다. 이걸 빼면 히트맵(월별)과
    일별 적합도가 같은 달의 일조를 서로 다르게 채점한다 — 두 화면이 어긋난다.
    """
    rows: list[dict[str, object]] = []
    stages = list(stage_rows)
    corr = dict(corrections or {})
    published = dict(published_by_month or {})
    for year, month in window:
        stage = dominant_stage(stages, planting_date, year, month)
        guides = _guides_for_stage(all_guides, stage)
        values, applied = apply_corrections(
            gather_indicator_values(soil, clim_by_month.get(month), clim_source, month),
            corr,
            year,
            month,
        )
        result = calculate_suitability(guides, values, applied)
        status = derive_status(bool(guides), result["score"], result["breakdown"])
        # 휴면기(기상 판정 근거 없음)는 점수·등급을 내보내지 않는다 — §18-4.
        is_dormant = status == "dormant"
        rows.append(
            {
                "year": year,
                "month": month,
                "growth_stage": stage,
                "status": status,
                "score": None if is_dormant else result["score"],
                "grade": None if is_dormant else result["grade"],
                "risk_flags": result["risk_flags"],
                "outlook_applied": bool(applied),
                # 칸마다 다른 발표분에서 올 수 있다 — 최상위에 하나로 두면 반드시 한쪽이
                # 틀린다(최상위 year를 뺀 것과 같은 이유). 보정이 없으면 None.
                "outlook_published_at": published.get((year, month)) if applied else None,
                # 내부용 — 창 커버리지 집계(`coverage_limitation`)에만 쓴다.
                # 응답 스키마(`MonthlyOutlookEntry`)에 없으므로 직렬화에서 빠진다.
                "breakdown": result["breakdown"],
            }
        )
    return rows


def compute_monthly_outlook(
    db: Session, user_id: int, farm_id: int, today: date
) -> dict[str, object]:
    """밭의 **다가오는 3개월** '문헌 기반 예상 적합도'(장기 탭 히트맵, `PRD.md` §4.4).

    창은 오늘이 속한 달부터 3개월이고 해를 넘길 수 있다 — 그래서 연도가 아니라 `today`를
    받는다(테스트에서 연말 시나리오를 주입할 수 있게 하는 목적도 겸한다).

    단계·지침·평년치를 각각 1회만 읽고 창을 메모리에서 돌린다 — 월별 재조회 방지(§17).
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
    # 밭의 읍면동을 넘겨 기온을 고도 감률 보정한다 — 평년치는 시군구 단위인데 밭 위치는
    # 읍면동까지 안다(토양 때문에 이미 그 해상도로 받고 있다).
    clim_source = load_climatology(db, farm.region_id, farm.bjd_code)
    clim_by_month = clim_source.by_month

    window = outlook_window(today)
    # 창 전체 보정치를 1회 조회(월별 재조회 금지). read-time 적용이라 캐시하지 않는다.
    corrections, published_by_month = load_corrections(db, farm.region_id, window)
    months = build_monthly_rows(
        stage_rows,
        all_guides,
        clim_by_month,
        soil,
        farm.planting_date,
        window,
        corrections,
        clim_source,
        published_by_month,
    )

    limitations = [
        TEMP_DAY_LIMITATION,
        MONTHLY_CLIMATOLOGY_LIMITATION,
        CLIMATOLOGY_PERIOD_LIMITATION,
        MONTHLY_STAGE_LIMITATION,
        MONTHLY_SOIL_LIMITATION,
    ]
    coverage = coverage_limitation(m["breakdown"] for m in months)
    if coverage is not None:
        limitations.insert(0, coverage)
    substitution = substitution_limitation(clim_source)
    if substitution is not None:
        limitations.insert(0, substitution)
    lapse = lapse_limitation(clim_source)
    if lapse is not None:
        limitations.insert(0, lapse)
    limitations.append(
        OUTLOOK_APPLIED_LIMITATION
        if any(m["outlook_applied"] for m in months)
        else OUTLOOK_MISSING_LIMITATION
    )
    if any(m["growth_stage"] in ("coloring", "maturity") for m in months):
        limitations.append(APPLE_STAGE_LIMITATION)
    if any(m["growth_stage"] in ("spring", "fall") for m in months):
        limitations.append(LETTUCE_SEASON_LIMITATION)
    # 창이 전부 비었으면 화면이 통째로 "제철 아님"이라 유저가 다음에 언제 보러 와야 할지
    # 알 수 없다. 창을 늘려 채우지 않고 문구로만 알린다(PRD §4.4).
    if all(m["growth_stage"] is None for m in months):
        following = next_season_month(stage_rows, farm.planting_date, window[-1])
        if following is not None:
            limitations.insert(
                0, f"이 작물은 {following[0]}년 {following[1]}월부터 생육기가 시작됩니다."
            )

    return {
        "farm_id": farm.id,
        "crop_id": farm.crop_id,
        "region_id": farm.region_id,
        "label": SUITABILITY_LABEL,
        "months": months,
        "limitations": limitations,
    }
