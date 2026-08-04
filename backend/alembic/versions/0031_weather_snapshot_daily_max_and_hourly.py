"""단기 예보 캐시에 일최고기온·시간별기온 컬럼 추가 (2026-08-04).

**왜**: 카드의 "낮 기온"이 실제로 낮 기온이 아니었다. `fold_daily()`가 `fcstTime`을 읽지도
않고 그날 `TMP`(1시간 기온) 전부를 산술평균한 값(`temp_avg`)을 그 자리에 보여주고 있었다.
실측 대조(2026-08-04 14시 발표, 순천 70,70)에서 그 괴리가 얼마나 큰지 확인됐다.

```
2026-08-04  일평균 31.3℃   일최고 38℃    ← 6.7℃ 차이. 사용자는 31.3을 "낮 기온"으로 봤다
2026-08-05  일평균 29.2℃   일최고 36.0℃
```

같은 호출에서 첫날 표본이 **15~23시 9개뿐**임도 확인됐다(발표시각 이후만 온다). 새벽·오전이
통째로 빠진 표본으로 평균을 내니 첫날만 값이 튀어 허용상한을 넘고 경고가 떴다 — 실제 위험이
아니라 부분 표본의 산물이다.

그래서 **표시와 채점을 분리**한다.
  - 표시: `temp_max`(일최고) — 사용자가 체감하는 낮 더위. 카드에 "낮 최고기온"으로 나간다.
  - 채점: `temp_avg`(일평균) — `temp_day` 지표 입력. **밴드·채점 로직은 건드리지 않는다.**

`hourly_temp`는 그 분리를 화면에서 설명하기 위한 것이다. 날짜 카드를 누르면 하루 기온 곡선에
일최고·일최저·일평균을 함께 얹어, 왜 두 숫자가 다른지와 첫날 표본이 어디까지만 있는지를
한 화면에서 보여준다(§18-4 정직한 한계 표기).

**JSONB를 고른 이유**: `uq_weather(region_id, kind, base_at, target_date)`가 하루 1행을
보장하는 구조를 유지하면서 시간별 값을 담아야 한다. 이 데이터는 그래프 렌더 전용이고 쿼리
대상이 아니라 별도 테이블로 정규화할 이득이 없다(행 수만 8~24배가 된다).
같은 스키마의 `suitability_result.breakdown`·`daily_recommendation.risk_flags`가 이미
JSONB라 선례도 있다(0001).

**`weather_snapshot`은 0001 이후 처음 ALTER된다.** 기존 행은 두 컬럼이 NULL로 남으므로
읽는 쪽이 NULL을 방어해야 한다(직전 발표분 캐시가 그 상태다).

`temp_max`는 지금은 표시 전용이지만, 나중에 `temp_max` **채점 지표**를 도입할 때 필요한
컬럼이 바로 이것이다. 현재 고온 임계(사과 31℃ 등)가 `temp_day.allowed_max`에 접혀 들어가
일평균과 비교되는 탓에 사실상 발동하지 않는 문제가 있는데, 그 수정은 밴드 재분류가 선행
조건이라 별도 결정으로 미뤘다(docs/temperature-open-decisions.md).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 다른 기온 컬럼(temp_avg·temp_night_min)과 같은 Numeric — 자릿수 제약은 두지 않는다.
    op.add_column("weather_snapshot", sa.Column("temp_max", sa.Numeric(), nullable=True))
    # [{"h": 15, "t": "29.5"}, …] 시각 오름차순. t를 문자열로 담는다 — JSONB 직렬화가
    # Decimal을 못 다루고, float으로 바꾸면 응답의 다른 기온값(Decimal→문자열)과 표기가 갈린다.
    op.add_column(
        "weather_snapshot", sa.Column("hourly_temp", postgresql.JSONB(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("weather_snapshot", "hourly_temp")
    op.drop_column("weather_snapshot", "temp_max")
