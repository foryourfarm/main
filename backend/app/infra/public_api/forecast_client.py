"""기상청 단기예보 조회 (data.go.kr 15084084, VilageFcstInfoService_2.0).

단기 탭의 데이터원. 격자좌표(nx, ny)만 받으므로 region_grid가 선행 조건이다.

실측으로 확인한 스펙(2026-07-25, 순천 격자 70,70 호출):
- resultCode가 **"00"**이다(흙토람 계열은 "200") → 코드 오버라이드 필요.
- dataType=JSON을 지원해 XML 파싱이 불필요하다.
- **PCP/SNO는 숫자가 아니라 "강수없음"/"적설없음" 문자열**로 온다. 그대로 float 하면
  터지므로 파싱에서 방어한다(§12 경계 방어).
- 응답은 (fcstDate, fcstTime, category) 조합의 롱포맷이라 날짜별로 접어야 쓸 수 있다.
"""

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from statistics import mean

import httpx

# https 고정(2026-08-03). data.go.kr이 평문 HTTP 응답을 중단해 `http://`는 연결이
# 걸린 채 타임아웃(15초)까지 매달린다 — 실측: http 25초 무응답 / https 0.08초 응답.
# 실패해도 캐시를 쓰지 않는 구조라(get_forecast_rows) 매 요청이 이 지연을 새로 먹었다.
BASE_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"

KST = timezone(timedelta(hours=9))

# 단기예보 발표시각(정시). 각 발표는 약 10분 후부터 조회 가능해 여유를 둔다.
BASE_TIMES = (2, 5, 8, 11, 14, 17, 20, 23)
PUBLISH_LAG_MIN = 45

# 한 번의 발표는 3일치를 3시간 간격으로 준다 → 넉넉히 받는다(페이징 방어).
NUM_OF_ROWS = 1000

SUCCESS_CODE = "00"

# 우리 지표로 쓰는 카테고리만 추린다.
CAT_TEMP = "TMP"  # 1시간 기온
CAT_TEMP_MIN = "TMN"  # 일 최저기온 — 야간 최저기온 지표의 직접 소스
CAT_PRECIP = "PCP"  # 1시간 강수량(문자열 가능)
CAT_POP = "POP"  # 강수확률
CAT_HUMIDITY = "REH"  # 습도

# "강수없음"·"적설없음"처럼 값이 아닌 표기. 0으로 해석한다(없다는 뜻).
_NO_VALUE_TOKENS = ("강수없음", "적설없음", "-", "")


class ForecastError(Exception):
    """예보 조회 실패(HTTP·resultCode·형식)."""


@dataclass(frozen=True)
class DailyForecast:
    """하루치로 접은 예보. weather_snapshot 한 행에 대응한다."""

    target_date: date
    temp_avg: Decimal | None
    temp_night_min: Decimal | None
    rainfall: Decimal | None  # 일 누적(mm)
    precip_prob_max: int | None  # 그날 최대 강수확률(%)
    humidity_max: int | None


def latest_base(now: datetime) -> tuple[str, str]:
    """가장 최근 조회 가능한 (base_date, base_time). 발표 직후 공백을 피해 여유를 둔다."""
    cutoff = now - timedelta(minutes=PUBLISH_LAG_MIN)
    for hour in sorted(BASE_TIMES, reverse=True):
        if cutoff.hour >= hour:
            return cutoff.strftime("%Y%m%d"), f"{hour:02d}00"
    # 자정 직후 — 전날 마지막 발표(23시)로 물러난다.
    prev = cutoff - timedelta(days=1)
    return prev.strftime("%Y%m%d"), f"{max(BASE_TIMES):02d}00"


def latest_base_at(now: datetime) -> datetime:
    """`latest_base`와 같은 발표시각을 datetime으로. 캐시 신선도 판정에 쓴다.

    벽시계 TTL로 판정하면 발표 주기(3h)와 어긋나 발표 사이 구간에서 매 요청이
    같은 발표분을 다시 조회한다(§18-1). 발표시각으로 비교하면 외부 호출 없이 판정된다.
    """
    base_date, base_time = latest_base(now)
    return datetime(
        int(base_date[:4]), int(base_date[4:6]), int(base_date[6:8]),
        int(base_time[:2]), tzinfo=KST,
    )


