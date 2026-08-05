"""사과·배 subsoil_texture(심토토성) 범주형 지침 행 신설 (finalplan.md P4).

**왜**: 범주형 배점표(`code_scores`) 채점 경로는 `app/services/suitability_service.py
category_score()`가 이미 구현돼 있다(P2). 이 마이그레이션은 그 경로가 조회할 **데이터**만
넣는다 — 사과(crop_id=1)·배(crop_id=2)의 `subsoil_texture` 지침 행 2개.

**계약 대조 결과: 차이 없음.** `outcomes/memory/crop_rules/{apple,pear}.json`
`physical_overrides.subsoil_texture`를 직접 읽어 아래 `_APPLE_CODE_SCORES`/`_PEAR_CODE_SCORES`와
키·값을 전수 대조했다 — 완전히 같다. `method` 문자열도 두 작물이 계약 원문과 글자 그대로
같다(같은 배점표·같은 환산식이라 문구 자체가 공유된다).

**밴드가 아니다 — optimal/allowed/risk_width 전부 NULL.** 이 지표는 연속 구간이 없는
범주형 조회(등급코드 1~6·99 → 점수)라 밴드 경계라는 개념이 성립하지 않는다. 값을 넣으면
`category_score()`가 아니라 `band_score()`가 이 행을 잘못 집어 없는 순서를 가정하게 된다.

**`allowed_min_kind`/`allowed_max_kind` = NULL, `not_applicable`이 아니다.** `not_applicable`은
"경계가 있으나 그 방향에 감점을 두지 않는다"는 뜻이다(예: 0038 사과 경사 `allowed_min_kind=
not_applicable` — 경사 0%가 하한이라 그 방향 감점이 없을 뿐 하한 자체는 있다). 여기는 하한·상한
이라는 축 자체가 없다(순서가 없는 범주). 있지도 않은 경계에 "감점 없음" 성격을 붙이는 것은
거짓 표기라 NULL로 둔다.

**`weight = 1.0`의 근거(계약에 이 값이 없다 — 구조적 중립값, 추측이 아니다):**
① 백엔드에 이미 있는 다른 토양 지표(ph·organic·p2o5·k·ca·mg)가 전부 1.0이다(pH만 예외적으로
1.5, `0004`·`0012`). ② 원 배점표(심교문 2016) 자체가 토양 물리성 항목마다 20점 만점을 동일하게
배정한다 — 항목 간 차등이 원 문헌에 없다. ③ P3이 토양 축을 지표 개수로 나누는 균등 평균으로
바꿔서(`suitability_service`, 이 마이그레이션이 손대지 않는 파일) 이 `weight`는 주 총점 계산에
개입하지 않고 `score_weighted`(부차 지표) 계산에만 쓰인다 — 주 총점을 좌우하는 자리가 아니므로
1.0 외의 값을 고를 근거도, 필요도 없다.

**`confidence = 'domestic_measured'`.** 계약 근거가 RDA 국립농업과학원 심교문(2016) 배점표이고
climate-soil-integrated-suitability-2021(PJ013548, 국가 문서)이 독립적으로 같은 값을 재확인한다
— 다른 RDA 국내 교본/배점표 기반 토양 지표(`0024`의 k·ca·mg)와 같은 confidence를 쓴다.

**`source_ref`는 계약의 `source` 필드를 그대로 옮긴다**(`0023`이 같은 목적으로 `source_ref`에
계약 서술을 옮긴 전례를 따른다). 사과·배 순위가 정반대라는 사실도 그 서술에 포함되므로
같이 옮긴다 — 감추지 않는다.

**🔴 알려진 한계(결함 아님, 이번 범위 밖) — 적재 배선 없음.** 이 지침 행이 실제로 채점에
쓰이려면 `soil_state.subsoil_texture_code`(`0040`)에 값이 있어야 하는데, `get_soil_profile`
호출자가 현재 0건이고(PNU 19자리 요구, `user_farm`엔 `bjd_code`만 있음) `gather_indicator_values`
도 아직 `subsoil_texture`를 모은다. 즉 이 행은 지금 프로덕션에서 `subsoil_texture:missing`이 될
뿐이다. 새 호출 경로를 만들거나 `gather_indicator_values`를 고치는 것은 이 마이그레이션의 범위가
아니다(각각 별도 작업 — 후자는 다른 에이전트가 직접 넣는다).

**🔴 `uq_guide`(crop_id, growth_stage, indicator)가 `growth_stage IS NULL`에서 중복을 막지
못한다 — 2026-08-05 clean DB(`fyf_replay`) 실측 확인.** Postgres 표준 UNIQUE 제약은 NULL을
서로 다른 값으로 취급해 같은 (crop_id, indicator)에 growth_stage=NULL인 행을 두 번 넣어도
제약이 걸리지 않는다(실측: 임시 행 2개를 넣어 재현, 제약 위반 없이 둘 다 커밋됨 — 정리 후
삭제). 그래서 이 마이그레이션은 DB 제약에 기대지 않고 `WHERE NOT EXISTS`로 자체 방어한다
(`0027`·`0031`이 같은 이유로 쓴 패턴). **재실행 시 동작**: 이미 두 행이 있으면 `WHERE NOT
EXISTS`가 걸려 INSERT가 0행을 갱신하고 조용히 스킵된다(중복 생성 없음) — `upgrade()` 끝의
개수 검증(`crop_id IN (1,2)`가 정확히 2행)이 첫 실행·재실행 양쪽에서 항상 성립함을 확인한다.
"""
import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0041"
down_revision: str | None = "0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 계약 원문(outcomes/memory/crop_rules/{apple,pear}.json physical_overrides.subsoil_texture
# .method) 그대로. 두 작물이 같은 배점표·같은 환산식을 설명하므로 문구가 완전히 같다.
_METHOD = (
    "범주형 조회(scripts/ml/scoring.py category_score) — 밴드가 아니다. 입력은 "
    "data/02_soil_physical_modified.csv의 subsoil_texture_code 원본 등급코드이며 %·순위로 "
    "환산하지 않는다. 국가 배점표 20/15/10/5를 항목 만점 20으로 나눠 백분율화했다"
    "(20→100, 15→75, 10→50, 5→25) — 국가 토양 적지평가가 항목당 20점 만점 합산이므로 "
    "항목점수/20이 그 항목의 0~1 기여도이고, 이 환산은 휴리스틱이 아니라 원 배점표의 산술 "
    "변환이다. 99(기타)는 null로 두어 채점 대상에서 제외한다(추측 금지). [확인 필요] 배점표의 "
    "'토성'이 심토인지 표토인지 원문에 명시가 없다 — 우리 입력은 심토(subsoil)이고, "
    "climate-soil-integrated-suitability-2021 표14가 같은 값을 '심토토성'으로 표기해 심토로 "
    "읽었다."
)

