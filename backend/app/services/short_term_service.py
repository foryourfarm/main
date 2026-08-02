"""단기 탭 — 예보 조회·캐시 + 날짜별 위험신호 판정 (PRD.md §4.5, DB.md §8.4).

위험 임계치를 새로 만들지 않는다. `crop_growth_guide`의 허용구간(allowed_min/max)이 이미
작물×단계별 위험 경계이므로, 장기 탭과 **같은 룰 엔진**에 예보값을 넣어 판정한다.
새 기준값을 코드에 박으면 §18-2 위반이고 장기/단기 판정이 어긋난다.

A씨 사례(봄철 야간저온으로 활착 실패)가 이 탭의 존재 이유다 — 그래서 단일 시점이 아니라
날짜별로 판정하고 **연속 지속**을 따로 표시한다(§7-4 시계열 요구).
"""

from datetime import date, datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infra.public_api.forecast_client import (
    DailyForecast,
    ForecastError,
    fetch_forecast,
    latest_base_at,
)
from app.models import CropGrowthGuide, RegionGrid, SoilState, UserFarm, WeatherSnapshot
from app.services.growth_stage_service import resolve_growth_stage
from app.services.suitability_service import (
    SUITABILITY_LABEL,
    WEATHER_INDICATORS,
    calculate_suitability,
    coverage_limitation,
    derive_status,
    load_guides,
)

KIND_FORECAST = "FORECAST"

FORECAST_LIMITATION = (
    "기상청 단기예보 기반입니다(발표시각 기준 약 3일치, 달력상 4~5일에 걸칠 수 있음). "
    "실측이 아니라 예보이며 발표마다 바뀝니다."
)
STALE_LIMITATION = (
    "예보 조회에 실패해 직전에 받아둔 값을 사용했습니다 — 최신이 아닐 수 있습니다."
)
# **"행위 영향을 반영한"을 다시 넣지 말 것.** 반영하는 코드가 없다 — soil_delta는 shadow
# 전용이라 predict_soil_delta를 부르는 유저 경로가 0건이고, artifact 경로도 비어 Δ=0 폴백이며,
# soil_change_rule 테이블은 프로덕션에서 0행에 읽는 코드도 0건이다. 아래 gather_indicator_values는
# SoilState를 그대로 읽는다. 없는 기능을 있다고 말하면 §18-4를 거꾸로 위반한다 —
# 초보자가 "내 작업이 반영된 내 땅 수치"로 믿게 되므로 과소 표기보다 나쁘다.
#
# "읍면동"도 쓰지 않는다. 등록 단위가 법정동 말단이라 리로 등록된 밭은 리 기준값이다
# (설정 화면의 soil_source는 동적으로 정확히 표기한다 — 이 상수는 그걸 따라가지 못한다).
SOIL_LIMITATION = (
    "토양 지표는 밭이 속한 동·리의 토양검정 표본 평균입니다 — 이 밭 흙을 직접 측정한 값이 "
    "아니고, 그동안의 시비·관수 등 작업 영향도 반영되지 않습니다."
)


def _to_snapshot_rows(
    region_id: int, base_at: datetime, days: list[DailyForecast]
) -> list[dict[str, object]]:
    return [
        {
            "region_id": region_id,
            "kind": KIND_FORECAST,
            "base_at": base_at,
            "target_date": d.target_date,
            "temp_avg": d.temp_avg,
            "temp_night_min": d.temp_night_min,
            "rainfall": d.rainfall,
            "sunlight": None,  # 단기예보는 일조를 주지 않는다
            "is_imputed": False,
        }
        for d in days
    ]


