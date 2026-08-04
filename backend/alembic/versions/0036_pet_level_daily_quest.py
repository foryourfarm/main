"""리텐션 장치(펫·레벨·데일리 퀘스트) 스키마 — PRD.md §14.5.

테이블 하나(`user_daily_quest`) + 컬럼 하나(`users.pet_code`)가 전부다.

**경험치/레벨 컬럼을 만들지 않는다.** 퀘스트 완료 로그의 합이 경험치이고 레벨은 파생값이라
저장할 것이 없다(`app/services/quest_service.py`). 카운터를 따로 두면 로그와 어긋나는 상태가
가능해지고 결정론(CLAUDE.md §2)이 깨진다.

`pet_code`는 nullable — 기존 계정을 백필하지 않는다. NULL은 "아직 안 고름"이고 서비스가
기본 펫으로 읽는다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0036"
down_revision: str | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("pet_code", sa.String(), nullable=True))
    op.create_table(
        "user_daily_quest",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("quest_date", sa.Date(), nullable=False),
        sa.Column("quest_code", sa.String(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        # 하루 한 번을 DB가 강제한다 — 동시 요청 두 개가 애플리케이션 검사를 함께 통과해도 막힌다.
        sa.UniqueConstraint("user_id", "quest_date", "quest_code", name="uq_user_daily_quest"),
    )
    # 조회는 항상 (유저, 날짜) 또는 (유저) 전체 집계라 이 순서면 둘 다 탄다.
    op.create_index("ix_user_daily_quest_user_date", "user_daily_quest", ["user_id", "quest_date"])


def downgrade() -> None:
    op.drop_index("ix_user_daily_quest_user_date", table_name="user_daily_quest")
    op.drop_table("user_daily_quest")
    op.drop_column("users", "pet_code")
