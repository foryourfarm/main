"""crop_growth_guide 성격 메타 컬럼 5종 추가 (스키마만, 값은 0039가 백필) — finalplan.md P1.

**왜**: `crop_growth_guide`는 지금 밴드 경계값(`allowed_min`/`allowed_max`)만 갖고 있고
그 경계가 어떤 **성격**인지(문헌이 준 절대한계인지, 재배 가능 범위인지, 완충 휴리스틱인지)를
표현할 곳이 없다. `outcomes/`(FarmML 이관 계약)의 `scoring.py.boundary_score()`는 이미
`allowed_min_kind`/`allowed_max_kind`에 따라 경계 점수를 0점 또는 60점으로 가른다
(`literature_limit`만 0점) — 두 구현이 같은 값을 쓰려면 백엔드도 이 성격을 저장해야 한다.
지금은 스키마만 만든다. 값 백필은 `0039`, 채점 로직 반영은 P2(이번 범위 밖).

**컬럼 5개, 전부 NULL 허용**(표기가 없는 밴드가 실재한다 — 추측 금지):

- `cultivation_type`: `open_field` | `facility`. 그 지표 기준표가 노지/시설 중 어느 쪽
  문헌인지의 출처 속성. 경계값 자체와는 무관하다.
- `allowed_min_kind`, `allowed_max_kind`: **방향별로 2컬럼**. 하나로 합치지 않는다 —
  사과 기온(`outcomes/memory/crop_rules/apple.json` temperature_guides)은 하한이
  `cultivable_range`(arccas 가능지 문헌값)이고 상한이 `heuristic`(±50% 대체값)이라,
  한 컬럼으로 합치면 반드시 한쪽이 거짓 표기가 된다.
- `method`: 측정 프로토콜 서술(예: "1:5 물(H2O) 침출, pH meter"). 계약의 서술이 길어
  기존 `source_ref`(VARCHAR)와 달리 `Text`로 둔다.
- `code_scores`: JSONB, 등급코드→점수 배점표(`subsoil_texture` 같은 범주형 지표용).
  `subsoil_texture` 지침 행 자체가 아직 없어(P4 작업) 지금은 항상 NULL이다.

**`allowed_min_kind`/`allowed_max_kind` CHECK 제약**: 허용값은 정확히 6개
(`outcomes/scripts/ml/scoring.py` `ALLOWED_KINDS`) — `literature_limit`, `cultivable_range`,
`literature_threshold`, `derived`, `heuristic`, `not_applicable`. 오타가 조용히
"표기 없음"(NULL)이나 다른 성격으로 채점되는 사고를 DB 단에서 막는다. `outcomes` 쪽은 이
집합을 벗어나면 `ValueError`를 낸다 — 같은 방어를 여기서도 건다.

`cultivation_type` CHECK도 같은 이유로 건다(`open_field`/`facility` 외 값 방지).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0038"
down_revision: str | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# outcomes/scripts/ml/scoring.py ALLOWED_KINDS와 정확히 같아야 한다 — 어긋나면 그 값이
# 채점 시(P2 반영 후) 이관 스크립트에서 ValueError로 죽는다.
_ALLOWED_KINDS = (
    "literature_limit",
    "cultivable_range",
    "literature_threshold",
    "derived",
    "heuristic",
    "not_applicable",
)
_ALLOWED_KIND_SQL = ", ".join(f"'{k}'" for k in _ALLOWED_KINDS)


def upgrade() -> None:
    op.add_column(
        "crop_growth_guide", sa.Column("cultivation_type", sa.String(), nullable=True)
    )
    op.add_column(
        "crop_growth_guide", sa.Column("allowed_min_kind", sa.String(), nullable=True)
    )
    op.add_column(
        "crop_growth_guide", sa.Column("allowed_max_kind", sa.String(), nullable=True)
    )
    op.add_column("crop_growth_guide", sa.Column("method", sa.Text(), nullable=True))
    op.add_column(
        "crop_growth_guide", sa.Column("code_scores", postgresql.JSONB(), nullable=True)
    )

    op.execute(
        "ALTER TABLE crop_growth_guide ADD CONSTRAINT ck_guide_cultivation_type "
        "CHECK (cultivation_type IS NULL OR cultivation_type IN ('open_field', 'facility'))"
    )
    op.execute(
        "ALTER TABLE crop_growth_guide ADD CONSTRAINT ck_guide_allowed_min_kind "
        f"CHECK (allowed_min_kind IS NULL OR allowed_min_kind IN ({_ALLOWED_KIND_SQL}))"
    )
    op.execute(
        "ALTER TABLE crop_growth_guide ADD CONSTRAINT ck_guide_allowed_max_kind "
        f"CHECK (allowed_max_kind IS NULL OR allowed_max_kind IN ({_ALLOWED_KIND_SQL}))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE crop_growth_guide DROP CONSTRAINT IF EXISTS ck_guide_allowed_max_kind")
    op.execute("ALTER TABLE crop_growth_guide DROP CONSTRAINT IF EXISTS ck_guide_allowed_min_kind")
    op.execute("ALTER TABLE crop_growth_guide DROP CONSTRAINT IF EXISTS ck_guide_cultivation_type")

    op.drop_column("crop_growth_guide", "code_scores")
    op.drop_column("crop_growth_guide", "method")
    op.drop_column("crop_growth_guide", "allowed_max_kind")
    op.drop_column("crop_growth_guide", "allowed_min_kind")
    op.drop_column("crop_growth_guide", "cultivation_type")
