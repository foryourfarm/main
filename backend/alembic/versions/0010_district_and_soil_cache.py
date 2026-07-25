"""읍면동 마스터 + 읍면동 토양 캐시 + 작물별 경지구분 (PRD.md §5, DB.md §3.9)

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-25

밭 등록 시 토양 기준값을 읍면동 단위로 확보하기 위한 스키마(근거·실측은 PR #31 / PRD §5).

- `district`: 읍면동 마스터. 온보딩 드롭다운 소스이자 흙토람 조회 키(법정동 10자리).
  행이 5,066개라 마이그레이션에 INSERT를 박지 않고 `scripts/load_districts.py`가
  docs/seed/bjd_to_region.csv(리포에 있음)에서 적재한다 — 마이그레이션 파일이 수백 KB로
  비대해지는 것을 피하고, 기상 평년치 ETL과 같은 패턴을 따른다.
- `district_soil`: 읍면동×경지구분 토양 기준값 캐시. 같은 동네에 여러 밭이 등록돼도
  외부 API를 다시 부르지 않는다(§12 호출량 방어).
- `crop.exam_field_type`: 작물 → 흙토람 경지구분 코드. 같은 읍면동에서도 경지구분에 따라
  값이 크게 달라(실측: 밭 유기물 20 vs 과수 51~62) 작물에 맞는 표본만 평균해야 한다.
  농업 기준값이라 코드 하드코딩 금지 → 마스터 컬럼으로 관리(CLAUDE.md §18-2).
  코드표(기술명세서 3.1): 1=논 2=밭 3=시설 4=과수 5=간척지(논) 6=간척지(밭) 7=임야 8=기타
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE district (
            bjd_code   CHAR(10) PRIMARY KEY,
            region_id  INTEGER NOT NULL REFERENCES region(id),
            name       VARCHAR(40) NOT NULL
        );
        CREATE INDEX ix_district_region ON district (region_id, name);

        CREATE TABLE district_soil (
            id             BIGSERIAL PRIMARY KEY,
            bjd_code       CHAR(10) NOT NULL REFERENCES district(bjd_code),
            field_type     VARCHAR(1) NOT NULL,
            ph             NUMERIC,
            ec             NUMERIC,
            p2o5           NUMERIC,
            organic_matter NUMERIC,
            sample_count   INTEGER NOT NULL,
            source         VARCHAR(60) NOT NULL,
            fetched_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_district_soil UNIQUE (bjd_code, field_type)
        );

        ALTER TABLE crop ADD COLUMN exam_field_type VARCHAR(1);

        -- 사과·배=과수(4), 오이=시설(3), 감자·상추=밭(2). 농사로 재배 형태 기준.
        UPDATE crop SET exam_field_type = '4' WHERE id IN (1, 2);
        UPDATE crop SET exam_field_type = '3' WHERE id = 3;
        UPDATE crop SET exam_field_type = '2' WHERE id IN (4, 5);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS district_soil;
        DROP TABLE IF EXISTS district;
        ALTER TABLE crop DROP COLUMN IF EXISTS exam_field_type;
        """
    )
