"""법정동 토양 기준값 확보 — 흙토람 토양검정 → 경지구분 필터 → 평균 → 캐시 (DB.md §3.9).

왜 법정동 말단인가(PRD.md §5, 실측 근거): 흙토람 토양검정은 검정 기록이 있는 최말단
법정동코드로만 조회된다 — 시/군 코드는 "데이터 없음"이고, 리가 있는 읍·면도 마찬가지다
(면 코드로 물으면 301). 게다가 시/군 안 편차가 매우 커서 상위 단위 평균은 유저 밭과 무관해진다.
말단 판정·선택지 노출은 is_leaf_bjd / farm_service.list_districts.
설계: docs/design/ri-level-district.md

왜 경지구분 필터인가: 같은 법정동에서도 값이 크게 다르다(실측: 순천 삼거동 밭 유기물 20 vs
과수 51~62). 등록 작물의 재배 형태에 맞는 표본만 평균한다(crop.exam_field_type).

캐시: (법정동, 경지구분) 단위로 저장해 같은 동네 재등록 시 외부 API를 다시 부르지 않는다(§12).
"""

import csv
import logging
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from statistics import mean

import httpx
from sqlalchemy.orm import Session

from app.infra.public_api.base import PublicApiError
from app.infra.public_api.soil_exam_client import SoilExam, get_soil_exam_list
from app.models import DistrictSoil

_log = logging.getLogger(__name__)

# 흙토람이 "그 코드에 기록이 없다"고 **답한** 코드. 조회 자체는 성공했다는 뜻이라
# 네트워크 실패와 구분해야 한다 — 전자는 데이터 한계, 후자는 우리 장애다(§18-4).
NO_DATA_CODE = "301"

# 한 페이지에 받는 표본 수. 흙토람이 허용하는 최대치다.
PAGE_SIZE = 100

# 페이지 수 상한 = 표본 2,000건. 실측 최대는 227건(고창읍 5279025031)이라 넉넉하지만,
# 상한이 없으면 병적으로 많은 리 하나가 밭 등록 한 번에 수백 콜을 낸다(§18-1).
# ponytail: 고정 상한. 실제로 2,000건을 넘는 리가 나오면 그때 Total_Count 기반으로 바꾼다.
MAX_PAGES = 20

SOURCE_PREFIX = "흙토람 토양검정"

# 행정통합으로 시군구 코드가 재부여된 지역의 신→구 앞5자리 대응.
# 흙토람은 통합 전 코드로만 데이터를 갖고 있어(검정 기록이 통합 전 시점) 신규 코드로는
# "데이터 없음"이 온다. 통합 시 읍면동 이하 5자리는 그대로라 앞 5자리만 치환하면 된다.
# 생성: scripts/gen_legacy_bjd_map.py (docs/seed/legacy_sgg_code.csv)
_LEGACY_CSV = Path(__file__).resolve().parents[3] / "docs" / "seed" / "legacy_sgg_code.csv"


@lru_cache(maxsize=1)
def legacy_prefix_map() -> dict[str, str]:
    """{신규 앞5자리: 옛 앞5자리}. 시드가 없으면 빈 맵(폴백 없이 동작)."""
    if not _LEGACY_CSV.exists():
        return {}
    with _LEGACY_CSV.open(encoding="utf-8") as f:
        return {r["new_sgg_prefix"]: r["legacy_sgg_prefix"] for r in csv.DictReader(f)}


def legacy_bjd_code(bjd_code: str) -> str | None:
    """통합 지역이면 옛 코드를, 아니면 None."""
    old = legacy_prefix_map().get(bjd_code[:5])
    return None if old is None else old + bjd_code[5:]


# 흙토람은 리가 있는 읍·면의 검정 기록을 **리 코드**로만 갖고 있다. 면 코드(리 자리 `00`)로
# 물으면 데이터가 있어도 301 "요청 데이터 없음"이 온다(실측: 부여 장암면 4476042000 → 301,
# 점상리 4476042021 → 100건). 리가 없는 동은 읍면동 코드가 곧 최종 코드라 영향이 없다.
# 이걸 몰라 농촌(읍·면) 전역이 토양 결측이었다 — 정작 귀농인 밭이 있는 곳이다.
_BJD_CSV = Path(__file__).resolve().parents[3] / "docs" / "seed" / "bjd_to_region.csv"


@lru_cache(maxsize=1)
def _ri_by_eupmyeondong() -> dict[str, list[str]]:
    """{읍면동 앞8자리: [리 법정동코드…]}. 시드가 없으면 빈 맵(리 조회 없이 동작)."""
    if not _BJD_CSV.exists():
        return {}
    out: dict[str, list[str]] = {}
    with _BJD_CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["ri"]:
                out.setdefault(row["bjd_code"][:8], []).append(row["bjd_code"])
    return {k: sorted(v) for k, v in out.items()}


