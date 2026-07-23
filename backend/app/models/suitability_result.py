from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Numeric, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SuitabilityResult(Base):
    """장기 적합도 baseline 캐시(DB.md §3.13). 평년치 기준 baseline만 저장 — 결정론적 캐시.
    장기예보(outlook) 보정은 캐시하지 않고 조회 시점에 얹는다(read-time, §8.1)."""

    __tablename__ = "suitability_result"
    __table_args__ = (
        UniqueConstraint("region_id", "crop_id", "growth_stage", name="uq_suit"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("region.id"))
    crop_id: Mapped[int] = mapped_column(ForeignKey("crop.id"))
    growth_stage: Mapped[str] = mapped_column()
    score: Mapped[Decimal] = mapped_column(Numeric)
    grade: Mapped[str] = mapped_column()
    """'S' | 'A' | 'B' | 'C' — DB CHECK 제약으로 강제(DB.md §3.13)."""
    breakdown: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    risk_flags: Mapped[list[Any] | None] = mapped_column(JSONB)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
