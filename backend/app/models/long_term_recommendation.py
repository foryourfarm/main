from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LongTermRecommendation(Base):
    """장기 탭(앞으로 3개월) 추천 문구 캐시(DB.md §3.16).

    **`daily_recommendation`과 키 전략이 다르다 — 밭당 1행이다.** 단기는 `target_date`가
    자연 키라 날짜별로 행이 쌓이지만, 장기 창은 항상 오늘 기준이라 **지난 창을 다시 보여줄
    일이 없다**(PRD §4.4 — 창이 과거를 보여줄 수 없다). 이력 소비처가 0이므로 행을 남기지
    않고 덮어쓴다(§2 YAGNI).

    히트/미스는 `input_hash`가 판정한다. 창 시작월만 키로 잡으면 매월 23일 3개월전망 발표나
    토양 backfill(`0024`)·지침 마이그레이션(`0027`·`0031`)으로 점수가 바뀌어도 문구가 낡은
    채 남는다 — 에러 없이 조용히 거짓말하는 부류라 §18-4에 걸린다.
    """

    __tablename__ = "long_term_recommendation"
    __table_args__ = (UniqueConstraint("user_farm_id", name="uq_long_term"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_farm_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user_farm.id", ondelete="CASCADE")
    )
    input_hash: Mapped[str] = mapped_column(String(64))
    """sha256 hex. 이 값이 바뀌면 저장된 문구는 낡은 것이다 — 재생성 트리거."""

    # 키가 아니라 디버깅·운영 조회용이다("이 문구가 어느 창의 것인가"를 psql로 볼 수 있게).
    window_start_year: Mapped[int] = mapped_column(Integer)
    window_start_month: Mapped[int] = mapped_column(Integer)

    risk_flags: Mapped[list[Any] | None] = mapped_column(JSONB)
    """이 문구가 왜 나왔나. daily_recommendation과 같은 이유로 함께 남긴다."""

    advice_text: Mapped[str | None] = mapped_column(Text)
    is_llm: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