def ri_codes(bjd_code: str) -> list[str]:
    """같은 읍면동에 속한 리 코드들. 리가 없는 동이면 빈 리스트.

    주의: 앞 8자리로 묶으므로 **리 코드를 넣으면 형제 리 전체(자기 포함)가 나온다** — 리와
    부모 면은 앞 8자리를 공유한다(공음면 5279034000, 구암리 5279034023). 그래서 말단 판정은
    이 함수를 직접 쓰지 않고 is_leaf_bjd를 쓴다.
    """
    return _ri_by_eupmyeondong().get(bjd_code[:8], [])


def is_leaf_bjd(bjd_code: str) -> bool:
    """법정동 말단인가 — 유저가 고를 수 있는 단위이자 흙토람이 검정 기록을 갖는 단위.

    법정동코드 10자리는 시도(2)+시군구(3)+읍면동(3)+리(2)다. 뒤 2자리가 `00`이면 읍면동
    자체이고, 아니면 리다(시드 20,275행 전수 확인: 예외 0건).

    리를 가진 읍·면은 말단이 아니다 — 그 코드로 흙토람에 물으면 데이터가 있어도 301이 온다.
    """
    if bjd_code[8:] != "00":
        return True  # 리 코드 자체
    return not ri_codes(bjd_code)


def _avg(values: list[Decimal | None]) -> Decimal | None:
    """결측을 제외하고 평균. 남는 값이 없으면 None(§12 결측 방어)."""
    present = [v for v in values if v is not None]
    if not present:
        return None
    return Decimal(str(round(float(mean(float(v) for v in present)), 2)))


def summarize(exams: list[SoilExam], field_type: str) -> dict[str, object]:
    """경지구분에 맞는 표본만 골라 평균한다. 표본이 없으면 값 전부 None + sample_count=0.

    순수 함수(DB·네트워크 무관) — 필터·평균 규칙을 테스트로 고정한다.
    """
    matched = [e for e in exams if e.field_type_code == field_type]
    return {
        "field_type": field_type,
        "ph": _avg([e.ph for e in matched]),
        "ec": _avg([e.ec for e in matched]),
        "p2o5": _avg([e.avail_p for e in matched]),
        "organic_matter": _avg([e.organic_matter for e in matched]),
        # 치환성 양이온(cmol/kg) — 흙토람이 주는 값을 그동안 버리고 있었다(0024에서 컬럼 추가).
        "k": _avg([e.k for e in matched]),
        "ca": _avg([e.ca for e in matched]),
        "mg": _avg([e.mg for e in matched]),
        "sample_count": len(matched),
    }


def _fetch_all_pages(code: str) -> list[SoilExam]:
    """한 법정동코드의 검정 표본 **전체**. 짧은 페이지가 오면 끝이다.

    **종전엔 1페이지만 읽어 잘리고 있었다** — 실측(2026-08-03): 고창읍 5279025031이 227건,
    5279025035가 162건, 부여 점상리 4476042021이 141건, 4476042027이 200건 이상. 첫 100건만
    평균하면 두 가지가 틀어진다:

    ⓐ 흙토람이 어떤 순서로 주는지 모르니 **편향 여부조차 알 수 없다**(연도순인지 지번순인지
      명세서에 없다). 지역 기준값이 "첫 100건 평균"이라는 사실 자체가 근거 없는 근사다.
    ⓑ **뒤 페이지에만 있는 경지구분 표본을 통째로 놓친다.** 1페이지가 논으로만 채워지면 그
      리는 "과수 표본 없음"으로 잘못 판정되고, 과수 밭이 토양 지표를 전부 잃는다 —
      §18-4가 금지하는 "데이터 한계인 척하는 우리 결함"이다.

    `Total_Count`가 응답 body에 있지만(실측: 227) 읽지 않는다 — 짧은 페이지로 끝을 아는 것이
    `fetch_items`에 body 필드 노출을 추가하는 것보다 코드가 적고, 마지막 페이지가 딱
    PAGE_SIZE로 끝나도 다음 페이지가 `code=200`·0건으로 와서 정상 종료된다(실측 확인).
    """
    out: list[SoilExam] = []
    for page in range(1, MAX_PAGES + 1):
        try:
            exams = get_soil_exam_list(code, page_no=page, page_size=PAGE_SIZE)
        except (PublicApiError, httpx.HTTPError):
            if page == 1:
                raise  # 첫 페이지 실패는 호출부가 "우리 장애 vs 기록 없음"으로 가른다
            # 뒤 페이지 실패로 **이미 받은 표본을 버리지 않는다**(§12). 표본이 줄 뿐이고,
            # 0건으로 되돌리면 있는 데이터를 두고 "기록 없음"이라 말하게 된다.
            _log.warning(
                "흙토람 %d페이지 실패 bjd=%s — 받은 %d건으로 진행", page, code, len(out), exc_info=True
            )
            return out
        out += exams
        if len(exams) < PAGE_SIZE:
            return out
    _log.warning(
        "흙토람 표본이 상한 %d건을 넘었다 bjd=%s — 이후 페이지는 버린다", MAX_PAGES * PAGE_SIZE, code
    )
    return out


