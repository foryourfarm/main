"""감자 괴경비대기(tuber) 지침의 누락된 허용하한 보완 (2026-07-29).

**왜**: 0021이 사과에서 고친 것과 같은 결함이다(`docs/guide-seed-known-issues.md` P2).
`allowed_min`이 NULL이면 `_indicator_score`가 `risk_width`를 읽기 전에 0점을 반환한다
(`suitability_service.py:125-130`). 감자 tuber 2행이 그 상태였다.

| indicator | optimal | 기존 allowed | 증상 |
|---|---|---|---|
| temp_day | 23~24 | NULL / 27 | 23도 미만 즉시 0점 (weight 2.5 — 감자 지표 중 최대) |
| temp_night_min | 10~14 | NULL / 28 | 10도 미만 즉시 0점 (weight 2.0) |

**허용하한 산출**: `allowed_min = optimal_min - (optimal_max - optimal_min) x 0.5`.
0019(오이 pH·감자 유기물·상추 유효인산)와 0021(사과 5행)이 이미 쓴 휴리스틱을 그대로
적용한다 — 새 산출식을 만들지 않는다.
- temp_day: 23 - 1 x 0.5 = **22.5**
- temp_night_min: 10 - 4 x 0.5 = **8.0**

상한은 둘 다 문헌값이라 건드리지 않는다 — temp_day 27(농사로 안내책자, 0004),
temp_night_min 28(Zhang 2024 야간 고온 괴경형성 중단, 0012).

**[확인 필요] 이 하한은 문헌이 아니라 휴리스틱이다.** 0019·0021 선례대로 `confidence`는
optimal의 근거를 유지하고 추정임을 `source_ref`에 남긴다. 감자 저온 쪽 붕괴점 문헌
(괴경 비대 정지 온도)을 확보하면 교체 대상.

**[확인 필요] optimal 23~24도 자체도 재확인 대상이다.** 이 하한 보완으로 22.5도까지는
허용, 약 20.3도까지는 위험구간 점수가 매겨지지만 그 아래는 여전히 0점이다. 국내 봄감자
괴경비대기 실제 기온대가 그보다 낮으면 optimal 값이 P1(사과 착색기)과 같은 계열의 시드
매핑 문제일 수 있다. 값은 0004 시드(농사로 안내책자)에서 왔고 원 근거 문서
(`crop-domain-knowledge.md`)가 리포에 없어(P5) 이번엔 판단하지 않았다 — 추측 금지(§3-4).

**주의**: source_ref 문구에 `%`가 들어가 바인드 파라미터로 넘긴다. `op.execute(f"...")`로
문자열 보간하면 psycopg가 `%`를 파라미터 자리표시자로 오인해 깨진다(0019에서 실측 확인).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

POTATO_CROP_ID = 4
TUBER_STAGE = "tuber"

# 허용하한이 문헌이 아니라 휴리스틱임을 행마다 남긴다(§18-4 — 추정치를 실측처럼 표기 금지).
HEURISTIC_NOTE = (
    " | 허용하한은 문헌값이 아니라 추정: allowed_min = optimal_min -(optimal 폭 x 50%), "
    "0019·0021과 동일한 휴리스틱. [확인 필요] 감자 저온 붕괴점 문헌 확보 시 교체."
)

# (indicator, allowed_min). 산출 근거는 모듈 docstring. optimal·상한은 건드리지 않는다.
TUBER_ALLOWED_MIN: tuple[tuple[str, float], ...] = (
    ("temp_day", 22.5),  # 23 - (24-23) x 0.5
    ("temp_night_min", 8.0),  # 10 - (14-10) x 0.5
)


def upgrade() -> None:
    bind = op.get_bind()
    for indicator, allowed_min in TUBER_ALLOWED_MIN:
        bind.execute(
            sa.text(
                "UPDATE crop_growth_guide "
                "SET allowed_min = :amin, "
                # coalesce 없이 `|| :note`는 source_ref가 NULL이면 결과도 NULL — 근거를 조용히 지운다.
                "    source_ref = coalesce(source_ref, '') || :note "
                "WHERE crop_id = :crop AND growth_stage = :stage AND indicator = :indicator"
            ),
            {
                "amin": allowed_min,
                "note": HEURISTIC_NOTE,
                "crop": POTATO_CROP_ID,
                "stage": TUBER_STAGE,
                "indicator": indicator,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    for indicator, _ in TUBER_ALLOWED_MIN:
        bind.execute(
            sa.text(
                "UPDATE crop_growth_guide "
                "SET allowed_min = NULL, source_ref = replace(source_ref, :note, '') "
                "WHERE crop_id = :crop AND growth_stage = :stage AND indicator = :indicator"
            ),
            {
                "note": HEURISTIC_NOTE,
                "crop": POTATO_CROP_ID,
                "stage": TUBER_STAGE,
                "indicator": indicator,
            },
        )
