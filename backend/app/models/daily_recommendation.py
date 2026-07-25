from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DailyRecommendation(Base):
    """단기 일일 추천 저장(DB.md §3.14). advice_text는 LLM 생성(폴백 시 규칙 문구, is_llm=false)."""

    __tablename__ = "daily_recommendation"
    __table_args__ = (UniqueConstraint("user_farm_id", "target_date", name="uq_daily"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_farm_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user_farm.id", ondelete="CASCADE")
    )
    target_date: Mapped[date] = mapped_column()
    risk_flags: Mapped[list[Any] | None] = mapped_column(JSONB)
    advice_text: Mapped[str | None] = mapped_column(Text)
    is_llm: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
