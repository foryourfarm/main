"""weather_climatology에 일사량 월평년 컬럼 추가

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-26

왜 필요한가: 일조시간 평년값(`sunlight_normal`)이 전 지역 NULL이다 — ETL 소스
(data/03_weather_monthly_modified.csv)에 일조 컬럼이 없다(scripts/load_weather_climatology.py
docstring). 그 결과 장기 탭의 일조 지표가 어느 지역에서도 채점되지 않았다.

농업기상 V3(`srqty`)가 일사량을 주고, 일사량 → 일조시간 환산은 실측 7,244행 홀드아웃에서
R²=0.904 / MAE 0.845h로 검증됐다(docs/seed/sunlight_calibration.json). 그래서 일사량을
평년값으로 적재해 두고 읽을 때 환산한다.

왜 일조시간을 미리 환산해 저장하지 않는가: 보정계수가 재보정되면 저장값이 낡는다.
원자료(일사량)를 저장하고 환산은 read-time에 한다 — 계수 변경이 즉시 반영된다.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE weather_climatology
            ADD COLUMN solar_radiation_normal NUMERIC;

        COMMENT ON COLUMN weather_climatology.solar_radiation_normal IS
            '일사량 월평년 (MJ/m2/day). 농업기상 V3 srqty. 일조시간 환산용 원자료.';
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE weather_climatology DROP COLUMN IF EXISTS solar_radiation_normal;")
