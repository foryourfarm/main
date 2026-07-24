"""crop_growth_stage (생육단계 → 날짜 매핑 마스터·시드)

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-24

planting_date/달력에서 생육단계를 파생하기 위한 매핑. 농업 기준값이라 시드로만 적재(§18-2).
근거: 농촌진흥청 농사로 농작업일정(공공누리 제2유형).

DOY(연중일자) 경계는 비윤년 기준(윤년은 2월 이후 ±1일 오차 — 단계 경계엔 무해).
상=1~10, 중=11~20, 하=21~말일. 사과 coloring/maturity는 문헌이 "성숙·착색"을 한 구간으로만
주어 착색기(잎따기)와 만생종 수확기로 근사 분리한 것(품종 정보 부재 → 이론 추정, UI 병기 필요).
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE crop_growth_stage (
            id           SERIAL PRIMARY KEY,
            crop_id      INTEGER NOT NULL REFERENCES crop(id),
            growth_stage VARCHAR(32) NOT NULL,
            mode         VARCHAR(24) NOT NULL,
            range_start  INTEGER NOT NULL,
            range_end    INTEGER NOT NULL,
            priority     INTEGER NOT NULL,
            CONSTRAINT uq_crop_growth_stage UNIQUE (crop_id, growth_stage),
            CONSTRAINT ck_crop_growth_stage_mode
                CHECK (mode IN ('day_of_year', 'days_after_planting'))
        );

        -- 사과(1)·배(2): 다년생 → 연중일자(day_of_year). 감자(4): 1년생 → 파종후경과일.
        -- 오이·상추: 하위 단계 문헌 없음 → 행 없음(resolver가 None=전기간 지침 반환).
        INSERT INTO crop_growth_stage
            (crop_id, growth_stage, mode, range_start, range_end, priority)
        VALUES
            -- 사과: 생장비대 4월하~9월중 / 착색 8월하~10월중 / 성숙 10월하~11월상
            (1, 'fruit_growth', 'day_of_year',         111, 263, 1),
            (1, 'coloring',     'day_of_year',         233, 293, 2),
            (1, 'maturity',     'day_of_year',         294, 314, 3),
            -- 배: 세포분열기~과실비대기 5월상~10월중
            (2, 'growing',      'day_of_year',         121, 293, 1),
            -- 감자: 출현기까지 초기 0~45일 / 형성·비대 46~120일(전체 생육 90~100일 + 버퍼)
            (4, 'early',        'days_after_planting',   0,  45, 1),
            (4, 'tuber',        'days_after_planting',  46, 120, 2);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS crop_growth_stage;")
