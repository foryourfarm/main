"""단기 탭 — 예보 조회·캐시 + 날짜별 위험신호 판정 (PRD.md §4.5, DB.md §8.4).

위험 임계치를 새로 만들지 않는다. `crop_growth_guide`의 허용구간(allowed_min/max)이 이미
작물×단계별 위험 경계이므로, 장기 탭과 **같은 룰 엔진**에 예보값을 넣어 판정한다.
새 기준값을 코드에 박으면 §18-2 위반이고 장기/단기 판정이 어긋난다.

A씨 사례(봄철 야간저온으로 활착 실패)가 이 탭의 존재 이유다 — 그래서 단일 시점이 아니라
날짜별로 판정하고 **연속 지속**을 따로 표시한다(§7-4 시계열 요구).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infra.public_api.forecast_client import (
    LAST_SLOT_HOUR,
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

# 오늘·내일·모레. 기상청 한 발표는 +4일까지 주지만(마지막 날은 00시 1슬롯뿐, forecast_client
# 슬롯표) 뒤로 갈수록 표본이 얇아 카드로 세울 값이 못 된다. 3일로 줄이면 "지금 대응할 창"만
# 남는다 — 늘리려면 이 상수만 올리면 되고 병합·판정 로직은 그대로다.
FORECAST_DAYS = 3

FORECAST_LIMITATION = (
    "기상청 단기예보 기반 오늘·내일·모레 3일치입니다. "
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
# 카드에 보이는 값과 채점에 쓰는 값이 다르다는 사실을 숨기지 않는다(§18-4). 종전에는 일평균을
# "낮 기온"이라 부르며 한 값이 두 역할을 겸했고, 실측에서 6.7℃까지 벌어졌다(일평균 31.3 vs
# 일최고 38). 채점 밴드가 어느 척도로 만들어진 것인지는 밴드마다 달라 아직 정리되지 않았다 —
# 그 미결정은 docs/temperature-open-decisions.md에 있고, 여기서는 사실만 알린다.
TEMP_SCALE_LIMITATION = (
    "카드의 '낮 최고기온'은 그날 예보 최고기온이고, 적합도 점수는 하루 평균기온으로 매깁니다 — "
    "서로 다른 값입니다. 고온·냉해 기준은 원래 최고·최저기온 기준인 경우가 많아, 평균으로 "
    "매긴 점수는 한낮·새벽의 극단적인 위험을 실제보다 약하게 볼 수 있습니다."
)
# 첫날은 발표시각 이후 시간대만 온다(실측: 14시 발표 → 오늘은 15~23시 9개뿐). 예보 지평
# 끝날은 반대로 앞부분만 온다. 편향 **방향**까지 적는다 — "부정확하다"만 적으면 어느 쪽으로
# 틀렸는지 몰라 유저가 대응할 수 없다.
PARTIAL_DAY_LIMITATION = (
    "일부 날짜는 하루 전체가 아니라 일부 시간대만 반영된 값입니다(카드에 '일부 시간대'로 표시). "
    "특히 오늘은 이 지역 예보를 처음 받아둔 시각보다 이른 시간대(자정~그 시각)가 어느 발표에도 "
    "없어 빠질 수 있습니다. 그런 날은 새벽·오전이 빠져 평균기온이 실제보다 높게, 최고기온은 낮 "
    "피크를 놓쳐 낮게 나올 수 있습니다."
)
# 합친 값이라는 사실을 숨기지 않는다(§18-4). 카드의 오늘 값은 한 발표분이 아니라 여러 발표분에서
# 왔고, 극값을 위험 쪽으로 취하므로 **한 방향으로** 편향돼 있다 — 그 방향까지 적는다.
MERGED_DAY_LIMITATION = (
    "오늘 값은 여러 발표분을 합친 것입니다 — 이미 지난 시간대는 그 시각을 예보했던 이전 발표에서, "
    "남은 시간대는 최신 발표에서 왔습니다. 최고·최저기온과 강수는 발표분이 엇갈릴 때 위험이 큰 "
    "쪽을 취하므로(경고를 놓치지 않기 위해서) 실제보다 세게 볼 수 있습니다."
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
            "temp_max": d.temp_max,
            "temp_night_min": d.temp_night_min,
            "rainfall": d.rainfall,
            "sunlight": None,  # 단기예보는 일조를 주지 않는다
            "hourly_temp": d.hourly_temp,
            # 부분 표본으로 낸 집계는 하루를 대표하지 못한다 — §12의 "대체됨 플래그"다.
            "is_imputed": d.is_partial,
        }
        for d in days
    ]


@dataclass(frozen=True)
class ForecastDay:
    """여러 발표분을 합친 하루치 예보. `weather_snapshot` 한 행이 아니라 **읽기 전용 뷰**다.

    ORM 행에 합친 값을 담지 않는 이유: 세션에 붙은 객체를 고치면 이어지는 조회의 autoflush가
    그 값을 DB에 써버린다. 발표분 원본은 그대로 남아야 한다(§12 출처·수집시각 기록).
    """

    base_at: datetime
    """합친 발표분 중 **가장 최신** 발표시각. 화면의 "○시 발표" 표기와 신선도 판정에 쓴다."""
    target_date: date
    temp_avg: Decimal | None
    """일평균기온. 채점 지표 `temp_day` 입력 — 합친 시간별 기온의 평균이다."""
    temp_max: Decimal | None
    temp_night_min: Decimal | None
    rainfall: Decimal | None
    sunlight: Decimal | None
    hourly_temp: list[dict[str, Any]] | None
    is_imputed: bool
    is_merged: bool
    """발표분 2개 이상을 합쳐 만든 값(화면 한계 표기용)."""


def _slot_hours(rows: Sequence[WeatherSnapshot]) -> dict[int, Decimal]:
    """발표분들의 시간별 기온을 **시각 단위로 합친다. 겹치면 뒤(최신) 발표가 이긴다.**

    호출자가 base_at 오름차순으로 넘긴다. JSONB는 타입이 느슨해 값이 깨져 있을 수 있으므로
    슬롯 하나가 이상해도 그 슬롯만 버리고 계속한다(§12 — 산출이 예외로 죽지 않게).
    """
    hours: dict[int, Decimal] = {}
    for row in rows:
        for slot in row.hourly_temp or []:
            if not isinstance(slot, dict):
                continue
            hour, raw = slot.get("h"), slot.get("t")
            if not isinstance(hour, int) or not 0 <= hour <= 23 or raw is None:
                continue
            try:
                hours[hour] = Decimal(str(raw))
            except InvalidOperation:
                continue
    return hours


def _merge_publications(rows: Sequence[WeatherSnapshot]) -> ForecastDay:
    """같은 날짜의 발표분 여러 개를 하루치 하나로 합친다. 순수 함수.

    **왜 합치는가**: 단기예보 첫날은 발표시각 이후 시간대만 온다(14시 발표 → 오늘 15~23시,
    `forecast_client` 슬롯표). 그래서 최신 발표분만 읽으면 새 발표를 받는 순간 오늘 카드에서
    이미 지난 새벽·오전이 통째로 빠진다 — 야간 최저가 오후 최저로 바뀌고, 강수 일누적이 남은
    시간대만으로 줄고, 기온 곡선의 앞부분이 사라진다. 지난 시간대는 **그 시각을 예보했던 이전
    발표**에만 있으므로 거기서 가져온다.

    **극값·강수는 발표분 중 위험이 큰 쪽을 취한다**(최고 max·최저 min·강수 max). 이유 둘:
      ⓐ 오늘 카드는 하루 전체를 말해야 한다. 오전에 이미 내린 비를 남은 시간대만 담은 최신
        발표로 덮으면 일누적이 실제보다 줄어든다.
      ⓑ 이 탭은 위험을 미리 알리는 자리다(PRD 철학 3). 두 발표가 엇갈릴 때 약한 쪽을 고르면
        경고를 놓친다 — 과대 경고는 한계 문구로 알릴 수 있지만 놓친 경고는 알릴 방법이 없다.
    한 방향으로 편향된다는 사실은 `MERGED_DAY_LIMITATION`으로 화면에 표기한다(§18-4).
    """
    ordered = sorted(rows, key=lambda r: r.base_at)
    newest = ordered[-1]
    hours = _slot_hours(ordered)
    covered = sorted(hours)
    temps = [hours[h] for h in covered]

    maxima = [r.temp_max for r in ordered if r.temp_max is not None]
    minima = [r.temp_night_min for r in ordered if r.temp_night_min is not None]
    rainfalls = [r.rainfall for r in ordered if r.rainfall is not None]
    # TMX/TMN은 하루 1회만 오고 오늘 날짜에는 아예 없다 — 합친 시간별 기온의 극값으로 보완한다.
    if temps:
        maxima.append(max(temps))
        minima.append(min(temps))

    return ForecastDay(
        base_at=newest.base_at,
        target_date=newest.target_date,
        # 합친 표본의 평균. 표본이 없으면(시간별이 비었으면) 최신 발표분 값을 그대로 쓴다.
        temp_avg=round(sum(temps) / len(temps), 1) if temps else newest.temp_avg,
        temp_max=max(maxima) if maxima else None,
        temp_night_min=min(minima) if minima else None,
        rainfall=max(rainfalls) if rainfalls else None,
        sunlight=newest.sunlight,  # 단기예보는 일조를 주지 않는다(항상 None)
        hourly_temp=[{"h": h, "t": str(hours[h])} for h in covered] or None,
        # 합친 뒤 커버리지로 다시 판정한다 — 발표분 각각은 부분이어도 합치면 온전할 수 있다.
        is_imputed=(
            not (covered[0] == 0 and covered[-1] >= LAST_SLOT_HOUR)
            if covered
            else any(bool(r.is_imputed) for r in ordered)
        ),
        is_merged=len(ordered) > 1,
    )


def _cached_rows(db: Session, region_id: int, since: date) -> list[ForecastDay]:
    """오늘·내일·모레 3일치 예보 캐시. **날짜별로 발표분을 합쳐** 돌려준다. 없으면 빈 리스트.

    종전에는 최신 발표분 하나만 골랐다(`MAX(base_at)`). 저장은 발표분마다 남아 있는데
    (`uq_weather`에 `base_at`이 있어 발표마다 새 행이다) **읽기가 버리고 있었다** — 그래서
    오늘 값이 새 발표를 받을 때마다 퇴화했다. 새 캐시 테이블·컬럼이 필요한 문제가 아니었다.
    """
    until = since + timedelta(days=FORECAST_DAYS - 1)
    # 합칠 범위는 **가장 최신 발표분으로부터 24시간**이다. 오늘을 하루 전체로 예보한 것은 그 전날
    # 발표뿐이므로(오늘 발표는 발표시각 이후만 준다) 하루는 필요하고, 그보다 오래된 발표는 뺀다 —
    # 합칠 때 극값을 위험 쪽으로 취하므로 낡은 발표의 극값이 경고로 되살아난다.
    #
    # **절대 날짜("어제 00시 이후")로 자르지 않는다.** 그러면 캐시가 하루보다 낡은 지역에서 목록이
    # 통째로 비어, 외부 API 장애 시 "마지막 캐시 + 최신 아님 고지"로 버티는 §12 폴백이 사라진다
    # (실측: region 145는 절대 날짜 기준으로 카드가 0장이 됐다).
    newest_base_at = (
        db.query(func.max(WeatherSnapshot.base_at))
        .filter(
            WeatherSnapshot.region_id == region_id,
            WeatherSnapshot.kind == KIND_FORECAST,
            WeatherSnapshot.target_date >= since,
            WeatherSnapshot.target_date <= until,
        )
        .scalar()
    )
    if newest_base_at is None:
        return []
    oldest_base_at = newest_base_at - timedelta(days=1)
    rows = (
        db.query(WeatherSnapshot)
        .filter(
            WeatherSnapshot.region_id == region_id,
            WeatherSnapshot.kind == KIND_FORECAST,
            WeatherSnapshot.target_date >= since,
            WeatherSnapshot.target_date <= until,
            WeatherSnapshot.base_at >= oldest_base_at,
        )
        .order_by(WeatherSnapshot.target_date, WeatherSnapshot.base_at)
        .all()
    )
    by_date: dict[date, list[WeatherSnapshot]] = {}
    for row in rows:
        by_date.setdefault(row.target_date, []).append(row)
    return [_merge_publications(same_date) for _, same_date in sorted(by_date.items())]


def get_forecast_rows(
    db: Session, region_id: int, service_key: str, today: date, now: datetime
) -> tuple[list[ForecastDay], bool]:
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
                "temp_max": stmt.excluded.temp_max,
                "temp_night_min": stmt.excluded.temp_night_min,
                "rainfall": stmt.excluded.rainfall,
                "sunlight": stmt.excluded.sunlight,
                "hourly_temp": stmt.excluded.hourly_temp,
                # 같은 발표분을 다시 받으면 부분성 판정도 같이 갱신돼야 한다. 갱신 목록에서
                # 빠뜨리면 0032 이전 캐시가 남은 구역에서 NULL/false가 굳는다.
                "is_imputed": stmt.excluded.is_imputed,
            },
        )
        db.execute(stmt)
        db.commit()
    return _cached_rows(db, region_id, today), False


def forecast_values(
    snap: ForecastDay, soil: SoilState | None
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
    """밭의 오늘·내일·모레 예보 + 날짜별 위험신호. 소유권은 user_id 스코프 404(§11)."""
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
                # temp_avg는 채점 입력이라 그래프가 "이 값으로 매겼다"를 보여주려면 필요하고,
                # temp_max는 카드에 나가는 표시값이다 — 둘을 함께 내보내야 모달이 그 차이를
                # 설명할 수 있다.
                "temp_avg": snap.temp_avg,
                "temp_max": snap.temp_max,
                "temp_night_min": snap.temp_night_min,
                "rainfall": snap.rainfall,
                "hourly_temp": snap.hourly_temp,
                "is_imputed": snap.is_imputed,
                "risk_flags": result["risk_flags"],
                # 행동추천이 값·허용구간을 함께 서술하려면 필요하다. 종전엔 계산해놓고
                # coverage_limitation에만 쓰고 버렸다(응답에 나가는 건 risk_flags 문자열뿐).
                "breakdown": result["breakdown"],
            }
        )

    limitations = [FORECAST_LIMITATION, TEMP_SCALE_LIMITATION, SOIL_LIMITATION]
    if any(row.is_merged for row in rows):
        limitations.insert(0, MERGED_DAY_LIMITATION)
    if any(bool(row.is_imputed) for row in rows):
        limitations.insert(0, PARTIAL_DAY_LIMITATION)
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
