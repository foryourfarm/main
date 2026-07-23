from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class WeatherSnapshot(Base):
    """기상 실황/예보 캐시(DB.md §3.10). kind='OBS'는 작년 실측 백필도 재사용(새 테이블 불필요)."""

    __tablename__ = "weather_snapshot"
    __table_args__ = (
        UniqueConstraint("region_id", "kind", "base_at", "target_date", name="uq_weather"),
        Index("ix_weather_region_target", "region_id", "target_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("region.id"))
    kind: Mapped[str] = mapped_column()
    """'OBS' | 'FORECAST' — DB CHECK 제약으로 강제(DB.md §3.10)."""
    base_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    target_date: Mapped[date] = mapped_column()
    temp_avg: Mapped[Decimal | None] = mapped_column(Numeric)
    temp_night_min: Mapped[Decimal | None] = mapped_column(Numeric)
    rainfall: Mapped[Decimal | None] = mapped_column(Numeric)
    sunlight: Mapped[Decimal | None] = mapped_column(Numeric)
    is_imputed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
