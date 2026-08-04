"""장기 탭 추천 문구 캐시 테이블 (2026-08-04).

**왜**: 장기 탭에 "그래서 지금 뭘 준비해야 하나"를 말해주는 문장이 없었다. 히트맵 3칸이
점수·등급을 보여주고 위험 목록이 플래그를 나열하지만, 초보 귀농인이 "9월 C등급 · 야간
최저기온 위험"을 읽고 행동으로 옮기지 못한다(PRD §10-2 "장기 커리큘럼 서술").

단기(`daily_recommendation`)와 같은 구조 — 규칙 문구가 품질 하한선이고 LLM은 다듬기만
한다 — 인데 **캐시 키만 다르다.**

**밭당 1행인 이유**: 단기는 `target_date`가 자연 키라 날짜별로 행이 쌓이지만, 장기 창은
항상 오늘 기준이라 지난 창을 다시 보여줄 일이 없다(PRD §4.4 — 창이 과거를 보여줄 수
없다). 이력 소비처가 0이므로 남기지 않고 덮어쓴다(§2 YAGNI). 그래서
`uq_long_term(user_farm_id)`이고 `input_hash`는 키가 아니라 **히트/미스 판정 컬럼**이다.

**왜 창 시작월이 아니라 해시인가**: 창 시작월만 키로 잡으면 매월 23일 3개월전망 발표로
점수가 갈아엎어져도 문구가 낡은 채 남는다. 점수를 바꾸는 변경은 전망 말고도 실제로 여러
번 있었다 — 토양 backfill(`0024`), 지침 마이그레이션(`0027`·`0031`). 그때마다 캐시가
**에러 없이 조용히 거짓말**을 하게 되므로 §18-4에 걸린다. 해시에는 창·점수·등급·위험
플래그·전망 발표시각에 더해 **프롬프트 버전**까지 넣는다(프롬프트를 고쳐도 캐시 때문에
반영이 안 되는 함정을 막는다).

실측상 이 해시는 밭당 월 1~2회 바뀐다(창은 달 단위, 전망은 월 1회 발표). 즉 LLM 호출량이
밭 하나당 월 1~2회로 묶인다(§18-1 무분별 호출 금지).

`advice_text`가 nullable인 것은 `daily_recommendation`과 같다 — 생성 실패 이력을 행으로
남길 수 있게 열어두되, 읽는 쪽은 항상 규칙 문구 폴백을 갖는다.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "long_term_recommendation",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_farm_id", sa.BigInteger(), nullable=False),
        # sha256 hex는 항상 64자다. 길이를 박아두면 다른 해시로 슬쩍 바뀌는 것을 DB가 막는다.
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        # 키가 아니라 운영 조회용 — psql로 "이 문구가 어느 창의 것인가"를 볼 수 있게.
        sa.Column("window_start_year", sa.Integer(), nullable=False),
        sa.Column("window_start_month", sa.Integer(), nullable=False),
        sa.Column("risk_flags", postgresql.JSONB(), nullable=True),
        sa.Column("advice_text", sa.Text(), nullable=True),
        sa.Column("is_llm", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_farm_id"], ["user_farm.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_farm_id", name="uq_long_term"),
    )
    # 밭당 1행이라 uq_long_term이 곧 조회 인덱스다 — 별도 인덱스를 만들지 않는다
    # (daily_recommendation은 (farm, date) 범위 조회가 있어 ix_daily가 따로 필요했다).


def downgrade() -> None:
    op.drop_table("long_term_recommendation")
