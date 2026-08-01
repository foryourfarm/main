"""기상청 AWS/지상 일통계 자료 (apihub.kma.go.kr typ01).

명세: `기상청_API-Guide.md` §지상 및 AWS 일통계 자료 조회
- URL: `https://apihub.kma.go.kr/api/typ01/url/sfc_aws_day.php`
- 인증: `authKey` (config.weather_apihub_key) — data.go.kr 키와 별개 체계다.

**역할**: 농업기상(218지점)이 없는 구역의 평년치를 채우는 2차 관측망이다. 일사량·일조시간은
여기 없고(아래 참고) 농업기상에만 있으므로 이 클라이언트가 농업기상을 대체하지는 못한다.

## 실호출로 확정한 것 (2026-08-01)

**응답은 XML/JSON이 아니라 텍스트다.** `#START7777` 다음에 `#` 주석 헤더가 오고, 공백으로
구분된 데이터행이 이어지다 `#7777END`로 끝난다. 인코딩은 **CP949**(지점명이 한글).

    # YYMMDD   STN         LON          LAT       HT      VAL
    20250701   212 127.88043000  37.68360000  140.20     31.7 홍천

마지막 지점명 칼럼은 헤더에 없지만 실제로 붙어 오고, 이름에 공백이 있으면 필드가 8개가
된다(실측: 22,611행 중 495행). 그래서 **앞에서부터 6개만 위치로 읽고 나머지는 이름으로 합친다.**

**호출당 기상요소는 하나다.** `obs=ta_max` 하나에 값 칼럼(VAL) 하나만 온다. 평균기온을 주는
`obs` 값은 없다 — `ta_avg`·`ta_day`·`ta_mean`·`ta` 모두 빈 응답이었고 명세 목록에도 최고·최저만
있다. 일평균이 필요하면 `(ta_max + ta_min) / 2`로 근사해야 한다(오차는 §아래).

**대신 지점·기간을 한 번에 준다.** `stn=0`이면 전 지점이고 `tm1~tm2`로 기간을 잡을 수 있다.
2026-07 한 달·전 지점 = 22,853행이 한 응답에 왔다. 그래서 지점별 반복 호출을 하지 않는다
(§18-1 무분별 호출 금지). 대안이던 `getDailyAwsData`(typ02)는 평균기온을 직접 주지만
**지점당 1회 호출**이라 5년치에 44,400회가 필요하고, 방재기상월보 기반이라 **발간이 2~3개월
지연된다**(2026-08-01에 2026-06이 "발간되지 않은 기간"). 이 클라이언트는 지연이 없다.

**결측 표기**: 실측 표본(ta_max 22,611행 / rn_day 3,560행)에서 음수 결측 코드는 나오지
않았다. 그래도 다른 기간·요소에서 나올 수 있으므로 파서는 음수 관측불가값과 비수치를
모두 결측(None)으로 흘린다 — 진입 지점에서 방어한다(§12).

## 일평균 근사 오차 (실측 1,592일 · 13지점 · 2025년 1/4/7/10월)

`(ta_max + ta_min) / 2`는 참 일평균보다 **체계적으로 +0.348℃ 높다**(R² 0.9959, MAE 0.518).
지형별로 산간 +0.197 ~ 내륙 +0.394로 갈리지만, 그 차이가 최종 적합도 점수에 미치는 영향은
0.2점 미만이라 전국 단일 보정값을 쓴다. 보정값과 근거는 코드가 아니라 시드에 둔다(§18-2).
재현: `scripts/validate_tavg_approximation.py`.
"""

from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.infra.public_api.base import PublicApiError

BASE_URL = "https://apihub.kma.go.kr/api/typ01/url/sfc_aws_day.php"

# typ01 텍스트 응답은 CP949다(지점명이 한글). UTF-8로 읽으면 이름이 깨진다.
ENCODING = "cp949"

# 값 칼럼 위치. 헤더(`# YYMMDD STN LON LAT HT VAL`) 기준이며, 그 뒤에 지점명이 더 붙는다.
_COL_COUNT = 6
_IDX_TM, _IDX_STN, _IDX_LON, _IDX_LAT, _IDX_HT, _IDX_VAL = range(_COL_COUNT)

# 관측불가·결측을 뜻하는 하한. 기온·강수 어느 쪽도 국내에서 이 아래로 내려가지 않는다.
_MISSING_BELOW = -90.0

# 우리가 쓰는 기상요소. 명세 §obs의 값 중 룰 엔진 지표에 대응하는 것만 추렸다.
OBS_TEMP_MAX = "ta_max"  # 일 최고기온 (℃)
OBS_TEMP_MIN = "ta_min"  # 일 최저기온 (℃) — temp_night_min 지표의 소스
OBS_RAIN = "rn_day"  # 일강수량 (mm)


