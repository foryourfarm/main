"""치환성 양이온(K·Ca·Mg) 채점 배선 — 캐시·상태 컬럼 + 상추 지침 (2026-07-29).

**왜**: 0020이 `RISK_WIDTH`에 `k`/`ca`/`mg`를 넣었지만 `crop_growth_guide`에 해당 indicator
행이 아예 없어 UPDATE 3건이 no-op이었다(`docs/guide-seed-known-issues.md` P3).
0019가 상추 K/Ca/Mg 문헌값을 반영하지 않은 이유도 같다 — 값을 받아올 자리가 없었다:
`soil_state`·`district_soil`에 컬럼이 없고 `INDICATOR_SOURCE_FIELDS`에도 안 걸려 있었다.

흙토람 토양검정 클라이언트(`soil_exam_client.py`)는 이미 `POSIFERT_K/CA/MG`를 파싱해
버리고 있었다. 그래서 이 마이그레이션은 **배선만** 한다 — 캐시·상태 컬럼 추가 + 지침 행 적재.

**단위 확인(추측 아님)**: `docs/api-specs/OPENAPI_chemistry_V2.pdf` 응답 명세가
`POSIFERT_K/CA/MG`를 **cmol+/kg**로 명시한다(예: K 0.174, Ca 3.500, Mg 1.100).
상추 기준(RDA 2022 진단기준표)도 cmol/kg이라 단위가 일치한다 — 환산 없이 그대로 쓴다.

**지침 값**: `outcomes/memory/crop_rules/lettuce.json`의 `soil_overrides`
(농촌진흥청 RDA 2022 노지 상추 토양 진단기준표).

| indicator | optimal | allowed | risk_width |
|---|---|---|---|
| k | 0.40~0.60 | 0.30~0.70 | 0.5041 |
| ca | 6.0~7.0 | 5.5~7.5 | 3.7777 |
| mg | 2.0~2.5 | 1.75~2.75 | 1.2632 |

allowed는 문헌값이 아니라 optimal 폭 ±50% 휴리스틱(0019·0021·0022와 동일) — 행마다 명시한다.
`risk_width`는 0020이 산출한 전국 실측 산포도(`outcomes/memory/indicator_dispersion.json`)를
그대로 쓴다. 0020은 이미 적용된 마이그레이션이라 값이 소급되지 않으므로 여기서 함께 넣는다.
weight는 0019가 상추 유효인산에 준 1.0에 맞춘다(pH 1.5보다 낮은 부지표).

**상추만 넣는 이유**: RDA 진단기준표를 확인한 작물이 상추뿐이다. 다른 4작물의 양이온
기준은 문헌이 없어 넣지 않는다 — 추측 금지(§3-4). 값이 확보되면 같은 형식으로 추가.

**기존 밭 영향**: `soil_state.k/ca/mg`는 NULL로 시작한다(캐시에도 값이 없다). 상추 밭은 이
세 지표가 `missing`으로 잡혀 `weight_sum`에서 빠지고 나머지 지표로 정상 채점된다 —
0점으로 깎이지 않는다. 밭 재등록·캐시 갱신 시점부터 값이 채워진다. [확인 필요] 기존
`district_soil` 캐시 행을 재조회로 채우는 백필은 이 PR 범위 밖이다(호출 쿼터 §18-1).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LETTUCE_CROP_ID = 5
CATION_TABLES = ("district_soil", "soil_state")
CATION_COLUMNS = ("k", "ca", "mg")

RDA_SOURCE = (
    "농촌진흥청(RDA 2022) 노지 상추 토양 진단기준표 — 치환성 {name}(cmol+/kg). "
    "outcomes/memory/crop_rules/lettuce.json. 허용경계는 문헌값이 아니라 추정: "
    "optimal 경계 ±(optimal 폭 x 50%), 0019와 동일한 휴리스틱. [확인 필요] 결핍/과다 "
    "붕괴점 문헌 확보 시 교체."
)
# 0020과 같은 문구 — 같은 산출물에서 온 값임을 추적할 수 있게 한다.
RISK_WIDTH_SOURCE = (
    "risk_width=2.0 x robust_sd(1.4826 x MAD), 전국 실측 산포도. "
    "출처 outcomes/memory/indicator_dispersion.json (2026-07-29)"
)

# (indicator, 국문명, optimal_min, optimal_max, allowed_min, allowed_max, risk_width)
LETTUCE_CATIONS: tuple[tuple[str, str, float, float, float, float, float], ...] = (
    ("k", "칼륨", 0.40, 0.60, 0.30, 0.70, 0.5041),
    ("ca", "칼슘", 6.0, 7.0, 5.5, 7.5, 3.7777),
    ("mg", "마그네슘", 2.0, 2.5, 1.75, 2.75, 1.2632),
)
CATION_WEIGHT = 1.0


def upgrade() -> None:
    for table in CATION_TABLES:
        for column in CATION_COLUMNS:
            op.add_column(table, sa.Column(column, sa.Numeric(), nullable=True))

    bind = op.get_bind()
    for indicator, name, opt_min, opt_max, allowed_min, allowed_max, risk_width in LETTUCE_CATIONS:
        bind.execute(
            sa.text(
                "INSERT INTO crop_growth_guide "
                "(crop_id, growth_stage, indicator, optimal_min, optimal_max, "
                " allowed_min, allowed_max, weight, source_ref, confidence, "
                " risk_width, risk_width_source) "
                "VALUES (:crop, NULL, :indicator, :opt_min, :opt_max, :allowed_min, :allowed_max, "
                " :weight, :source, 'domestic_measured', :risk_width, :risk_source)"
            ),
            {
                "crop": LETTUCE_CROP_ID,
                "indicator": indicator,
                "opt_min": opt_min,
                "opt_max": opt_max,
                "allowed_min": allowed_min,
                "allowed_max": allowed_max,
                "weight": CATION_WEIGHT,
                "source": RDA_SOURCE.format(name=name),
                "risk_width": risk_width,
                "risk_source": RISK_WIDTH_SOURCE,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM crop_growth_guide "
            "WHERE crop_id = :crop AND growth_stage IS NULL AND indicator IN ('k', 'ca', 'mg')"
        ),
        {"crop": LETTUCE_CROP_ID},
    )
    for table in CATION_TABLES:
        for column in CATION_COLUMNS:
            op.drop_column(table, column)
