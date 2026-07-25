"""crop_growth_guide 근거·신뢰도 + 강수 단위 분리 (문헌 조사 반영)

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-25

문헌 조사(LoopReport.md, 기온강수량-문헌정리.md) 결과 두 가지 결함이 확인됐다.

1) **강수 단위 혼동** — 문헌이 "mm/시즌 vs mm/일 혼동 → 단위 명시 필수"로 경고한 문제가
   실제로 있었다. `rainfall` 지표 하나에 장기 탭은 월평년(mm/월, 순천 7월 400.4), 단기 탭은
   예보 일누적(mm/일, 0)을 넣고 **같은 기준(감자 33.3~66.7)과 비교**했다. 그 결과 비가 안
   오는 날(0mm)이 "위험"으로 판정됐다. 지표를 단위별로 분리한다.
   - `rainfall_monthly` (mm/월) — 장기 탭, weather_climatology 소스
   - `rainfall_daily`  (mm/일) — 단기 탭, weather_snapshot 소스
   기존 `rainfall` 행은 월 단위 소스로만 쓰였으므로 `rainfall_monthly`로 이관한다.

2) **근거·신뢰도 표기 부재** — 농업 기준값에 출처가 없어 "이 숫자 어디서 왔나"에 답할 수
   없고, 국내 실측값과 해외 문헌 잠정치가 구분되지 않았다. 문헌이 "해외 문헌 기반 값은
   잠정치로 표시하고 신뢰도 낮음 플래그"를 요구했고, CLAUDE.md §18-4(근사를 확정값처럼
   쓰지 않기)와도 직결된다.
   - `source_ref`  근거 출처
   - `confidence`  domestic_measured | foreign_literature | provisional

confidence는 UI 표현 강도를 조절하는 근거가 된다("국내 실측" vs "이론 추정").
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE crop_growth_guide
            ADD COLUMN source_ref VARCHAR(300),
            ADD COLUMN confidence VARCHAR(24);

        ALTER TABLE crop_growth_guide
            ADD CONSTRAINT ck_guide_confidence
            CHECK (confidence IS NULL OR confidence IN
                   ('domestic_measured', 'foreign_literature', 'provisional'));

        -- 기존 rainfall 행은 월평년(weather_climatology)으로만 평가돼 왔다 → 월 단위로 이관.
        UPDATE crop_growth_guide SET indicator = 'rainfall_monthly'
        WHERE indicator = 'rainfall';
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE crop_growth_guide SET indicator = 'rainfall'
        WHERE indicator IN ('rainfall_monthly', 'rainfall_daily');

        ALTER TABLE crop_growth_guide DROP CONSTRAINT IF EXISTS ck_guide_confidence;
        ALTER TABLE crop_growth_guide
            DROP COLUMN IF EXISTS source_ref,
            DROP COLUMN IF EXISTS confidence;
        """
    )