@dataclass(frozen=True)
class AwsDailyValue:
    """지점 × 일자 × 기상요소 하나. 값이 결측이면 애초에 만들지 않는다."""

    point_code: str  # STN (예: "108") — 농업기상 코드(`230802A001`)와 조인되지 않는다
    obs_date: str  # YYYY-MM-DD
    value: float
    lat: float
    lon: float
    altitude: float | None
    point_name: str


def _to_float(raw: str) -> float | None:
    """수치 아니거나 관측불가 하한 미만이면 결측(None)."""
    try:
        value = float(raw)
    except ValueError:
        return None
    return None if value < _MISSING_BELOW else value


def parse_response(text: str) -> list[AwsDailyValue]:
    """typ01 텍스트 → 관측값 목록. 순수 함수 — 파싱 규칙을 테스트로 고정한다.

    `#`로 시작하는 줄(헤더·주석·종료표시)은 건너뛴다. 지점명에 공백이 있어 필드 수가
    가변이므로 앞 6개만 위치로 읽고 나머지를 이름으로 합친다.
    """
    out: list[AwsDailyValue] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < _COL_COUNT:
            continue

        value = _to_float(parts[_IDX_VAL])
        lat = _to_float(parts[_IDX_LAT])
        lon = _to_float(parts[_IDX_LON])
        if value is None or lat is None or lon is None:
            continue  # 값이나 좌표가 없으면 쓸 수 없다 — 조용히 0으로 만들지 않는다

        raw_date = parts[_IDX_TM]
        if len(raw_date) < 8 or not raw_date[:8].isdigit():
            continue

        out.append(
            AwsDailyValue(
                point_code=parts[_IDX_STN],
                obs_date=f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}",
                value=value,
                lat=lat,
                lon=lon,
                altitude=_to_float(parts[_IDX_HT]),
                point_name=" ".join(parts[_COL_COUNT:]) or parts[_IDX_STN],
            )
        )
    return out


def fetch_daily(
    obs: str,
    begin_date: str,
    end_date: str,
    point_code: str = "0",
    timeout: float = 120.0,
) -> list[AwsDailyValue]:
    """기상요소 하나를 기간·지점 단위로 조회한다.

    Args:
        obs: `OBS_TEMP_MAX` 등. **호출당 하나만** 된다(모듈 docstring).
        begin_date, end_date: `YYYYMMDD`.
        point_code: 지점번호. 기본 `"0"`이면 전 지점 — 지점별 반복 호출 대신 이걸 쓴다.
        timeout: 전 지점 한 달이 1.4MB 정도라 넉넉히 잡는다.

    Raises:
        PublicApiError: HTTP 실패 또는 종료 표시(`#7777END`)가 없는 잘린 응답.
    """
    params = {
        "tm1": begin_date,
        "tm2": end_date,
        "obs": obs,
        "stn": point_code,
        "disp": "0",
        "help": "0",
        "authKey": settings.weather_apihub_key,
    }
    try:
        resp = httpx.get(BASE_URL, params=params, timeout=timeout)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise PublicApiError("HTTP_ERROR", f"AWS 일통계 조회 실패({obs}): {exc}") from exc

    text = resp.content.decode(ENCODING, errors="replace")
    # 인증 실패·파라미터 오류는 200에 오류 문구로 온다. 종료 표시로 온전한 응답인지 본다.
    if "#7777END" not in text:
        raise PublicApiError("UPSTREAM_UNAVAILABLE", f"AWS 응답이 잘렸거나 오류다({obs}): {text[:200]}")
    return parse_response(text)


def fetch_daily_temps_and_rain(
    begin_date: str,
    end_date: str,
    point_code: str = "0",
    timeout: float = 120.0,
) -> dict[tuple[str, str], dict[str, float]]:
    """최고·최저기온·강수를 한 번에 모아 `(지점, 날짜) → {요소: 값}`으로 돌려준다.

    요소마다 호출이 필요하므로(모듈 docstring) 3회 호출한다. 결측인 요소는 키 자체가 없다 —
    호출부가 `.get()`으로 결측을 구분할 수 있게 하려는 것이다(0으로 채우지 않는다).
    """
    merged: dict[tuple[str, str], dict[str, float]] = {}
    for obs in (OBS_TEMP_MAX, OBS_TEMP_MIN, OBS_RAIN):
        for row in fetch_daily(obs, begin_date, end_date, point_code, timeout):
            merged.setdefault((row.point_code, row.obs_date), {})[obs] = row.value
    return merged