def _cached_rows(db: Session, region_id: int, since: date) -> list[WeatherSnapshot]:
    """가장 최근 발표분의 예보 캐시. 없으면 빈 리스트."""
    latest = (
        db.query(WeatherSnapshot.base_at)
        .filter(
            WeatherSnapshot.region_id == region_id,
            WeatherSnapshot.kind == KIND_FORECAST,
        )
        .order_by(WeatherSnapshot.base_at.desc())
        .first()
    )
    if latest is None:
        return []
    return list(
        db.query(WeatherSnapshot)
        .filter(
            WeatherSnapshot.region_id == region_id,
            WeatherSnapshot.kind == KIND_FORECAST,
            WeatherSnapshot.base_at == latest[0],
            WeatherSnapshot.target_date >= since,
        )
        .order_by(WeatherSnapshot.target_date)
    )


def get_forecast_rows(
    db: Session, region_id: int, service_key: str, today: date, now: datetime
) -> tuple[list[WeatherSnapshot], bool]:
    """(예보 행, is_stale). 캐시가 신선하면 그대로, 아니면 조회 후 upsert.

    조회 실패 시 마지막 캐시를 쓰고 is_stale=True로 알린다 — 외부 장애가 화면을 죽이지
    않게 한다(§12). 캐시도 없으면 빈 리스트.
    """
    # 신선도는 벽시계 TTL이 아니라 "최신 발표분을 갖고 있나"로 판정한다. 발표 주기가
    # 3시간이라 3시간 TTL은 발표 사이 구간에서 항상 만료돼, 같은 발표분을 매 요청마다
    # 다시 조회했다(§18-1 무분별 호출). 발표시각 비교는 외부 호출 없이 끝난다.
    cached = _cached_rows(db, region_id, today)
    if cached and cached[0].base_at >= latest_base_at(now):
        return cached, False

    grid = db.query(RegionGrid).filter(RegionGrid.region_id == region_id).first()
    if grid is None:
        # 격자 매핑이 없으면 예보를 부를 수 없다. 조용히 0점 내지 않고 결측으로 둔다.
        return cached, bool(cached)

    try:
        days, base_at = fetch_forecast(service_key, grid.nx, grid.ny, now=now)
    except ForecastError:
        return cached, bool(cached)

    rows = _to_snapshot_rows(region_id, base_at, days)
    if rows:
        stmt = insert(WeatherSnapshot).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_weather",
            set_={
                "temp_avg": stmt.excluded.temp_avg,
                "temp_night_min": stmt.excluded.temp_night_min,
                "rainfall": stmt.excluded.rainfall,
                "sunlight": stmt.excluded.sunlight,
            },
        )
        db.execute(stmt)
        db.commit()
    return _cached_rows(db, region_id, today), False


def forecast_values(
    snap: WeatherSnapshot, soil: SoilState | None
) -> dict[str, object]:
    """룰 엔진 입력. 기상은 예보값, 토양은 밭 추정값.

    강수는 **일 단위 지표(rainfall_daily)** 에 넣는다 — 예보는 일누적이고 장기 탭의
    월평년(rainfall_monthly)과 단위가 달라, 한 지표로 묶으면 비 안 온 날(0mm)이 위험으로
    판정된다(0011에서 분리).
    """
    return {
        "temp_day": snap.temp_avg,
        "temp_night_min": snap.temp_night_min,
        "rainfall_daily": snap.rainfall,
        "sunlight": snap.sunlight,
        "ph": soil.ph if soil else None,
        "ec": soil.ec if soil else None,
        "p2o5": soil.p2o5 if soil else None,
        "organic": soil.organic_matter if soil else None,
        "k": soil.k if soil else None,
        "ca": soil.ca if soil else None,
        "mg": soil.mg if soil else None,
    }


# 단기 탭에서는 값이 생길 수 없는 지표. 월 단위 지표를 그대로 두면 매일 "결측"으로 떠
# 위험목록을 오염시킨다(점수 계산에는 영향 없지만 노이즈).
DAILY_UNAVAILABLE_INDICATORS = frozenset({"rainfall_monthly", "sunlight"})


def _usable_daily(guide: CropGrowthGuide) -> bool:
    return guide.indicator not in DAILY_UNAVAILABLE_INDICATORS


