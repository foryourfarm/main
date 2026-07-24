"""5종 crop_growth_guide 마스터 시드 (crop-domain-knowledge.md §4).

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-24
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO crop_growth_guide
            (crop_id, growth_stage, indicator, optimal_min, optimal_max,
             allowed_min, allowed_max, weight)
        VALUES
            (1, 'fruit_growth', 'temp_day',       18,   24, NULL, 30, 2.0),
            (1, 'maturity',     'temp_day',       20,   25, NULL, NULL, 1.5),
            (1, 'coloring',     'temp_day',       12,   13, NULL, NULL, 1.0),
            (1, 'coloring',     'temp_night_min',  8,    8, NULL, NULL, 1.0),
            (1, NULL,           'organic',        20,   30, NULL, NULL, 1.0),
            (1, NULL,           'p2o5',          300,  550, NULL, NULL, 1.0),
            (2, 'growing',      'temp_day',     18.5, 21.5,   17,   23, 2.0),
            (3, NULL,           'temp_day',       20,   22,   15,   30, 2.0),
            (4, 'early',        'temp_day',       14,   23,    5,   27, 1.5),
            (4, 'tuber',        'temp_day',       23,   24, NULL,   27, 2.5),
            (4, 'tuber',        'temp_night_min', 10,   14, NULL, NULL, 2.0),
            (4, NULL,           'rainfall',     33.3, 66.7, NULL, NULL, 1.5),
            (5, NULL,           'temp_day',       15,   20,    4,   30, 2.0);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM crop_growth_guide
        WHERE
            (crop_id = 1 AND growth_stage IN ('fruit_growth', 'maturity', 'coloring'))
            OR (crop_id = 1 AND growth_stage IS NULL AND indicator IN ('organic', 'p2o5'))
            OR (crop_id = 2 AND growth_stage = 'growing')
            OR (crop_id = 3 AND growth_stage IS NULL AND indicator = 'temp_day')
            OR (crop_id = 4 AND growth_stage IN ('early', 'tuber'))
            OR (crop_id = 4 AND growth_stage IS NULL AND indicator = 'rainfall')
            OR (crop_id = 5 AND growth_stage IS NULL AND indicator = 'temp_day');
        """
    )
