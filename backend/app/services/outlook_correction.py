"""장기예보(tercile) 기반 평년치 보정 — read-time 전용 (DB.md §8.1).

**캐시하지 않는다.** outlook은 발표마다 바뀌는 시변 신호라 `suitability_result`에 섞으면
"같은 입력 → 같은 출력" 캐시 결정론이 깨진다(§3.13 B1). 캐시엔 평년치 baseline만 두고
이 보정은 조회 시점에 얹는다.

공식(§8.1): 보정치 = P(높음)×(+δ) + P(비슷)×0 + P(낮음)×(−δ) = (P높음 − P낮음) × δ

δ 산정(§10 미결정 해소): 상수로 추측하지 않고 RSS가 주는 '비슷' tercile 구간에서 유도한다.
    δ = (similar_high − similar_low) / 2

의도적 단순화: 실제 비슷구간은 평년값 기준 **비대칭**이다(실측: 평년 296.6mm,
구간 209.3~374.4 → 아래 −87.3 / 위 +77.8). 양쪽을 따로 쓰면 확률이 33/33/33일 때도
보정치가 0이 아니게 되어 "정보 없으면 움직이지 않는다"는 §8.1 불변식이 깨진다. 그래서
반폭 하나로 대칭화하고, 원본 경계는 DB에 그대로 남겨 나중에 정교화할 수 있게 둔다.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import WeatherOutlook

OUTLOOK_TEMP = "temp"
OUTLOOK_RAINFALL = "rainfall"

# 생육지침 지표 → outlook 지표. outlook은 기온·강수만 제공하므로(§8.1 B3) 나머지 지표
# (야간최저기온·일조·토양)는 보정 없이 평년치/실측을 그대로 쓴다.
INDICATOR_TO_OUTLOOK: dict[str, str] = {
    "temp_day": OUTLOOK_TEMP,
    # 3개월전망 강수는 월 단위 신호이므로 월 지표에만 대응한다(일 지표는 예보 소관).
    "rainfall_monthly": OUTLOOK_RAINFALL,
}

_THIRD = Decimal(1) / Decimal(3)


def correction_delta(
    prob_below: Decimal | None,
    prob_above: Decimal | None,
    similar_low: Decimal | None,
    similar_high: Decimal | None,
) -> Decimal | None:
    """(P높음 − P낮음) × δ. 확률·구간이 결측이면 None(보정 없음 — 산출은 계속된다, §12).

    확률은 % 단위(예: 60)로 들어오므로 100으로 나눠 쓴다.
    """
    if None in (prob_below, prob_above, similar_low, similar_high):
        return None
    assert prob_below is not None and prob_above is not None  # noqa: S101 — 타입 좁히기
    assert similar_low is not None and similar_high is not None  # noqa: S101
    half_width = (similar_high - similar_low) / 2
    if half_width <= 0:
        return None  # 구간 폭이 0/음수면 신호가 없다고 본다
    weight = (prob_above - prob_below) / Decimal(100)
    return weight * half_width


def load_corrections(
    db: Session, region_id: int, months: list[int], year: int
) -> dict[tuple[int, str], Decimal]:
    """{(월, 생육지침 지표): 보정치}. 같은 (지역,월,지표)는 최신 발표분만 쓴다.

    published_at 내림차순으로 읽고 처음 본 키만 채택 — 과거 발표분이 최신을 덮지 않게.
    """
    if not months:
        return {}
    # date 객체로 넘겨야 한다 — 문자열이면 Postgres가 DATE vs VARCHAR 비교를 거부한다.
    targets = [date(year, m, 1) for m in months]
    stmt = (
        select(WeatherOutlook)
        .where(
            WeatherOutlook.region_id == region_id,
            WeatherOutlook.target_month.in_(targets),
        )
        .order_by(WeatherOutlook.published_at.desc())
    )

    seen: set[tuple[int, str]] = set()
    out: dict[tuple[int, str], Decimal] = {}
    for row in db.scalars(stmt):
        key = (row.target_month.month, row.indicator)
        if key in seen:
            continue  # 더 오래된 발표분 — 무시
        seen.add(key)
        delta = correction_delta(
            row.prob_below, row.prob_above, row.similar_low, row.similar_high
        )
        if delta is None:
            continue
        for guide_indicator, outlook_indicator in INDICATOR_TO_OUTLOOK.items():
            if outlook_indicator == row.indicator:
                out[(row.target_month.month, guide_indicator)] = delta
    return out


def apply_corrections(
    values: dict[str, float | Decimal | None],
    corrections: dict[tuple[int, str], Decimal],
    month: int,
) -> tuple[dict[str, float | Decimal | None], dict[str, tuple[Decimal, Decimal]]]:
    """보정 적용값과 분해 내역을 반환. 내역 = {지표: (baseline, 보정치)} (§8.1-5 근거 제시용).

    baseline이 결측인 지표는 보정할 대상이 없으므로 건너뛴다.
    """
    corrected = dict(values)
    applied: dict[str, tuple[Decimal, Decimal]] = {}
    for indicator in INDICATOR_TO_OUTLOOK:
        delta = corrections.get((month, indicator))
        baseline = values.get(indicator)
        if delta is None or baseline is None:
            continue
        base = Decimal(str(baseline))
        corrected[indicator] = base + delta
        applied[indicator] = (base, delta)
    return corrected, applied
