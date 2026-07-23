from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RegionGrid(Base):
    """기상청 격자 매핑, 마스터(DB.md §3.3)."""

    __tablename__ = "region_grid"

    region_id: Mapped[int] = mapped_column(ForeignKey("region.id"), primary_key=True)
    nx: Mapped[int] = mapped_column()
    ny: Mapped[int] = mapped_column()