def persistent_risks(days: list[dict[str, object]], min_days: int = 2) -> list[dict[str, object]]:
    """연속으로 반복되는 **기상** 위험만 골라낸다 — "야간 저온 3일 지속"이 A씨 사례의 핵심이다.

    토양 지표는 제외한다. 토양은 며칠 안에 변하지 않아 위험이면 매일 똑같이 뜨는데,
    이를 "5일 지속 위험"으로 올리면 정보가 없는 경보가 되고 정작 봐야 할 기상 위험을
    가린다. 토양 상태는 날짜별 risk_flags와 장기 탭에서 확인한다.

    순수 함수. 하루짜리 노이즈와 지속 위험을 구분하는 규칙을 테스트로 고정한다.
    """
    streaks: dict[str, list[str]] = {}
    for day in days:
        flags = {
            str(f)
            for f in day["risk_flags"]  # type: ignore[union-attr]
            if str(f).endswith(":outside_allowed")
            and str(f).split(":")[0] in WEATHER_INDICATORS
        }
        for flag in flags:
            streaks.setdefault(flag, []).append(str(day["target_date"]))
    out: list[dict[str, object]] = []
    for flag, dates in streaks.items():
        if len(dates) >= min_days:
            out.append({"flag": flag, "days": len(dates), "dates": sorted(dates)})
    return sorted(out, key=lambda x: (-int(x["days"]), str(x["flag"])))


def compute_short_term(
    db: Session, user_id: int, farm_id: int, service_key: str, today: date, now: datetime
) -> dict[str, object]:
    """밭의 오늘~3일 예보 + 날짜별 위험신호. 소유권은 user_id 스코프 404(§11)."""
    farm = (
        db.query(UserFarm)
        .filter(UserFarm.user_id == user_id, UserFarm.id == farm_id)
        .first()
    )
    if farm is None:
        raise AppError(404, "FARM_NOT_FOUND", "밭을 찾을 수 없습니다.")

    rows, is_stale = get_forecast_rows(db, farm.region_id, service_key, today, now)
    soil = db.query(SoilState).filter(SoilState.user_farm_id == farm.id).first()

    days: list[dict[str, object]] = []
    breakdowns: list[dict[str, dict[str, object]]] = []
    for snap in rows:
        # 단계는 그 날짜 기준으로 다시 판정한다 — 3일 안에 단계가 넘어갈 수 있다.
        stage = resolve_growth_stage(db, farm.crop_id, farm.planting_date, snap.target_date)
        guides = [g for g in load_guides(db, farm.crop_id, stage or "") if _usable_daily(g)]
        result = calculate_suitability(guides, forecast_values(snap, soil))
        breakdowns.append(result["breakdown"])
        days.append(
            {
                "target_date": snap.target_date,
                "growth_stage": stage,
                "status": derive_status(bool(guides), result["score"], result["breakdown"]),
                "score": result["score"],
                "grade": result["grade"],
                "temp_avg": snap.temp_avg,
                "temp_night_min": snap.temp_night_min,
                "rainfall": snap.rainfall,
                "risk_flags": result["risk_flags"],
                # 행동추천이 값·허용구간을 함께 서술하려면 필요하다. 종전엔 계산해놓고
                # coverage_limitation에만 쓰고 버렸다(응답에 나가는 건 risk_flags 문자열뿐).
                "breakdown": result["breakdown"],
            }
        )

    limitations = [FORECAST_LIMITATION, SOIL_LIMITATION]
    coverage = coverage_limitation(breakdowns)
    if coverage is not None:
        limitations.insert(0, coverage)
    if is_stale:
        limitations.insert(0, STALE_LIMITATION)

    return {
        "farm_id": farm.id,
        "crop_id": farm.crop_id,
        "region_id": farm.region_id,
        "as_of": today,
        "base_at": rows[0].base_at if rows else None,
        "is_stale": is_stale,
        "label": SUITABILITY_LABEL,
        "days": days,
        "persistent_risks": persistent_risks(days),
        "limitations": limitations,
    }