def _fetch_exams(bjd_code: str) -> tuple[list[SoilExam], str | None, bool]:
    """(표본, 실제 조회에 쓴 코드, 조회 실패 여부). 신규 코드가 비면 통합 전 코드로 1회 재시도한다.

    전부 실패/빈 결과면 (빈 리스트, None, ...) — 등록을 막지 않는다(§12).

    **세 번째 값이 "우리 장애"와 "데이터 한계"를 가른다.** 흙토람이 301로 "기록 없음"이라고
    답한 것과 네트워크가 죽어 못 받은 것은 전혀 다른데, 종전엔 둘 다 "표본 0건"으로 나가
    유저가 우리 장애를 지역 데이터 한계로 오해했다(§18-4 위반).

    **종전 `except (PublicApiError, OSError)`는 네트워크 실패를 못 잡았다.** httpx 예외는
    `OSError` 하위가 아니라 `httpx.HTTPError` 계열이다(실측 확인). 그래서 타임아웃·401·5xx가
    그대로 위로 튀어 **밭 등록이 500으로 죽었다** — §12의 "산출이 예외로 죽지 않게 한다"를
    정면으로 어기고 있었다. 2026-08-03 data.go.kr http 중단 때 실제로 이 경로를 탔다.

    이웃 리를 모아 평균하는 폴백이 있었는데 지웠다. 유저가 리를 직접 고르게 된 뒤로
    (list_districts가 말단만 노출) 리 코드로 바로 조회되고, 표집 40곳이 전부 데이터를 줬다
    (14개 시도 균등 표집 28곳 + 고창 공음면 12곳, 통합전 코드 재시도 포함). 즉 폴백은 탈
    자리가 없어졌고, 남겨두면 이웃 리 평균(실측 EC 0.47~8.15, 점수 오차 최대 60점)을 "내 땅
    값"처럼 보여준다 — §18-4·PRD 철학 1 위반. 결측은 채점 커버리지 문구로 정직하게 드러낸다.
    """
    candidates = [bjd_code]
    old = legacy_bjd_code(bjd_code)
    if old is not None:
        candidates.append(old)

    fetch_failed = False
    for code in candidates:
        try:
            exams = _fetch_all_pages(code)
        except PublicApiError as exc:
            # 상대가 답을 준 경우. 301(기록 없음)은 사실이고, 나머지 코드는 우리 잘못일
            # 수 있으니(파라미터 오류 201 등) 실패로 센다.
            if exc.code != NO_DATA_CODE:
                fetch_failed = True
                _log.warning("흙토람 조회 오류 code=%s bjd=%s: %s", exc.code, code, exc)
            continue
        except httpx.HTTPError:
            # 타임아웃·연결 실패·4xx/5xx. **여기가 종전에 안 잡히던 자리다.**
            fetch_failed = True
            _log.warning("흙토람 조회 실패(네트워크) bjd=%s", code, exc_info=True)
            continue
        if exams:
            return exams, code, False
    return [], None, fetch_failed


# 리가 있는 읍·면으로 물었을 때의 문구. "조회 실패"로 뭉개면 유저가 무엇을 하면 되는지
# 알 수 없다 — 리를 고르면 실제로 해결되는 경우라서 다음 행동을 알려줘야 한다.
NO_LEAF_RECORD = f"{SOURCE_PREFIX}(읍·면 단위로는 기록 없음 — 리를 선택하면 조회됩니다)"


# 조회 자체가 실패했을 때. "기록 없음"과 절대 같은 문구를 쓰지 않는다 — 전자는 지역의
# 데이터 한계고 이건 우리 장애다. 유저에게 "다시 시도된다"를 알려 다음 행동을 알 수 있게 한다.
FETCH_FAILED = f"{SOURCE_PREFIX}(토양 정보를 가져오지 못했습니다 — 다음 조회에 다시 시도합니다)"


