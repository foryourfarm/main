"""`0019` 부분 적용 잔여분 backfill — 지침 6건 (프로덕션 데이터 사고 복구).

**체인 위치가 특이하다: `0038` → 이 파일 → `0039`.** 번호는 0042지만 0039보다 **먼저** 돈다.
`0039`가 백필 전에 대상 행의 존재·허용경계를 `_assert_band`로 검증하고 다르면 `RuntimeError`로
죽기 때문이다 — 그 검증이 통과하려면 이 복구가 앞서야 한다. `0038`~`0041`은 어느 환경에도
적용된 적이 없어(로컬·프로덕션 모두 `0037`) 체인 중간에 끼워도 이력 재작성이 아니다.

## 무엇이 있었나

프로덕션에서 `alembic upgrade head`가 `0039`에서 죽었다(2026-08-05):

    RuntimeError: 0039: crop=3 ph 지침 행이 없다 — 백필 대상이 사라졌다.

진단 스크립트로 전수 대조하니 프로덕션에만 **행 없음 4건 + 값 불일치 2건**이 있었다.
같은 대조를 로컬(`0037`, 전 마이그레이션 정상 적용)에 돌리면 **0건**이다 — 즉 `0039`의
기대값은 옳고 프로덕션 DB만 어긋나 있었다.

    행 없음      오이 ph · 상추 ph · 상추 p2o5 · 오이 temp_day(growing)
    값 불일치    상추 temp_day spring·fall: DB 4~30 vs 기대 2.5~36

**여섯 건 모두 `0019`(오이·상추·감자 생육 기준 문헌 갱신) 소관이다.** 값 불일치 쪽은
프로덕션이 `0019` 이전 값(4~30)을 그대로 들고 있다는 뜻이고, 로컬 `source_ref`가
`문보흠·조일환`(= `0019`가 심는 출처)인 것으로 확인했다.

## 이미 한 번 겪은 사고다

`0027`이 같은 이유로 존재한다 — 2026-08-02 실배포에서 **감자 `organic` 전기간 지침이
프로덕션에 없었다.** `0019`는 적용 완료로 표시돼 있어(당시 head가 이미 훨씬 뒤였다) 재실행
대상이 아니라 backfill 대상이었고, 그때 원인은 특정하지 못했다(재현 불가능한 과거 배포 사고).
**그때는 눈에 띈 한 건만 고쳤다** — 화면에 증상이 뜬 감자 밭 하나로 발견했기 때문이다.
나머지 6건은 그대로 남아 있었고, `0039`의 검증이 비로소 전수로 드러냈다.

교훈은 "부분 적용을 확인하는 장치가 마이그레이션 성공 여부와 별개로 필요하다"는 것이다.
`0039`의 `_assert_band`가 그 역할을 우연히 해냈다 — 이 파일은 그 검증을 통과시키려는 것이
아니라 **검증이 옳게 지적한 결손을 실제로 메우는 것**이다.

## 어떻게

`0027`과 같은 패턴이다 — 없으면 넣고(`WHERE NOT EXISTS`), 값이 다르면 맞춘다. 멱등이라
정상 DB(로컬)에서는 **아무것도 바뀌지 않는다**(UPDATE는 값이 이미 같고 INSERT는 스킵된다).
그래서 `0039`가 로컬에서도 프로덕션에서도 같게 동작한다.

`source_ref`는 값을 넣는 행에만 적는다 — 이미 있는 행의 근거 서술을 이 파일이 덮으면
원본(`0019`·`0031`)과 갈릴 위험만 생긴다.

**downgrade는 값 복원을 하지 않는다.** 되돌릴 "원래 상태"가 프로덕션의 결손 그 자체이고,
그것을 재현하는 것은 사고를 되살리는 일이다. 이 파일이 넣은 행만 지운다.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0042"
# 🔴 0038 뒤, 0039 앞이다(위 docstring 참고). 0039.down_revision이 이 값을 가리킨다.
down_revision: str | None = "0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# `0020`이 심어 둔 지표별 감쇠폭(전국 실측 산포도). 새로 넣는 행도 같은 값을 써야 위험구간
# 곡선이 다른 행과 갈리지 않는다. 출처: outcomes/memory/indicator_dispersion.json
_RISK_WIDTH = {"ph": "0.4641", "p2o5": "275.3322", "temp_day": "2.219"}
_RISK_WIDTH_SOURCE = (
    "risk_width=2.0 x robust_sd(1.4826 x MAD), 전국 실측 산포도. "
    "출처 outcomes/memory/indicator_dispersion.json"
)

# 없으면 넣을 행. (crop_id, growth_stage, indicator, omin, omax, amin, amax, weight, source)
# 값·weight·출처는 정상 적용된 DB(로컬 0037)에서 그대로 읽어왔다 — 여기서 새로 정하지 않는다.
_INSERT_ROWS: list[tuple[int, str | None, str, str, str, str, str, str, str]] = [
    (
        3, None, "ph", "6.0", "6.5", "5.5", "6.8", "1.5",
        "optimal 6.0~6.5는 RDA 「작물별 비료사용처방」 5차 개정본(2022) p103 시설재배토양 "
        "진단기준표, allowed 5.5~6.8은 제주특별자치도 농업기술원 과채류(오이) 재배기술서의 "
        "'약산성에서 중성으로 pH 5.5~6.8이 적당'(재배 가능 범위). 두 값은 모순이 아니라 역할이 "
        "다르다 — 처방기준은 토양검정 판정 최적구간, 제주 자료는 재배 가능 범위. "
        "[0042 backfill] 0019 부분 적용으로 프로덕션에 이 행이 없어 복구했다.",
    ),
    (
        5, None, "ph", "6.5", "7.0", "6.25", "7.25", "1.5",
        "농촌진흥청(RDA 2022) 노지 상추 재배 토양 화학성 표준 적정범위(진단기준표). "
        "[0042 backfill] 0019 부분 적용으로 프로덕션에 이 행이 없어 복구했다.",
    ),
    (
        5, None, "p2o5", "250", "400", "175", "475", "1.0",
        "농촌진흥청(RDA 2022) 노지 상추 토양 진단기준표 — 유효인산. "
        "[0042 backfill] 0019 부분 적용으로 프로덕션에 이 행이 없어 복구했다.",
    ),
    (
        3, "growing", "temp_day", "25", "28", "5", "35", "2.0",
        "제주특별자치도 농업기술원 과채류(오이) 재배기술서 — 노지 생육적온(주간) 25~28도, "
        "35도 이상/5도 이하 시 생육 중지. crop_code 04009가 노지재배 코드인데 기존값(20~22)은 "
        "시설재배 외기 근사였던 것을 실측 노지 문헌으로 교체"
        "(outcomes/memory/crop_rules/cucumber.json). "
        "[0042 backfill] 0019 부분 적용으로 프로덕션에 이 행이 없어 복구했다.",
    ),
]

# 값만 맞출 행(행은 있는데 `0019` 이전 값이 남아 있다). source_ref는 건드리지 않는다.
# (crop_id, growth_stage, indicator, omin, omax, amin, amax)
_FIX_ROWS: list[tuple[int, str, str, str, str, str, str]] = [
    (5, "spring", "temp_day", "22", "24", "2.5", "36"),
    (5, "fall", "temp_day", "22", "24", "2.5", "36"),
]

# 파라미터를 명시적으로 캐스팅한다. `INSERT ... SELECT`에서는 Postgres가 대상 컬럼 타입으로
# 추론해 주지 않아 `AmbiguousParameter: inconsistent types deduced`로 죽는다(0031이 실측).
_INSERT_SQL = sa.text(
    """
    INSERT INTO crop_growth_guide
        (crop_id, growth_stage, indicator, optimal_min, optimal_max,
         allowed_min, allowed_max, weight, source_ref, confidence,
         risk_width, risk_width_source)
    SELECT CAST(:crop AS integer), CAST(:stage AS varchar), CAST(:ind AS varchar),
           CAST(:omin AS numeric), CAST(:omax AS numeric),
           CAST(:amin AS numeric), CAST(:amax AS numeric),
           CAST(:w AS numeric), CAST(:src AS varchar),
           'domestic_measured', CAST(:rw AS numeric), CAST(:rws AS varchar)
    WHERE NOT EXISTS (
        SELECT 1 FROM crop_growth_guide
        WHERE crop_id = :crop AND indicator = CAST(:ind AS varchar)
          AND growth_stage IS NOT DISTINCT FROM CAST(:stage AS varchar)
    )
    """
)

_FIX_SQL = sa.text(
    """
    UPDATE crop_growth_guide
       SET optimal_min = CAST(:omin AS numeric), optimal_max = CAST(:omax AS numeric),
           allowed_min = CAST(:amin AS numeric), allowed_max = CAST(:amax AS numeric)
     WHERE crop_id = :crop AND growth_stage = CAST(:stage AS varchar)
       AND indicator = CAST(:ind AS varchar)
    """
)


def upgrade() -> None:
    conn = op.get_bind()
    for crop, stage, ind, omin, omax, amin, amax, weight, source in _INSERT_ROWS:
        conn.execute(
            _INSERT_SQL,
            {
                "crop": crop, "stage": stage, "ind": ind,
                "omin": omin, "omax": omax, "amin": amin, "amax": amax,
                "w": weight, "src": source,
                "rw": _RISK_WIDTH[ind], "rws": _RISK_WIDTH_SOURCE,
            },
        )
    for crop, stage, ind, omin, omax, amin, amax in _FIX_ROWS:
        conn.execute(
            _FIX_SQL,
            {
                "crop": crop, "stage": stage, "ind": ind,
                "omin": omin, "omax": omax, "amin": amin, "amax": amax,
            },
        )


def downgrade() -> None:
    # 이 파일이 넣은 행만 지운다(위 docstring 참고 — 값 복원은 사고 재현이라 하지 않는다).
    #
    # 행 단위 `IN ((3, NULL, 'ph'), …)`을 쓰지 않는다 — NULL은 `=` 비교가 참이 되지 않아
    # `growth_stage IS NULL`인 세 행이 **조용히 안 지워진다**(삭제 0건인데 성공으로 끝난다).
    conn = op.get_bind()
    for crop, stage, ind, *_ in _INSERT_ROWS:
        conn.execute(
            sa.text(
                "DELETE FROM crop_growth_guide "
                " WHERE crop_id = :crop AND indicator = CAST(:ind AS varchar)"
                "   AND growth_stage IS NOT DISTINCT FROM CAST(:stage AS varchar)"
            ),
            {"crop": crop, "stage": stage, "ind": ind},
        )
