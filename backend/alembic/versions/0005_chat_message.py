"""chat_message (상담 챗봇 대화 로그, 런타임 기록) (DB.md §3.16)

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-24

로그인 유저의 멀티턴 히스토리를 (user_id, session_id)로 스코프해 저장/로드한다(소유권 CLAUDE.md §11).
계정 삭제 시 대화도 삭제(FK ON DELETE CASCADE, §17). 게스트는 저장하지 않음.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE chat_message (
            id          BIGSERIAL PRIMARY KEY,
            user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            session_id  VARCHAR(64) NOT NULL,
            role        VARCHAR(16) NOT NULL,
            content     TEXT NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_chat_message_user_session ON chat_message (user_id, session_id, id);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS chat_message;")
