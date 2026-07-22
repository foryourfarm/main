-- foryourfarm initial schema
-- 설계 근거/컬럼 설명은 DB.md 참고. Spring Boot 스캐폴딩 후에는 이 파일을
-- backend/src/main/resources/db/migration/V1__init_schema.sql 로 그대로 옮겨 Flyway가 관리한다.

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
    id          INT PRIMARY KEY,
    name        VARCHAR(50) NOT NULL,
    sido        VARCHAR(30) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE region_grid (
    region_id   INT PRIMARY KEY REFERENCES region(id),
    nx          INT NOT NULL,
    ny          INT NOT NULL
);

CREATE TABLE crop (
    id              INT PRIMARY KEY,
    name            VARCHAR(30) NOT NULL,
    season_weeks    INT NOT NULL
);

CREATE TABLE crop_growth_guide (
    id              BIGSERIAL PRIMARY KEY,
    crop_id         INT NOT NULL REFERENCES crop(id),
    indicator       VARCHAR(30) NOT NULL, -- temp_day / temp_night_min / ph / ec / rainfall / sunlight / p2o5 / organic ...
    optimal_min     NUMERIC,
    optimal_max     NUMERIC,
    allowed_min     NUMERIC,
    allowed_max     NUMERIC,
    weight          NUMERIC NOT NULL,
    week_from       INT,
    week_to         INT,
    CONSTRAINT uq_guide UNIQUE (crop_id, indicator, week_from, week_to)
);

CREATE TABLE soil_data (
    id              BIGSERIAL PRIMARY KEY,
    region_id       INT NOT NULL REFERENCES region(id),
    soil_texture    VARCHAR(30),
    ph              NUMERIC,
    ec              NUMERIC,
    p2o5            NUMERIC,
    organic_matter  NUMERIC,
    source          VARCHAR(50) NOT NULL,
    collected_at    TIMESTAMPTZ NOT NULL,
    is_imputed      BOOLEAN NOT NULL DEFAULT false,
    CONSTRAINT uq_soil UNIQUE (region_id)
);

CREATE TABLE weather_history (
    id              BIGSERIAL PRIMARY KEY,
    region_id       INT NOT NULL REFERENCES region(id),
    week_no         INT NOT NULL CHECK (week_no BETWEEN 1 AND 53),
    temp_avg        NUMERIC,
    temp_night_min  NUMERIC,
    rainfall        NUMERIC,
    sunlight        NUMERIC,
    is_imputed      BOOLEAN NOT NULL DEFAULT false,
    collected_at    TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_weather UNIQUE (region_id, week_no)
);
CREATE INDEX ix_weather_region_week ON weather_history (region_id, week_no);

CREATE TABLE game_save (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    current_week    INT NOT NULL DEFAULT 1 CHECK (current_week >= 1),
    season          VARCHAR(10) NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'IN_PROGRESS',
    version         INT NOT NULL DEFAULT 0, -- 낙관적 락 (DB.md §7)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_game_save_user ON game_save (user_id);

CREATE TABLE farm_plot (
    id              BIGSERIAL PRIMARY KEY,
    game_save_id    BIGINT NOT NULL REFERENCES game_save(id) ON DELETE CASCADE,
    region_id       INT NOT NULL REFERENCES region(id),
    crop_id         INT NOT NULL REFERENCES crop(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_plot UNIQUE (game_save_id, region_id, crop_id)
);

CREATE TABLE suitability_result (
    id              BIGSERIAL PRIMARY KEY,
    region_id       INT NOT NULL REFERENCES region(id),
    crop_id         INT NOT NULL REFERENCES crop(id),
    week_no         INT NOT NULL,
    score           NUMERIC NOT NULL CHECK (score BETWEEN 0 AND 100),
    grade           CHAR(1) NOT NULL CHECK (grade IN ('S','A','B','C')),
    breakdown       JSONB,
    risk_flags      JSONB,
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_suit UNIQUE (region_id, crop_id, week_no)
);

CREATE TABLE cultivation_log (
    id              BIGSERIAL PRIMARY KEY,
    game_save_id    BIGINT NOT NULL REFERENCES game_save(id) ON DELETE CASCADE,
    region_id       INT NOT NULL REFERENCES region(id),
    crop_id         INT NOT NULL REFERENCES crop(id),
    week_no         INT NOT NULL,
    grade           CHAR(1) NOT NULL,
    risk_summary    JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_log_save ON cultivation_log (game_save_id, week_no);

-- updated_at 자동 갱신 (DB.md §5 Trigger)
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_game_save_updated_at BEFORE UPDATE ON game_save
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Lobby 등급 표시용 (DB.md §5 View)
CREATE VIEW v_plot_current_suitability AS
SELECT fp.id AS farm_plot_id, fp.game_save_id, fp.region_id, fp.crop_id,
       gs.current_week, sr.score, sr.grade, sr.risk_flags
FROM farm_plot fp
JOIN game_save gs ON gs.id = fp.game_save_id
LEFT JOIN suitability_result sr
       ON sr.region_id = fp.region_id
      AND sr.crop_id = fp.crop_id
      AND sr.week_no = gs.current_week;
