"""상추 토양 유기물 채점 밴드 적재 (2026-08-03).

**왜**: FarmML PR "update crop scoring contract"가 `outcomes/`에서 출처미상 공유
`soil_rules`를 걷어내고 상추 유기물을 작물 전용 밴드로 신설했는데(EC와 같은 처방
5차 p169), 백엔드에는 상추 유기물 지침 행 자체가 없었다 — 상추 교본 264쪽에는 포장
유기물 적정구간이 없어 종전엔 "공유값과 동일해 override 불필요"로 봤던 결손이다.
`test_guide_outcomes_contract.py`의 미반영 지표 게이트가 `float(None)` TypeError에
가려 있던 이 갭을 드러냈다(0028 리뷰 참고).

**컬럼 추가가 없다.** `organic`은 사과(0004)·감자(0019)에 이미 있는 기존 지표라
`crop_growth_guide.indicator='organic'` 행만 상추(crop_id=5)에 추가하면 된다.

    optimal 20~30 g/kg, allowed 15~35 g/kg (처방 5차 p169, ±50% 휴리스틱)

**[확인 필요] 재배형 주의.** 원문 표기는 시설재배토양 기준이고 우리 실측(흙토람)은
노지다 — EC(0028)와 같은 종류의 위험이다. Tyurin법(국내 표준)으로 측정법은 확인됐다.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SOURCE = (
    "RDA 「작물별 비료사용처방」 5차(2022) p169 진단기준표 20~30 g/kg. "
    "outcomes/memory/crop_rules/lettuce.json soil_overrides.organic_matter와 같은 값이어야 "
    "한다(두 구현의 점수가 갈리면 안 되는 계약). 상추 교본에는 포장 유기물 적정구간이 없어 "
    "이 표로 결손을 채웠다. allowed_min/max는 완충구간 문헌이 없어 optimal 폭(10.0) ±50%(5.0) "
    "휴리스틱(§8) [확인 필요]. [확인 필요] 원문은 시설재배토양 기준표이고 우리 실측은 노지다. "
    "측정법은 Tyurin법(국내 표준, national-agri-environment-monitoring-2020.md)으로 확인됨."
)

_OPTIMAL_MIN = 20.0
_OPTIMAL_MAX = 30.0
_ALLOWED_MIN = 15.0
_ALLOWED_MAX = 35.0
_WEIGHT = 1.0
# 0020이 이미 심어 둔 감쇠폭 — organic 지표는 사과·감자에서 이미 쓰이고 있어 값 자체는
# 새로 만들지 않는다(전국 실측 산포도, 작물 공통).
_RISK_WIDTH = 9.2069
_RISK_WIDTH_SOURCE = (
    "risk_width=2.0 x robust_sd(1.4826 x MAD), 전국 실측 산포도. "
    "출처 outcomes/memory/indicator_dispersion.json"
)


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO crop_growth_guide
                (crop_id, growth_stage, indicator, optimal_min, optimal_max,
                 allowed_min, allowed_max, weight, source_ref, confidence,
                 risk_width, risk_width_source)
            VALUES (5, NULL, 'organic', :omin, :omax, :amin, :amax, :w, :src,
                    'domestic_measured', :rw, :rws)
            """
        ),
        {
            "omin": _OPTIMAL_MIN,
            "omax": _OPTIMAL_MAX,
            "amin": _ALLOWED_MIN,
            "amax": _ALLOWED_MAX,
            "w": _WEIGHT,
            "src": _SOURCE,
            "rw": _RISK_WIDTH,
            "rws": _RISK_WIDTH_SOURCE,
        },
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM crop_growth_guide "
            "WHERE crop_id = 5 AND growth_stage IS NULL AND indicator = 'organic'"
        )
    )