# 계약 원문(source 필드) 그대로 — 사과·배 순위가 정반대라는 사실도 포함해 옮긴다.
_APPLE_SOURCE = (
    "심교문(2016) 「토양·기후요인을 종합적으로 고려한 과수 재배적지 구분」 농촌진흥청 "
    "국립농업과학원 영농기술정보, 사과 토양 배점표: 최적지(20점) 사양질·미사사양질 / 적지(15점) "
    "식양질 / 가능지(10점) 미사식양질·식질 / 저위생산지(5점) 사질·역질·사력질. "
    "knowledge-base/papers/common/rda-fruit-suitability-integration-shim-2016.md. 교차 확인: "
    "climate-soil-integrated-suitability-2021(PJ013548) 표11과 완전 일치(국가 문서 2건 독립 "
    "일치). 🔴 배와 순위가 정반대다 — 배 최적은 식양질·미사식양질이라 같은 흙이 두 작물에서 "
    "100점/50점으로 갈린다. 계산 오류가 아니라 국가 배점표 자체가 작물별로 다르게 준 것이다. "
    "역질·사력질(5점)은 우리 codebook에 코드가 없어 매핑 대상이 아니다. allowed 밴드를 두지 "
    "않은 이유는 범주 지표에 완충구간이라는 개념이 성립하지 않기 때문이다 — CLAUDE.md §8의 "
    "이진 채점 금지는 연속 지표의 절벽을 막는 규칙이고, 이 지표는 4등급 전부에 0이 아닌 점수"
    "(100/75/50/25)가 있어 절벽이 없다."
)
_PEAR_SOURCE = (
    "심교문(2016) 「토양·기후요인을 종합적으로 고려한 과수 재배적지 구분」 농촌진흥청 "
    "국립농업과학원 영농기술정보, 배 토양 배점표: 최적지(20점) 식양질·미사식양질 / 적지(15점) "
    "사양질·미사사양질 / 가능지(10점) 식질 / 저위생산지(5점) 사질·역질·사력질. "
    "knowledge-base/papers/common/rda-fruit-suitability-integration-shim-2016.md. 교차 확인: "
    "climate-soil-integrated-suitability-2021(PJ013548) 표14 심토토성 행과 일치하며, 4차 "
    "리서치에서 나머지 4행까지 확보돼 표가 완성됐다(국가 문서 2건 독립 일치). 🔴 사과와 순위가 "
    "정반대다 — 사과 최적은 사양질·미사사양질이라 같은 흙이 두 작물에서 100점/75점 또는 "
    "50점/100점으로 갈린다. 계산 오류가 아니라 국가 배점표 자체가 작물별로 다르게 준 것이며, "
    "공통 토성 규칙을 쓰면 반드시 한쪽이 틀린다. 역질·사력질(5점)은 우리 codebook에 코드가 "
    "없어 매핑 대상이 아니다. allowed 밴드를 두지 않은 이유는 범주 지표에 완충구간이라는 개념이 "
    "성립하지 않기 때문이다 — 4등급 전부에 0이 아닌 점수(100/75/50/25)가 있어 절벽이 없다"
    "(CLAUDE.md §8)."
)

