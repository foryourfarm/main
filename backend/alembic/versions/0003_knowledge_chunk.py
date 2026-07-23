"""knowledge_chunk (챗봇 RAG, pgvector) + crop 마스터 시드 (DB.md §3.15)

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-23

pgvector 확장 필요 → docker-compose.yml 이미지를 pgvector/pgvector:pg16으로 교체.
crop_id FK가 실제 5종 행을 요구하므로 여기서 함께 시드(마스터 데이터는 마이그레이션/시드로 적재, CLAUDE.md §10).
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE EXTENSION IF NOT EXISTS vector;

        INSERT INTO crop (id, name) VALUES
            (1, '사과'),
            (2, '배'),
            (3, '오이'),
            (4, '감자'),
            (5, '상추')
        ON CONFLICT (id) DO NOTHING;

        CREATE TABLE knowledge_chunk (
            id          BIGSERIAL PRIMARY KEY,
            source_ref  VARCHAR(200) NOT NULL,
            crop_id     INT REFERENCES crop(id),
            content     TEXT NOT NULL,
            embedding   vector(1024) NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS knowledge_chunk;
        DELETE FROM crop WHERE id IN (1, 2, 3, 4, 5);
        """
    )
