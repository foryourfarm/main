from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FarmActionLog(Base):
    """사용자 행동 기록 → 토양변화 입력(DB.md §3.8). action_type은 soil_change_rule.action_type과 대응."""

    __tablename__ = "farm_action_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_farm_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user_farm.id", ondelete="CASCADE")
    )
    action_type: Mapped[str] = mapped_column()
    amount: Mapped[Decimal | None] = mapped_column(Numeric)
    acted_on: Mapped[date] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