def parse_number(raw: str | None) -> Decimal | None:
    """예보값 → Decimal. "강수없음" 같은 표기는 0, 그 외 비수치는 None(결측)."""
    if raw is None:
        return None
    text = raw.strip()
    if text in _NO_VALUE_TOKENS:
        return Decimal(0)
    # "1.0mm 미만", "30.0~50.0mm" 같은 구간 표기도 온다 → 앞 숫자만 취한다.
    head = ""
    for ch in text:
        if ch.isdigit() or ch == ".":
            head += ch
        elif head:
            break
    if head in ("", "."):
        return None
    try:
        return Decimal(head)
    except ArithmeticError:
        return None


def fold_daily(items: list[dict[str, object]]) -> list[DailyForecast]:
    """롱포맷 items를 날짜별로 접는다. 순수 함수 — 파싱 규칙을 테스트로 고정한다."""
    by_date: dict[str, dict[str, list[Decimal]]] = {}
    for it in items:
        fcst_date = str(it.get("fcstDate") or "")
        category = str(it.get("category") or "")
        if not fcst_date or category not in (
            CAT_TEMP, CAT_TEMP_MIN, CAT_PRECIP, CAT_POP, CAT_HUMIDITY
        ):
            continue
        value = parse_number(str(it.get("fcstValue")) if it.get("fcstValue") is not None else None)
        if value is None:
            continue
        by_date.setdefault(fcst_date, {}).setdefault(category, []).append(value)

    out: list[DailyForecast] = []
    for fcst_date in sorted(by_date):
        buckets = by_date[fcst_date]
        temps = buckets.get(CAT_TEMP, [])
        mins = buckets.get(CAT_TEMP_MIN, [])
        precip = buckets.get(CAT_PRECIP, [])
        pops = buckets.get(CAT_POP, [])
        rehs = buckets.get(CAT_HUMIDITY, [])
        # TMN(일 최저기온)은 하루 1회만 오고, 첫날은 이미 지나 빠질 수 있어 TMP 최저로 폴백.
        night_min = min(mins) if mins else (min(temps) if temps else None)
        out.append(
            DailyForecast(
                target_date=date(int(fcst_date[:4]), int(fcst_date[4:6]), int(fcst_date[6:8])),
                temp_avg=Decimal(str(round(float(mean(float(t) for t in temps)), 1)))
                if temps
                else None,
                temp_night_min=night_min,
                rainfall=sum(precip, Decimal(0)) if precip else None,
                precip_prob_max=int(max(pops)) if pops else None,
                humidity_max=int(max(rehs)) if rehs else None,
            )
        )
    return out


def fetch_forecast(
    service_key: str, nx: int, ny: int, now: datetime | None = None, timeout: float = 15.0
) -> tuple[list[DailyForecast], datetime]:
    """(일별 예보, 발표시각). 실패는 ForecastError로 올려 호출부가 캐시 폴백하게 한다(§12)."""
    moment = now or datetime.now(KST)
    base_date, base_time = latest_base(moment)
    params = {
        "serviceKey": service_key,
        "pageNo": "1",
        "numOfRows": str(NUM_OF_ROWS),
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": str(nx),
        "ny": str(ny),
    }
    try:
        resp = httpx.get(BASE_URL, params=params, timeout=timeout)
        resp.raise_for_status()
        body = json.loads(resp.text)
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise ForecastError(f"예보 조회 실패: {exc}") from exc

    header = body.get("response", {}).get("header", {})
    if header.get("resultCode") != SUCCESS_CODE:
        raise ForecastError(f"[{header.get('resultCode')}] {header.get('resultMsg')}")

    items = body.get("response", {}).get("body", {}).get("items", {}).get("item", [])
    if not isinstance(items, list) or not items:
        raise ForecastError("예보 항목이 비어 있음")

    return fold_daily(items), latest_base_at(moment)