# 계약 code_scores 그대로(outcomes/memory/crop_rules/{apple,pear}.json). 99(기타)는 None —
# 0점이 아니라 채점 제외.
_APPLE_CODE_SCORES: dict[str, float | None] = {
    "1": 25.0, "2": 100.0, "3": 100.0, "4": 75.0, "5": 50.0, "6": 50.0, "99": None,
}
_PEAR_CODE_SCORES: dict[str, float | None] = {
    "1": 25.0, "2": 75.0, "3": 75.0, "4": 100.0, "5": 100.0, "6": 50.0, "99": None,
}

# (crop_id, code_scores, source_ref)
_ROWS: list[tuple[int, dict[str, float | None], str]] = [
    (1, _APPLE_CODE_SCORES, _APPLE_SOURCE),
    (2, _PEAR_CODE_SCORES, _PEAR_SOURCE),
]

# WHERE NOT EXISTS로 자체 방어(위 docstring — uq_guide는 growth_stage IS NULL 중복을 못 막는다
# 것을 실측 확인). 파라미터 타입은 명시 캐스팅한다(0031과 같은 이유 —
# `INSERT ... SELECT`에서 Postgres가 타입을 추론하지 않아 AmbiguousParameter로 죽는다).
_INSERT = sa.text(
    """
    INSERT INTO crop_growth_guide
        (crop_id, growth_stage, indicator, optimal_min, optimal_max,
         allowed_min, allowed_max, risk_width, weight, cultivation_type,
         allowed_min_kind, allowed_max_kind, method, code_scores, source_ref, confidence)
    SELECT CAST(:crop AS integer), NULL, 'subsoil_texture',
           NULL, NULL, NULL, NULL, NULL,
           CAST(:weight AS numeric), 'open_field', NULL, NULL,
           CAST(:method AS text), CAST(:scores AS jsonb),
           CAST(:src AS varchar), 'domestic_measured'
    WHERE NOT EXISTS (
        SELECT 1 FROM crop_growth_guide
         WHERE crop_id = :crop AND growth_stage IS NULL AND indicator = 'subsoil_texture'
    )
    """
)

_COUNT = sa.text(
    "SELECT count(*) FROM crop_growth_guide "
    "WHERE indicator = 'subsoil_texture' AND crop_id IN (1, 2)"
)

_DELETE = sa.text(
    "DELETE FROM crop_growth_guide WHERE indicator = 'subsoil_texture' AND crop_id IN (1, 2)"
)


def upgrade() -> None:
    conn = op.get_bind()
    for crop_id, code_scores, source in _ROWS:
        result = conn.execute(
            _INSERT,
            {
                "crop": crop_id,
                "weight": 1.0,
                "method": _METHOD,
                "scores": json.dumps(code_scores),
                "src": source,
            },
        )
        if result.rowcount not in (0, 1):
            raise RuntimeError(
                f"0041: crop_id={crop_id} subsoil_texture INSERT가 {result.rowcount}행을 "
                "건드렸다(기대 0 또는 1) — WHERE NOT EXISTS 단일 행 INSERT ... SELECT가 이보다 "
                "더 건드릴 수 없어야 한다."
            )
    count = conn.execute(_COUNT).scalar()
    if count != 2:
        raise RuntimeError(
            f"0041: subsoil_texture 지침 행이 {count}개다(기대 2, crop_id 1·2 각 1행) — "
            "uq_guide는 growth_stage IS NULL에서 중복을 막지 못하므로(실측 확인, 위 docstring) "
            "WHERE NOT EXISTS로 자체 방어했는데도 개수가 틀렸다면 기존 데이터 상태가 예상과 "
            "다르다는 뜻이다."
        )


def downgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(_DELETE)
    if result.rowcount != 2:
        raise RuntimeError(
            f"0041 downgrade: {result.rowcount}행을 삭제했다(기대 2) — subsoil_texture 지침 "
            "행이 upgrade 이후 수동으로 바뀌었을 수 있다."
        )
