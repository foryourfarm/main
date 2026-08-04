from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DailyRecommendation(Base):
    """단기 일일 추천 저장(DB.md §3.14). advice_text는 LLM 생성(폴백 시 규칙 문구, is_llm=false).

    **날짜만으로는 캐시 키가 부족하다**(`0034`). 단기예보는 발표 주기가 3시간이라 하루에
    여덟 번 갱신되는데, 날짜로만 잡으면 새벽에 저장한 "위험 없음"이 오후 폭우 예보에도
    그대로 나간다. `input_hash`가 그날 안에서의 낡음을 판정한다.
    """

    __tablename__ = "daily_recommendation"
    __table_args__ = (UniqueConstraint("user_farm_id", "target_date", name="uq_daily"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_farm_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user_farm.id", ondelete="CASCADE")
    )
    target_date: Mapped[date] = mapped_column()
    input_hash: Mapped[str | None] = mapped_column(String(64))
    """sha256 hex(`advice_cache.prompt_fingerprint`). `0034` 이전 행은 NULL이라 다음 조회가
    미스로 보고 한 번 다시 만든다 — backfill이 필요 없다."""

    risk_flags: Mapped[list[Any] | None] = mapped_column(JSONB)
    advice_text: Mapped[str | None] = mapped_column(Text)
    is_llm: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
