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
    if cached is not None:
        return cached

    exams, queried_code = _fetch_exams(bjd_code)
    if queried_code is None:
        source = f"{SOURCE_PREFIX}(조회 실패 — 표본 없음)"
    elif queried_code != bjd_code:
        source = f"{SOURCE_PREFIX}(읍면동 {queried_code} 통합전코드, 경지구분 {field_type})"
    else:
        source = f"{SOURCE_PREFIX}(읍면동 {bjd_code}, 경지구분 {field_type})"

    summary = summarize(exams, field_type)
    row = DistrictSoil(
        bjd_code=bjd_code,
        source=f"{source}, 표본 {summary['sample_count']}건",
        **{k: v for k, v in summary.items() if k != "field_type"},
        field_type=field_type,
    )
    db.add(row)
    db.flush()
    return row