def source_label(
    bjd_code: str, queried_code: str | None, field_type: str, fetch_failed: bool = False
) -> str:
    """유저에게 그대로 노출되는 출처 문구(§18-4) — 어느 코드로 조회했는지 숨기지 않는다.

    순수 함수. `soil_state.base_source` → `FarmOut.soil_source` → 화면 출처 footer로 흘러가므로
    문구가 곧 유저와의 약속이다. 테스트로 고정한다.

    `fetch_failed`는 "네트워크·API 오류로 못 받음"이다. 종전엔 이 경우도 "표본 없음"으로
    나가 **우리 장애를 지역 데이터 한계처럼 말했다** — 없는 사실을 단정하는 §18-4 위반이다.
    """
    if queried_code is None:
        if fetch_failed:
            return FETCH_FAILED  # 데이터가 없는 게 아니라 못 받은 것이다
        if not is_leaf_bjd(bjd_code):
            return NO_LEAF_RECORD  # 리 전환 전에 등록된 밭이 여기 온다
        return f"{SOURCE_PREFIX}(기록 없음 — 이 지역·경지구분의 토양검정 표본이 없습니다)"
    if queried_code != bjd_code:
        return f"{SOURCE_PREFIX}(법정동 {queried_code} 통합전코드, 경지구분 {field_type})"
    return f"{SOURCE_PREFIX}(법정동 {bjd_code}, 경지구분 {field_type})"


def effective_source(bjd_code: str | None, stored: str, has_values: bool) -> str:
    """저장된 출처 문구를 응답 시점 기준으로 다시 본다.

    문구는 등록 시점에 `soil_state.base_source`로 굳어 스스로 고쳐지지 않는다. 리 단위 전환
    전에 면 코드로 등록된 밭은 "조회 실패 — 표본 없음"을 들고 있는데, 그건 "그 법정동에 기록이
    실제로 없다"(도시 동)는 뜻이라 다음 행동이 없는 막다른 문구다. 정작 이 밭들은 리를 고르면
    해결된다 — 안내가 반대로 나간다.

    **값이 있으면 건드리지 않는다.** 그 문구는 실제 조회 근거이고, 덮으면 없는 결측을
    지어내는 셈이다(§18-4). 고쳐 쓰는 건 지표가 전부 빈 경우뿐이다.
    """
    if has_values or bjd_code is None or is_leaf_bjd(bjd_code):
        return stored
    return f"{NO_LEAF_RECORD}, 표본 0건"


def get_or_fetch(
    db: Session, bjd_code: str, field_type: str, *, refresh: bool = False
) -> DistrictSoil:
    """캐시 우선. 미스면 흙토람 조회 후 저장한다.

    외부 API 실패 시에도 등록을 막지 않는다 — 표본 0건으로 기록하고 진행한다(§12).
    토양 지표는 결측이 되어 적합도가 기상만으로 산출된다.

    Args:
        refresh: 캐시가 있어도 다시 조회한다. **지표 컬럼이 늘어났을 때 필요하다** — 0024로
            치환성 양이온(k·ca·mg)이 생겼지만 그 전에 캐시된 행은 그 값이 NULL이고,
            `sample_count > 0`이라 평소 경로로는 영구히 갱신되지 않는다(그 읍면동에 새로
            등록하는 밭도 양이온이 빈다). 상시 경로에서는 쓰지 않는다 — 무분별 재조회는
            §18-1 위반이다. 지금 호출부는 `scripts/repair_empty_soil_state.py` 하나다.
    """
    cached = (
        db.query(DistrictSoil)
        .filter(DistrictSoil.bjd_code == bjd_code, DistrictSoil.field_type == field_type)
        .first()
    )
    # 표본 0건은 "조회 실패"도 포함한다. 그대로 캐시하면 일시적 장애 한 번에 그 읍면동이
    # 영구히 토양 결측이 된다(실측: 리 코드 버그로 농촌 전역이 이 상태였다). 0건이면
    # 캐시를 믿지 않고 다시 부른다 — get_or_fetch는 밭 등록 때만 불려 재조회 비용이 작다.
    # ponytail: TTL 없이 항상 재시도. 호출이 잦아지면 fetched_at 기준 TTL로 바꾼다.
    if cached is not None and cached.sample_count > 0 and not refresh:
        return cached

    exams, queried_code, fetch_failed = _fetch_exams(bjd_code)
    source = source_label(bjd_code, queried_code, field_type, fetch_failed)

    summary = summarize(exams, field_type)
    values = {
        **{k: v for k, v in summary.items() if k != "field_type"},
        "source": f"{source}, 표본 {summary['sample_count']}건",
    }
    if cached is not None:
        # 0건 행 재조회 — 새로 add하면 (bjd_code, field_type) 유니크에 걸린다.
        for key, value in values.items():
            setattr(cached, key, value)
        db.flush()
        return cached

    row = DistrictSoil(bjd_code=bjd_code, field_type=field_type, **values)
    db.add(row)
    db.flush()
    return row
