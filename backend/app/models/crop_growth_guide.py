from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CropGrowthGuide(Base):
    """작물×지표×생육단계별 생육 지침, 마스터·직접 제작(DB.md §3.5)."""

    __tablename__ = "crop_growth_guide"
    __table_args__ = (UniqueConstraint("crop_id", "growth_stage", "indicator", name="uq_guide"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crop.id"))
    growth_stage: Mapped[str | None] = mapped_column()
    indicator: Mapped[str] = mapped_column()
    optimal_min: Mapped[Decimal | None] = mapped_column(Numeric)
    optimal_max: Mapped[Decimal | None] = mapped_column(Numeric)
    allowed_min: Mapped[Decimal | None] = mapped_column(Numeric)
    allowed_max: Mapped[Decimal | None] = mapped_column(Numeric)
    weight: Mapped[Decimal] = mapped_column(Numeric)
