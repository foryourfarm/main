"""읍면동 토양 기준값 확보 — 흙토람 토양검정 → 경지구분 필터 → 평균 → 캐시 (DB.md §3.9).

왜 읍면동인가(PRD.md §5, 실측 근거): 흙토람 토양검정은 읍면동 법정동코드로만 조회되고
(시/군 코드는 "데이터 없음"), 시/군 안 편차가 매우 커서 평균이 유저 밭과 무관해진다.

왜 경지구분 필터인가: 같은 읍면동에서도 값이 크게 다르다(실측: 순천 삼거동 밭 유기물 20 vs
과수 51~62). 등록 작물의 재배 형태에 맞는 표본만 평균한다(crop.exam_field_type).

캐시: (읍면동, 경지구분) 단위로 저장해 같은 동네 재등록 시 외부 API를 다시 부르지 않는다(§12).
"""

import csv
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from statistics import mean

from sqlalchemy.orm import Session

from app.infra.public_api.base import PublicApiError
from app.infra.public_api.soil_exam_client import SoilExam, get_soil_exam_list
from app.models import DistrictSoil

# 조회 표본 수 상한. 흙토람은 페이지 단위로 주며, 읍면동 하나의 대표값을 잡는 데
# 이 정도면 충분하다(더 늘리면 호출 비용만 커진다).
PAGE_SIZE = 100

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

# 조회할 리 수 상한. 리 하나가 4초쯤 걸려 전부 돌면 등록이 1분을 넘는다. 리는 같은 면
# 안이라 토양이 비슷하고 표본도 리당 수십 건씩 나와, 앞 몇 곳만으로 대표값이 선다.
# ponytail: 상한 5. 리 간 편차가 문제되면 표본 수 기준(예: 100건까지)으로 바꾼다.
RI_SAMPLE_LIMIT = 5


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
    """그 읍면동에 속한 리 코드들. 리가 없는 동이면 빈 리스트."""
    return _ri_by_eupmyeondong().get(bjd_code[:8], [])


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
        "sample_count": len(matched),
    }


def _fetch_exams(bjd_code: str) -> tuple[list[SoilExam], str | None]:
    """(표본, 실제 조회에 쓴 코드). 신규 코드가 비면 통합 전 코드로 1회 재시도한다.

    전부 실패/빈 결과면 (빈 리스트, None) — 등록을 막지 않는다(§12).
    """
    candidates = [bjd_code]
    old = legacy_bjd_code(bjd_code)
    if old is not None:
        candidates.append(old)

    for code in candidates:
        try:
            exams = get_soil_exam_list(code, page_no=1, page_size=PAGE_SIZE)
        except (PublicApiError, OSError):
            continue  # 데이터 없음(301)·파라미터 오류(201)·네트워크 실패 → 다음 후보
        if exams:
            return exams, code

    # 읍·면은 리 코드로만 기록돼 있다(위 _BJD_CSV 주석). 리를 앞에서부터 모은다.
    pooled: list[SoilExam] = []
    sampled = 0
    for ri in ri_codes(bjd_code)[:RI_SAMPLE_LIMIT]:
        try:
            exams = get_soil_exam_list(ri, page_no=1, page_size=PAGE_SIZE)
        except (PublicApiError, OSError):
            continue
        if exams:
            pooled.extend(exams)
            sampled += 1
    if pooled:
        return pooled, f"{bjd_code} 리 {sampled}곳"
    return [], None


def get_or_fetch(db: Session, bjd_code: str, field_type: str) -> DistrictSoil:
    """캐시 우선. 미스면 흙토람 조회 후 저장한다.

    외부 API 실패 시에도 등록을 막지 않는다 — 표본 0건으로 기록하고 진행한다(§12).
    토양 지표는 결측이 되어 적합도가 기상만으로 산출된다.
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
    if cached is not None and cached.sample_count > 0:
        return cached

    exams, queried_code = _fetch_exams(bjd_code)
    if queried_code is None:
        source = f"{SOURCE_PREFIX}(조회 실패 — 표본 없음)"
    elif queried_code.startswith(f"{bjd_code} 리 "):
        # 읍면동 전체가 아니라 리 일부만 표집했다는 사실을 숨기지 않는다(§18-4).
        source = f"{SOURCE_PREFIX}({queried_code}, 경지구분 {field_type})"
    elif queried_code != bjd_code:
        source = f"{SOURCE_PREFIX}(읍면동 {queried_code} 통합전코드, 경지구분 {field_type})"
    else:
        source = f"{SOURCE_PREFIX}(읍면동 {bjd_code}, 경지구분 {field_type})"

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
