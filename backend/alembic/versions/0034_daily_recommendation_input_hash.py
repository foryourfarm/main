"""단기 추천 캐시에 입력 지문 컬럼 추가 (2026-08-04).

**왜**: `daily_recommendation`은 `uq_daily(user_farm_id, target_date)`가 키라 **하루에 한 번만**
문구를 만든다. 그런데 기상청 단기예보는 발표 주기가 3시간이라 하루에 여덟 번 갱신되고
(`short_term_service.get_forecast_rows`가 최신 발표분을 받으면 캐시를 갱신한다), 그때마다
위험 판정이 바뀔 수 있다.

그래서 이런 일이 난다:

```
05:00  첫 조회 → "앞으로 3일간 기상 위험 신호가 없습니다."  저장(is_llm=true)
14:00  새 발표분에 폭우 추가 → 날짜 카드에 강수 경고가 뜬다
       그런데 추천 카드는 여전히 "위험 신호가 없습니다"
```

**같은 화면에서 두 블록이 정면으로 모순한다.** 에러 없이 조용히 거짓말하는 부류라 §18-4에
걸리고, "선제적 안내"(PRD 철학 3)가 정작 필요한 순간에 실효된다.

`0033`이 장기 추천에 도입한 것과 같은 해법이다 — 저장된 문구가 아직 유효한지를 **입력 지문**
으로 판정한다. 다만 지문 재료는 `0033` 당시보다 정확해졌다(`app/services/advice_cache.py`):
다듬은 결과를 결정하는 것은 `프롬프트 버전 + 작물명 + 규칙 문구` 셋뿐이므로 그것만 해시한다.
장기 쪽도 같은 함수로 통일했다 — 같은 개념의 해시 레시피가 둘이면 반드시 갈라진다.

**`uq_daily`는 그대로 둔다.** 단기는 날짜가 여전히 의미 있는 키다(그날 무슨 안내가 나갔는지
날짜로 조회한다). 장기처럼 밭당 1행으로 접지 않는다 — 창이 아니라 날짜라 이력이 자연스럽다.

**nullable인 이유**: 기존 행에는 지문이 없다. NULL은 어떤 지문과도 같지 않으므로 다음 조회가
**미스로 보고 한 번 다시 만든다** — 정확히 원하는 동작이라 backfill이 필요 없다.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # sha256 hex는 항상 64자. `0033`의 long_term_recommendation.input_hash와 같은 폭이다.
    op.add_column(
        "daily_recommendation", sa.Column("input_hash", sa.String(length=64), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("daily_recommendation", "input_hash")
