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
    normal_value: Mapped[Decimal | None] = mapped_column(Numeric)
    """권역 평년값(RSS normalYear). 우리 weather_climatology와 별개 — 권역 단위 값."""
    similar_low: Mapped[Decimal | None] = mapped_column(Numeric)
    similar_high: Mapped[Decimal | None] = mapped_column(Numeric)
    """'비슷' tercile 구간 경계. 보정 단위 δ를 여기서 유도한다(상수 추측 금지).
    평년값 기준 비대칭이라(실측: 평년 296.6, 구간 209.3~374.4) 반폭 하나로 뭉개지 않는다."""
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
