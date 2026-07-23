from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class WeatherOutlook(Base):
    """3개월 장기예보 캐시, 범주형(DB.md §3.12). 평년치(WeatherClimatology)에 대한 방향성 보정 신호."""

    __tablename__ = "weather_outlook"
    __table_args__ = (
        UniqueConstraint(
            "region_id", "target_month", "indicator", "published_at", name="uq_outlook"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("region.id"))
    target_month: Mapped[date] = mapped_column()
    indicator: Mapped[str] = mapped_column()
    """'temp' | 'rainfall'(DB.md §3.12) — KMA 계절전망이 제공하는 지표만."""
    category: Mapped[str] = mapped_column()
    """'BELOW' | 'NORMAL' | 'ABOVE' — DB CHECK 제약으로 강제."""
    prob_below: Mapped[Decimal | None] = mapped_column(Numeric)
    prob_normal: Mapped[Decimal | None] = mapped_column(Numeric)
    prob_above: Mapped[Decimal | None] = mapped_column(Numeric)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
