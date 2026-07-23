"""weather_climatology + weather_outlook (장기 탭 기상 신호, DB.md §3.11/§3.12)

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-22

장기 탭 적합도의 기상 입력이 '평년치 + 장기예보 보정'으로 확정되면서
평년값(weather_climatology)과 3개월 장기예보(weather_outlook) 테이블 추가.
knowledge_chunk(RAG)은 pgvector 확장/이미지 교체가 필요해 별도 착수 시 추가.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE weather_climatology (
            id                      BIGSERIAL PRIMARY KEY,
            region_id               INT NOT NULL REFERENCES region(id),
            month                   INT NOT NULL CHECK (month BETWEEN 1 AND 12),
            temp_avg_normal         NUMERIC,
            temp_night_min_normal   NUMERIC,
            rainfall_normal         NUMERIC,
            sunlight_normal         NUMERIC,
            source                  VARCHAR(50) NOT NULL,
            fetched_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_climatology UNIQUE (region_id, month)
        );

        CREATE TABLE weather_outlook (
            id              BIGSERIAL PRIMARY KEY,
            region_id       INT NOT NULL REFERENCES region(id),
            target_month    DATE NOT NULL,
            indicator       VARCHAR(20) NOT NULL,
            category        VARCHAR(10) NOT NULL CHECK (category IN ('BELOW', 'NORMAL', 'ABOVE')),
            prob_below      NUMERIC,
            prob_normal     NUMERIC,
            prob_above      NUMERIC,
            published_at    TIMESTAMPTZ NOT NULL,
            fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_outlook UNIQUE (region_id, target_month, indicator, published_at)
        );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS weather_outlook;
        DROP TABLE IF EXISTS weather_climatology;
        """
    )
