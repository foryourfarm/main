"""init schema (실시간 서비스 방향, DB.md 기준)

Revision ID: 0001
Revises:
Create Date: 2026-07-22

게임형 스키마는 폐기하고 새 방향(장/단기 예측 웹서비스)으로 baseline 재작성.
설계 근거·컬럼 설명은 DB.md 참고.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE users (
            id              BIGSERIAL PRIMARY KEY,
            email           VARCHAR(255) NOT NULL,
            password_hash   VARCHAR(255) NOT NULL,
            nickname        VARCHAR(50) NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ux_users_email UNIQUE (email)
        );

        CREATE TABLE region (
            id      INT PRIMARY KEY,
            name    VARCHAR(50) NOT NULL,
            sido    VARCHAR(30) NOT NULL
        );
        CREATE INDEX ix_region_name ON region (name);

        CREATE TABLE region_grid (
            region_id   INT PRIMARY KEY REFERENCES region(id),
            nx          INT NOT NULL,
            ny          INT NOT NULL
        );

        CREATE TABLE crop (
            id      INT PRIMARY KEY,
            name    VARCHAR(30) NOT NULL
        );

        CREATE TABLE crop_growth_guide (
            id              BIGSERIAL PRIMARY KEY,
            crop_id         INT NOT NULL REFERENCES crop(id),
            growth_stage    VARCHAR(20),
            indicator       VARCHAR(30) NOT NULL,
            optimal_min     NUMERIC,
            optimal_max     NUMERIC,
            allowed_min     NUMERIC,
            allowed_max     NUMERIC,
            weight          NUMERIC NOT NULL,
            CONSTRAINT uq_guide UNIQUE (crop_id, growth_stage, indicator)
        );

        CREATE TABLE soil_change_rule (
            id              INT PRIMARY KEY,
            action_type     VARCHAR(30) NOT NULL,
            indicator       VARCHAR(30) NOT NULL,
            effect_coeff    NUMERIC NOT NULL,
            decay_days      INT,
            source_ref      VARCHAR(200) NOT NULL,
            CONSTRAINT uq_soil_rule UNIQUE (action_type, indicator)
        );

        CREATE TABLE user_farm (
            id              BIGSERIAL PRIMARY KEY,
            user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            region_id       INT NOT NULL REFERENCES region(id),
            crop_id         INT NOT NULL REFERENCES crop(id),
            planting_date   DATE NOT NULL,
            label           VARCHAR(50),
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_user_farm_user ON user_farm (user_id);

        CREATE TABLE farm_action_log (
            id              BIGSERIAL PRIMARY KEY,
            user_farm_id    BIGINT NOT NULL REFERENCES user_farm(id) ON DELETE CASCADE,
            action_type     VARCHAR(30) NOT NULL,
            amount          NUMERIC,
            acted_on        DATE NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_action_farm ON farm_action_log (user_farm_id, acted_on);

        CREATE TABLE soil_state (
            id              BIGSERIAL PRIMARY KEY,
            user_farm_id    BIGINT NOT NULL REFERENCES user_farm(id) ON DELETE CASCADE,
            soil_texture    VARCHAR(30),
            ph              NUMERIC,
            ec              NUMERIC,
            p2o5            NUMERIC,
            organic_matter  NUMERIC,
            base_source     VARCHAR(50) NOT NULL,
            is_estimated    BOOLEAN NOT NULL DEFAULT true,
            computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_soil_state UNIQUE (user_farm_id)
        );

        CREATE TABLE weather_snapshot (
            id              BIGSERIAL PRIMARY KEY,
            region_id       INT NOT NULL REFERENCES region(id),
            kind            VARCHAR(10) NOT NULL CHECK (kind IN ('OBS', 'FORECAST')),
            base_at         TIMESTAMPTZ NOT NULL,
            target_date     DATE NOT NULL,
            temp_avg        NUMERIC,
            temp_night_min  NUMERIC,
            rainfall        NUMERIC,
            sunlight        NUMERIC,
            is_imputed      BOOLEAN NOT NULL DEFAULT false,
            fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_weather UNIQUE (region_id, kind, base_at, target_date)
        );
        CREATE INDEX ix_weather_region_target ON weather_snapshot (region_id, target_date);

        CREATE TABLE suitability_result (
            id              BIGSERIAL PRIMARY KEY,
            region_id       INT NOT NULL REFERENCES region(id),
            crop_id         INT NOT NULL REFERENCES crop(id),
            growth_stage    VARCHAR(20) NOT NULL,
            score           NUMERIC NOT NULL CHECK (score BETWEEN 0 AND 100),
            grade           CHAR(1) NOT NULL CHECK (grade IN ('S', 'A', 'B', 'C')),
            breakdown       JSONB,
            risk_flags      JSONB,
            computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_suit UNIQUE (region_id, crop_id, growth_stage)
        );

        CREATE TABLE daily_recommendation (
            id              BIGSERIAL PRIMARY KEY,
            user_farm_id    BIGINT NOT NULL REFERENCES user_farm(id) ON DELETE CASCADE,
            target_date     DATE NOT NULL,
            risk_flags      JSONB,
            advice_text     TEXT,
            is_llm          BOOLEAN NOT NULL DEFAULT true,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_daily UNIQUE (user_farm_id, target_date)
        );
        CREATE INDEX ix_daily_farm ON daily_recommendation (user_farm_id, target_date);

        -- updated_at 자동 갱신 (DB.md §5)
        CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();

        -- 대시보드 카드용 (DB.md §5)
        CREATE VIEW v_farm_today AS
        SELECT uf.id AS user_farm_id, uf.user_id, uf.region_id, uf.crop_id, uf.planting_date,
               ss.ph, ss.ec, ss.is_estimated,
               dr.target_date, dr.risk_flags, dr.advice_text
        FROM user_farm uf
        LEFT JOIN soil_state ss ON ss.user_farm_id = uf.id
        LEFT JOIN daily_recommendation dr
               ON dr.user_farm_id = uf.id
              AND dr.target_date = CURRENT_DATE;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP VIEW IF EXISTS v_farm_today;
        DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
        DROP FUNCTION IF EXISTS set_updated_at();
        DROP TABLE IF EXISTS daily_recommendation;
        DROP TABLE IF EXISTS suitability_result;
        DROP TABLE IF EXISTS weather_snapshot;
        DROP TABLE IF EXISTS soil_state;
        DROP TABLE IF EXISTS farm_action_log;
        DROP TABLE IF EXISTS user_farm;
        DROP TABLE IF EXISTS soil_change_rule;
        DROP TABLE IF EXISTS crop_growth_guide;
        DROP TABLE IF EXISTS crop;
        DROP TABLE IF EXISTS region_grid;
        DROP TABLE IF EXISTS region;
        DROP TABLE IF EXISTS users;
        """
    )
