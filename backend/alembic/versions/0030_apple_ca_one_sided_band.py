"""사과 치환성 Ca를 단측 밴드(상한 없음)로 정정한다 (2026-08-03).

**왜**: `outcomes/`가 apple.json ca의 `optimal_max`·`allowed_max`를 null로 바꿨다(0024가
6.0/6.5로 적재했던 값). 원인은 데이터가 아니라 표기 확인이었다 — RDA 사과 교본 표5-21(2018)
치환성 Ca가 "5~6cmol/kg **이상**"이라 상한 붕괴점을 주지 않는다. 2018 교본은 pdftotext
컬럼 정렬이 깨져 있어 "이상"이 추출 아티팩트일 가능성을 의심했지만, 2025 개정 교본 표5-20이
정상 추출된 형태로 같은 값을 재확인해 아티팩트가 아님이 확인됐다(원문 대조, 2026-08-03).

**배는 그대로 둔다.** 배 교본 표5-25는 같은 항목을 "5~6"(양측)으로 적는다 — 같은 지표라도
교본별 표기가 다를 수 있다는 것이지 계산 오류가 아니다(`regional_score_manifest.json`
`crop_band_precision_note`). `0024`가 심어 둔 배 ca(5.0~6.0 / 4.5~6.5)는 바뀌지 않는다.

**룰 엔진도 같이 고쳐야 계약이 성립한다.** `suitability_service._indicator_score`와
`calculate_suitability`가 optimal_max=None을 "지침 없음"으로 오인해 그 지표를 통째로
스킵시키고 있었다 — 이 마이그레이션과 같은 커밋에서 단측 밴드를 정식 처리하도록 고쳤다
(`outcomes/scripts/ml/scoring.py` `band_score()`와 같은 곡선, `outcomes/README.md`
체크리스트 2번).

**[확인 필요] 남기는 것.** 사과가 정말 상한이 없는 작물 생리인지, RDA가 두 교본을
따로 써서 생긴 표기 흔들림인지는 미확정이다. K도 같은 방식으로 사과 0.6~0.9 vs 배
0.3~0.6(두 배 차이)이 미해소 상태다.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_MAX = 6.0
_OLD_ALLOWED_MAX = 6.5

_NEW_SOURCE = (
    "RDA 교본 개량목표 표5-21(원문 대조 검증됨, "
    "knowledge-base/papers/apple/rda-apple-handbook-2018.md). 치환성 칼슘(석회). "
    "양이온 목표비 Ca 65%:Mg 15%:K 5%. 단측 밴드(2026-08-03 정정): 원문 표기가 "
    "'5~6cmol/kg 이상'이라 상한 붕괴점을 주지 않는다 — 2018 교본 표5-21은 pdftotext 컬럼 "
    "정렬이 깨져 있었으나, 2025 개정 교본 표5-20이 정상 추출된 형태로 동일 값을 재확인해 "
    "아티팩트가 아님을 확인했다(원문 대조, 2026-08-03). 배 교본 표5-25는 같은 항목을 "
    "'5~6'(양측)으로 적어 상한이 있다. [확인 필요] 사과가 정말 상한이 없는 작물 생리인지, "
    "RDA가 두 교본을 따로 써서 생긴 표기 흔들림인지는 미확정."
)
_OLD_SOURCE = (
    "RDA 교본 개량목표 표5-21(원문 대조 검증됨, "
    "knowledge-base/papers/apple/rda-apple-handbook-2018.md). allowed_min/max는 완충구간 "
    "문헌이 없어 optimal 폭 ±50% 휴리스틱(CLAUDE.md §8) [확인 필요]. 치환성 칼슘(석회). "
    "양이온 목표비 Ca 65%:Mg 15%:K 5%. [확인 필요] 전국 토양 실측 중앙값 7.23 cmol/kg로 "
    "목표 상한 초과."
)

_WHERE = "crop_id = 1 AND growth_stage IS NULL AND indicator = 'ca'"


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            f"UPDATE crop_growth_guide "
            f"SET optimal_max = NULL, allowed_max = NULL, source_ref = :src WHERE {_WHERE}"
        ),
        {"src": _NEW_SOURCE},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            f"UPDATE crop_growth_guide "
            f"SET optimal_max = :omax, allowed_max = :amax, source_ref = :src WHERE {_WHERE}"
        ),
        {"omax": _OLD_MAX, "amax": _OLD_ALLOWED_MAX, "src": _OLD_SOURCE},
    )
