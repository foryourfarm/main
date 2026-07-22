-- 나무형/밭작물형 구분 + 행동카드 카탈로그 (DB.md §3.6, §3.3, §3.12)
-- 경제 시스템(cash_balance, economy_log)은 MVP 범위 아님 — v2 이후 별도 마이그레이션에서 추가(DB.md §3.12 하단 계획 참고).
-- Flyway 컨벤션: 이미 적용된 V1은 수정하지 않고 새 버전으로 추가한다.

ALTER TABLE crop
    ADD COLUMN crop_type VARCHAR(10) NOT NULL DEFAULT 'FIELD' CHECK (crop_type IN ('TREE', 'FIELD'));
ALTER TABLE crop
    ALTER COLUMN crop_type DROP DEFAULT;
ALTER TABLE crop
    ALTER COLUMN season_weeks DROP NOT NULL; -- TREE는 성장추적 자체가 없어 NULL

ALTER TABLE farm_plot
    ADD COLUMN planted_at_week INT NOT NULL DEFAULT 1;

CREATE TABLE action_card (
    id                     INT PRIMARY KEY,
    code                   VARCHAR(30) NOT NULL,
    label                  VARCHAR(50) NOT NULL,
    applicable_crop_type   VARCHAR(10) CHECK (applicable_crop_type IN ('TREE', 'FIELD')),
    trigger_week_min       INT,
    trigger_week_max       INT,
    description            TEXT,
    CONSTRAINT uq_action_card_code UNIQUE (code)
);
