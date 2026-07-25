from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class WeatherClimatology(Base):
    """월별 평년값 캐시, 지역 최초 등록 시 확보(DB.md §3.11). 장기 탭 적합도 계산의 baseline."""

    __tablename__ = "weather_climatology"
    __table_args__ = (UniqueConstraint("region_id", "month", name="uq_climatology"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("region.id"))
    month: Mapped[int] = mapped_column()
    temp_avg_normal: Mapped[Decimal | None] = mapped_column(Numeric)
    temp_night_min_normal: Mapped[Decimal | None] = mapped_column(Numeric)
    rainfall_normal: Mapped[Decimal | None] = mapped_column(Numeric)
    sunlight_normal: Mapped[Decimal | None] = mapped_column(Numeric)
    source: Mapped[str] = mapped_column()
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
