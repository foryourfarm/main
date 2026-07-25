"""근거 없는 월 강수 적정구간 제거 (감자 rainfall_monthly)

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-25

FE 장기 탭을 붙여 눈으로 확인하다 발견: 감자가 12개월 중 **10개월이 "월 강수량 위험"**으로
뜨고 점수가 0/100/0으로 극단적으로 튀었다(순천 월강수 19.9~400.4mm).

원인 — 기준값 33.3~66.7은 월별 기준이 아니라 **생육기간 총강수 400~800mm를 12로 나눈 값**이다
(400/12=33.3, 800/12=66.7). 시즌 총량을 월 평균으로 환산한 단위 변환 부산물이며, 문헌이
경고한 "mm/시즌 vs mm/일 혼동"의 또 다른 형태다.

한국은 장마 때문에 월강수가 20~400mm로 20배 변동하므로 이 기준으로는 여름엔 항상 초과,
겨울엔 항상 미달이 된다. 즉 어떤 지역·어떤 해도 "적정"일 수 없는 기준으로 위험 경보를
내고 있었다 — 근거 없는 기준값이므로 제거한다(§18-2 기준값은 근거 있는 시드로만,
§18-4 근사를 확정값처럼 쓰지 않기).

강수 위험 판정은 문헌 근거가 확실한 **일 과습 임계(rainfall_daily, 30~50mm)** 로만 한다.
월 강수를 적정구간으로 판정하려면 국내 실측 기반 월별 기준이 필요하다 — 감자 물요구량
논문(문헌정리 27번, 45개 지역·30년)이 후보지만 ETc 상대값이라 절대값(mm) 환산이 안 된다.
[확인 필요]로 남긴다.

제거 후 감자 장기 탭은 기온·토양으로만 판정되어 월별 차이가 실제 의미를 갖는다.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM crop_growth_guide WHERE indicator = 'rainfall_monthly';")


def downgrade() -> None:
    # 되돌리면 근거 없는 기준이 다시 살아난다는 점에 유의(0004 시드 값 복원).
    op.execute(
        """
        INSERT INTO crop_growth_guide
            (crop_id, growth_stage, indicator, optimal_min, optimal_max,
             allowed_min, allowed_max, weight, source_ref, confidence)
        VALUES (4, NULL, 'rainfall_monthly', 33.3, 66.7, NULL, NULL, 1.5,
                '0004 시드(시즌 총강수 400~800mm를 12로 나눈 값 — 근거 불충분)', 'provisional')
        ON CONFLICT (crop_id, growth_stage, indicator) DO NOTHING;
        """
    )
