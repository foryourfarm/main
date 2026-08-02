"""감자 유기물(organic) 전기간 공통 지침 backfill (2026-08-02)

Revision ID: 0027
Revises: 0026
Create Date: 2026-08-02

**왜**: `0019`가 감자(crop_id=4)에 전기간 공통(growth_stage IS NULL) `organic` 지침을
추가했어야 하는데, 실배포 검증(2026-08-02, PR #74 배포 후 감자 밭 실사용 확인) 중
프로덕션 DB에 그 행이 없는 것을 발견했다.

```
id | growth_stage | indicator      | optimal_min | optimal_max
19 |              | rainfall_daily |           0 |          30
 9 | early        | temp_day       |          14 |          23
10 | tuber        | temp_day       |          23 |          24
11 | tuber        | temp_night_min |          10 |          14
```

`organic` 행이 없어서 파종 전(1~5월, 이 검증에 쓴 밭은 6/17 파종) 달은 생육단계가 없고
(`stage=None`) 전기간 공통 지침도 없어 `has_guides=False` → 상태가 `dormant`(생육기 아님,
토양만 채점)가 아니라 `out_of_season`(제철 아님, 아무 근거 없음)으로 잘못 나왔다.

**격리된 문제로 보인다** — 같은 배포에서 사과·배·상추의 전기간 공통 지침(유기물·유효인산·
K·Ca·Mg)은 정상 작동을 직접 확인했다(단기 탭 위험 플래그·장기 탭 히트맵). `0019` 실행
당시 이 한 INSERT만 어떤 이유로 빠졌거나 실패한 것으로 추정되나 원인은 특정하지 못했다
— 재현 불가능한 과거 배포 사고라 backfill로 처리하고 근본 원인 규명은 미룬다.

**`0019`를 고치지 않고 새 마이그레이션으로 하는 이유**: `0019`는 이미 프로덕션에
`alembic_version`으로 적용 완료 처리돼 있다(`0026`까지 head가 진행됐다는 것 자체가
증거) — 즉 다른 환경에서는 이미 성공 적용된 이력이다. `0023`(이번 세션에서 직접 고침)과
달리 이건 "적용된 적 없는 마이그레이션"이 아니라 "적용됐는데 결과가 새는" 경우라
재실행 대상이 아니라 backfill 대상이다.

값·근거 텍스트는 `0019`의 `POTATO_ORGANIC_SOURCE`와 완전히 동일하게 옮긴다 — 이 시드가
이미 있었어야 할 값이지 새로 정하는 값이 아니다. `WHERE NOT EXISTS`로 멱등 처리한다
— 이미 있는 환경(로컬 등)에서 다시 돌려도 중복 삽입되지 않는다.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 0019.POTATO_ORGANIC_SOURCE와 동일 — 새 근거가 아니라 그때 빠진 값을 그대로 옮긴다.
_SOURCE = (
    "정진철 외 2003(한국환경농학회지 22권 4호, 261-265쪽), 전국 7개 지역 2개년 실측 — 토양 "
    "유기물이 건물율·칩색도와 강한 상관, 실측범위 10~47g/kg. [확인 필요] 원 논문은 '높을수록 "
    "좋다'는 단조 상관만 제시하고 명시적 적정구간을 안 줘 — optimal_min=30은 관측범위 상위절반을 "
    "'양호' 구간으로 잡은 편집 판단. allowed_max=55.5는 optimal 폭 절반 폭만큼의 휴리스틱."
)


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            """
            INSERT INTO crop_growth_guide
                (crop_id, growth_stage, indicator, optimal_min, optimal_max,
                 allowed_min, allowed_max, weight, source_ref, confidence)
            SELECT 4, NULL, 'organic', 30, 47, 10, 55.5, 1.0, :src, 'domestic_measured'
            WHERE NOT EXISTS (
                SELECT 1 FROM crop_growth_guide
                WHERE crop_id = 4 AND growth_stage IS NULL AND indicator = 'organic'
            )
            """
        ),
        {"src": _SOURCE},
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "DELETE FROM crop_growth_guide "
            "WHERE crop_id = 4 AND growth_stage IS NULL AND indicator = 'organic'"
        )
    )
