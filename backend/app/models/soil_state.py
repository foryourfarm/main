from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Numeric, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SoilState(Base):
    """밭별 현재 추정 토양 상태(DB.md §3.9). 밭당 1행, 갱신은 upsert(uq_soil_state)."""

    __tablename__ = "soil_state"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_farm_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user_farm.id", ondelete="CASCADE"), unique=True
    )
    soil_texture: Mapped[str | None] = mapped_column()
    ph: Mapped[Decimal | None] = mapped_column(Numeric)
    ec: Mapped[Decimal | None] = mapped_column(Numeric)
    p2o5: Mapped[Decimal | None] = mapped_column(Numeric)
    organic_matter: Mapped[Decimal | None] = mapped_column(Numeric)
    base_source: Mapped[str] = mapped_column()
    is_estimated: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
