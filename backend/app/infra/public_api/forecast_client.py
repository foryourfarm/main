"""기상청 단기예보 조회 (data.go.kr 15084084, VilageFcstInfoService_2.0).

단기 탭의 데이터원. 격자좌표(nx, ny)만 받으므로 region_grid가 선행 조건이다.

실측으로 확인한 스펙(2026-07-25, 순천 격자 70,70 호출):
- resultCode가 **"00"**이다(흙토람 계열은 "200") → 코드 오버라이드 필요.
- dataType=JSON을 지원해 XML 파싱이 불필요하다.
- **PCP/SNO는 숫자가 아니라 "강수없음"/"적설없음" 문자열**로 온다. 그대로 float 하면
  터지므로 파싱에서 방어한다(§12 경계 방어).
- 응답은 (fcstDate, fcstTime, category) 조합의 롱포맷이라 날짜별로 접어야 쓸 수 있다.

실측으로 확인한 슬롯 구조(2026-08-04 15:43, 14시 발표, 순천 70,70 — item 798개):

```
        TMP                         TMX        TMN
오늘    n= 9  15~23시  1시간 간격   (없음)     (없음)   ← 발표시각 이후만, 새벽·오전 결손
+1일    n=24  00~23시  1시간        1500 슬롯  0600 슬롯
+2일    n=24  00~23시  1시간        1500       0600
+3일    n= 8  00~21시  3시간        1500       0600
+4일    n= 1  00시만                (없음)     (없음)
```

여기서 두 가지가 이 모듈의 설계를 좌우한다.

1. **첫날은 발표시각 이후 시간대만 온다.** 14시 발표면 오늘은 15~23시 9개뿐이라 새벽 최저와
   오전이 통째로 빠진다. 그 표본으로 산술평균을 내면 **일평균이 실제보다 높다.** TMX·TMN도
   오늘 날짜에는 아예 없어 TMP의 최고·최저로 폴백해야 한다.
2. **TMP 간격이 날짜마다 다르다** — +2일까지는 1시간, +3일은 3시간이다. 그래서 "표본 몇 개면
   온전한 하루"라는 개수 기준은 쓸 수 없고, 대신 **덮은 시각 범위**로 판정한다(LAST_SLOT_HOUR).
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

# 한 번의 발표가 주는 양은 날짜마다 다르다(위 슬롯 구조) — 실측 798개였다. 넉넉히 받아
# 페이징을 피한다.
NUM_OF_ROWS = 1000

SUCCESS_CODE = "00"

# 우리 지표로 쓰는 카테고리만 추린다.
CAT_TEMP = "TMP"  # 1시간 기온
CAT_TEMP_MAX = "TMX"  # 일 최고기온 — 화면의 "낮 최고기온" 직접 소스
CAT_TEMP_MIN = "TMN"  # 일 최저기온 — 야간 최저기온 지표의 직접 소스
CAT_PRECIP = "PCP"  # 1시간 강수량(문자열 가능)
CAT_POP = "POP"  # 강수확률
CAT_HUMIDITY = "REH"  # 습도

# 그날 표본이 하루를 온전히 덮었는지 판정할 마지막 시각.
# **개수로 판정할 수 없다** — TMP 간격이 1시간(+2일까지)과 3시간(+3일)으로 갈려 "온전한 하루"의
# 표본 수가 24개와 8개로 다르다. 반면 마지막 슬롯은 1시간 간격이면 23시, 3시간 간격이면 21시라
# 두 경우 모두 21시 이상이다. 그래서 21을 기준선으로 두면 간격에 무관하게 뒤결손만 잡아낸다.
LAST_SLOT_HOUR = 21

# "강수없음"·"적설없음"처럼 값이 아닌 표기. 0으로 해석한다(없다는 뜻).
_NO_VALUE_TOKENS = ("강수없음", "적설없음", "-", "")


class ForecastError(Exception):
    """예보 조회 실패(HTTP·resultCode·형식)."""


@dataclass(frozen=True)
class DailyForecast:
    """하루치로 접은 예보. weather_snapshot 한 행에 대응한다.

    **`temp_avg`와 `temp_max`는 쓰임이 다르다.** `temp_avg`(일평균)는 채점 지표 `temp_day`의
    입력이고, `temp_max`(일최고)는 화면에 "낮 최고기온"으로 보여주는 값이다. 한 값이 두 역할을
    겸하면서 일평균을 "낮 기온"이라 부르던 것이 이 분리의 이유다(docs/temperature-scoring.md).
    """

    target_date: date
    temp_avg: Decimal | None
    """일평균기온. 채점(`temp_day`) 입력 — 화면 표시용이 아니다."""
    temp_max: Decimal | None
    """일최고기온. TMX 우선, 없으면 TMP 최고로 폴백(첫날은 TMX가 오지 않는다)."""
    temp_night_min: Decimal | None
    rainfall: Decimal | None  # 일 누적(mm)
    precip_prob_max: int | None  # 그날 최대 강수확률(%)
    humidity_max: int | None
    hourly_temp: list[dict[str, object]] | None
    """시간별 기온 `[{"h": 15, "t": "29.5"}, …]`(시각 오름차순). 모달 그래프용.

    `t`를 문자열로 담는 이유: JSONB 직렬화가 Decimal을 못 다루고, float으로 바꾸면 응답의
    다른 기온값(Decimal→문자열)과 표기가 갈린다.
    """
    is_partial: bool
    """그날 표본이 하루를 온전히 덮지 못함(앞결손·뒤결손). True면 집계값이 편향돼 있다."""


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


def parse_hour(raw: object) -> int | None:
    """fcstTime("HHMM") → 시각(0~23). 형식이 어긋나면 None — 값 자체는 버리지 않는다."""
    text = str(raw or "").strip()
    if len(text) < 2 or not text[:2].isdigit():
        return None
    hour = int(text[:2])
    return hour if 0 <= hour <= 23 else None


def fold_daily(items: list[dict[str, object]]) -> list[DailyForecast]:
    """롱포맷 items를 날짜별로 접는다. 순수 함수 — 파싱 규칙을 테스트로 고정한다."""
    by_date: dict[str, dict[str, list[Decimal]]] = {}
    # TMP는 값과 함께 **시각**도 남긴다 — 하루 커버리지 판정(is_partial)과 그래프에 쓴다.
    # 종전에는 fcstTime을 읽지도 않아 첫날 부분 표본을 온전한 하루와 구분할 수 없었다.
    hourly: dict[str, dict[int, Decimal]] = {}
    for it in items:
        fcst_date = str(it.get("fcstDate") or "")
        category = str(it.get("category") or "")
        if not fcst_date or category not in (
            CAT_TEMP, CAT_TEMP_MAX, CAT_TEMP_MIN, CAT_PRECIP, CAT_POP, CAT_HUMIDITY
        ):
            continue
        value = parse_number(str(it.get("fcstValue")) if it.get("fcstValue") is not None else None)
        if value is None:
            continue
        by_date.setdefault(fcst_date, {}).setdefault(category, []).append(value)
        if category == CAT_TEMP:
            hour = parse_hour(it.get("fcstTime"))
            if hour is not None:
                hourly.setdefault(fcst_date, {})[hour] = value

    out: list[DailyForecast] = []
    for fcst_date in sorted(by_date):
        buckets = by_date[fcst_date]
        temps = buckets.get(CAT_TEMP, [])
        maxs = buckets.get(CAT_TEMP_MAX, [])
        mins = buckets.get(CAT_TEMP_MIN, [])
        precip = buckets.get(CAT_PRECIP, [])
        pops = buckets.get(CAT_POP, [])
        rehs = buckets.get(CAT_HUMIDITY, [])
        # TMX/TMN(일 최고·최저)은 하루 1회만 오고 **첫날은 둘 다 아예 없다**(실측 확인) —
        # 그때는 TMP의 최고·최저로 폴백한다. 부분 표본이면 그 폴백값도 실제 극값에 못 미치는데,
        # 방향이 한쪽으로만(최고는 과소, 최저는 과대) 어긋나는 것은 is_partial로 고지한다.
        day_max = max(maxs) if maxs else (max(temps) if temps else None)
        night_min = min(mins) if mins else (min(temps) if temps else None)

        hours = sorted(hourly.get(fcst_date, {}))
        # 앞결손(발표시각 이후만 온 첫날)이나 뒤결손(예보 지평 끝)이면 그날 집계는 하루 전체를
        # 대표하지 못한다. 표본 개수가 아니라 덮은 시각 범위로 본다(LAST_SLOT_HOUR 주석).
        is_partial = not hours or hours[0] > 0 or hours[-1] < LAST_SLOT_HOUR
        out.append(
            DailyForecast(
                target_date=date(int(fcst_date[:4]), int(fcst_date[4:6]), int(fcst_date[6:8])),
                temp_avg=Decimal(str(round(float(mean(float(t) for t in temps)), 1)))
                if temps
                else None,
                temp_max=day_max,
                temp_night_min=night_min,
                rainfall=sum(precip, Decimal(0)) if precip else None,
                precip_prob_max=int(max(pops)) if pops else None,
                humidity_max=int(max(rehs)) if rehs else None,
                hourly_temp=[{"h": h, "t": str(hourly[fcst_date][h])} for h in hours] or None,
                is_partial=is_partial,
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
