"""soil_state_snapshot (실측 이력 append-only) + prediction_shadow (토양변화 shadow 로그)

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-24

토양변화 shadow 추론(P0)의 저장소. 실측 시각을 보존하는 snapshot으로 안전한 feature_as_of를
잡고, 목표별 예측을 prediction_shadow에 is_exposed=false로 기록한다(핸드오프 §4.2, 가이드 §2).
둘 다 밭 하위 리소스이므로 계정/밭 삭제 시 함께 삭제(FK ON DELETE CASCADE, CLAUDE.md §11/§17).
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE soil_state_snapshot (
            id              BIGSERIAL PRIMARY KEY,
            user_farm_id    BIGINT NOT NULL REFERENCES user_farm(id) ON DELETE CASCADE,
            measured_at     TIMESTAMPTZ NOT NULL,
            ph              NUMERIC,
            organic_matter  NUMERIC,
            available_p     NUMERIC,
            source          VARCHAR(64) NOT NULL,
            is_measured     BOOLEAN NOT NULL DEFAULT true,
            is_imputed      BOOLEAN NOT NULL DEFAULT false,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_soil_state_snapshot_farm_measured
            ON soil_state_snapshot (user_farm_id, measured_at);

        CREATE TABLE prediction_shadow (
            id              BIGSERIAL PRIMARY KEY,
            user_farm_id    BIGINT NOT NULL REFERENCES user_farm(id) ON DELETE CASCADE,
            target          VARCHAR(32) NOT NULL,
            point           NUMERIC,
            lo              NUMERIC,
            hi              NUMERIC,
            model_version   VARCHAR(128) NOT NULL,
            data_version    VARCHAR(64) NOT NULL,
            feature_as_of   DATE NOT NULL,
            target_date     DATE NOT NULL,
            prediction_type VARCHAR(32) NOT NULL,
            fallback_used   BOOLEAN NOT NULL DEFAULT false,
            is_exposed      BOOLEAN NOT NULL DEFAULT false,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_prediction_shadow_farm_target
            ON prediction_shadow (user_farm_id, target, created_at);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS prediction_shadow;
        DROP TABLE IF EXISTS soil_state_snapshot;
        """
    )
