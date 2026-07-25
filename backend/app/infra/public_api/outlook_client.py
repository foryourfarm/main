"""기상청 3개월전망 RSS(XML) 조회·파싱 — 장기예보 tercile 확률 (DB.md §3.12).

왜 RSS인가(2026-07-25 실측 검증):
- data.go.kr 15050698 '기상청_3개월전망'은 오픈API가 아니라 **PDF fileData**라 기계판독 불가.
- 기상청 API허브 예특보에는 단·중기예보만 있고 장기예보 API가 없다.
- 반면 이 RSS는 tercile 확률(낮음/비슷/높음 %)을 숫자 태그로 주고, 권역 평년값과
  '비슷' 구간까지 함께 준다 → 보정 단위 δ를 상수로 추측하지 않고 데이터에서 유도 가능.

실측으로 확인한 함정 2개(둘 다 방어 필수):
1. **발표일이 이동한다** — 원칙은 매월 23일이나 2026-05는 22일(주말)에 나왔고 23·24일
   URL은 존재하지 않았다. 그래서 23일 기준으로 앞뒤 며칠을 탐색한다.
2. **없는 날짜도 HTTP 200 + HTML 에러페이지를 반환한다** — 상태코드만 믿고 파싱하면
   쓰레기를 적재한다. XML 파싱 성공 + 기대 루트/태그 존재까지 확인해야 한다.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree

import httpx

URL_TEMPLATE = "http://www.kma.go.kr/repositary/xml/fct/mon/img/fct_mon3rss_108_{stamp}.xml"

# 발표 원칙일(23일) 기준 탐색 순서. 주말·공휴일이면 앞당겨 발표되므로 22일을 먼저 본다.
RELEASE_DAY = 23
PROBE_OFFSETS = (0, -1, 1, -2, 2, -3, 3)

KST = timezone(timedelta(hours=9))

INDICATOR_TEMP = "temp"
INDICATOR_RAINFALL = "rainfall"

# (지표, RSS 권역 컨테이너 태그, 권역명 태그, 태그 중위 토큰)
_SECTIONS = (
    (INDICATOR_TEMP, "local_ta", "local_ta_name", "local_ta"),
    (INDICATOR_RAINFALL, "local_rn", "local_rn_name", "local_rn"),
)

_RANGE_RE = re.compile(r"^\s*(-?[\d.]+)\s*~\s*(-?[\d.]+)\s*$")


class OutlookFetchError(Exception):
    """유효한 3개월전망 XML을 찾지 못함(탐색 범위 내 전부 실패)."""


@dataclass(frozen=True)
class OutlookRecord:
    """권역×대상월×지표 하나. region 매핑은 상위(ETL)에서 zone_name으로 붙인다."""

    zone_name: str
    target_month: date  # 해당 월 1일로 정규화
    indicator: str
    category: str  # BELOW | NORMAL | ABOVE — 최대 확률 tercile
    prob_below: Decimal | None
    prob_normal: Decimal | None
    prob_above: Decimal | None
    normal_value: Decimal | None  # 권역 평년값(normalYear)
    similar_low: Decimal | None  # '비슷' 구간 하한
    similar_high: Decimal | None  # '비슷' 구간 상한
    published_at: datetime


def _to_decimal(raw: str | None) -> Decimal | None:
    if raw is None or not raw.strip():
        return None
    try:
        return Decimal(raw.strip())
    except InvalidOperation:
        return None


def _parse_range(raw: str | None) -> tuple[Decimal | None, Decimal | None]:
    """'24.6~25.6' → (24.6, 25.6). 형식이 다르면 (None, None) — 결측 처리, 예외 아님."""
    if raw is None:
        return None, None
    m = _RANGE_RE.match(raw)
    if m is None:
        return None, None
    return _to_decimal(m.group(1)), _to_decimal(m.group(2))


def _category(
    below: Decimal | None, normal: Decimal | None, above: Decimal | None
) -> str:
    """최대 확률 tercile. 전부 결측이거나 동률이면 NORMAL(보수적 판정)."""
    candidates = [("BELOW", below), ("NORMAL", normal), ("ABOVE", above)]
    known = [(name, v) for name, v in candidates if v is not None]
    if not known:
        return "NORMAL"
    best = max(v for _, v in known)
    winners = [name for name, v in known if v == best]
    return winners[0] if len(winners) == 1 else "NORMAL"


def _target_months(published: date) -> list[date]:
    """발표월 다음 1~3개월. 연말 발표는 해를 넘긴다(12월 발표 → 1·2·3월)."""
    months: list[date] = []
    for step in (1, 2, 3):
        total = published.month + step - 1
        months.append(date(published.year + total // 12, total % 12 + 1, 1))
    return months


def parse_outlook_xml(raw: bytes, published: date) -> list[OutlookRecord]:
    """RSS XML을 권역×월×지표 레코드로 변환. 유효성 검증 실패 시 ValueError."""
    root = ElementTree.fromstring(raw)  # 비XML(HTML 에러페이지)이면 여기서 ParseError
    if root.tag != "rss":
        raise ValueError(f"예상과 다른 루트 태그: <{root.tag}>")

    targets = _target_months(published)
    records: list[OutlookRecord] = []

    for indicator, container_tag, name_tag, token in _SECTIONS:
        containers = root.findall(f".//{container_tag}")
        if not containers:
            raise ValueError(f"<{container_tag}> 권역 블록이 없음 — 스키마 변경 의심")
        for container in containers:
            zone_name = (container.findtext(name_tag) or "").strip()
            if not zone_name:
                continue
            for idx, target_month in enumerate(targets, start=1):
                prefix = f"month{idx}_{token}"
                # 확률 태그는 <month_local_ta> 하위에 있어 자식이 아니라 후손으로 찾는다.
                below = _to_decimal(container.findtext(f".//{prefix}_minVal"))
                normal = _to_decimal(container.findtext(f".//{prefix}_similarVal"))
                above = _to_decimal(container.findtext(f".//{prefix}_maxVal"))
                if below is None and normal is None and above is None:
                    continue  # 그 월 블록이 비어 있으면 건너뜀(결측 방어)
                low, high = _parse_range(container.findtext(f".//{prefix}_similarRange"))
                records.append(
                    OutlookRecord(
                        zone_name=zone_name,
                        target_month=target_month,
                        indicator=indicator,
                        category=_category(below, normal, above),
                        prob_below=below,
                        prob_normal=normal,
                        prob_above=above,
                        normal_value=_to_decimal(container.findtext(f".//{prefix}_normalYear")),
                        similar_low=low,
                        similar_high=high,
                        published_at=datetime(
                            published.year, published.month, published.day, tzinfo=KST
                        ),
                    )
                )
    if not records:
        raise ValueError("확률값이 하나도 파싱되지 않음")
    return records


def _looks_like_outlook_xml(body: bytes) -> bool:
    """HTTP 200 + HTML 에러페이지를 걸러낸다(실측된 실제 케이스)."""
    head = body[:200].lstrip()
    return head.startswith(b"<?xml") or head.startswith(b"<rss")


def fetch_latest_outlook(
    as_of: date, timeout: float = 20.0, max_months_back: int = 2
) -> tuple[list[OutlookRecord], date]:
    """as_of 기준 가장 최근 발표분을 찾아 (레코드, 발표일) 반환.

    발표일 이동을 흡수하기 위해 각 월의 23일 주변을 탐색하고, 그 달에 아직 발표가
    없으면 이전 달로 물러난다. 전부 실패하면 OutlookFetchError.
    """
    attempted: list[str] = []
    for months_back in range(max_months_back + 1):
        total = as_of.month - months_back - 1
        anchor = date(as_of.year + total // 12, total % 12 + 1, RELEASE_DAY)
        for offset in PROBE_OFFSETS:
            candidate = anchor + timedelta(days=offset)
            if candidate > as_of:
                continue  # 미래 발표분은 없음
            stamp = candidate.strftime("%Y%m%d")
            attempted.append(stamp)
            try:
                resp = httpx.get(URL_TEMPLATE.format(stamp=stamp), timeout=timeout)
            except httpx.HTTPError:
                continue
            if resp.status_code != 200 or not _looks_like_outlook_xml(resp.content):
                continue
            try:
                return parse_outlook_xml(resp.content, candidate), candidate
            except (ElementTree.ParseError, ValueError):
                continue
    raise OutlookFetchError(f"유효한 3개월전망 XML 없음 — 시도한 날짜: {attempted}")
