from decimal import Decimal

from sqlalchemy import Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SoilChangeRule(Base):
    """토양 변화 계수, 마스터 — 토양변화 모델(DB.md §3.6). 계수는 코드 하드코딩 금지, 이 시드로만 관리."""

    __tablename__ = "soil_change_rule"
    __table_args__ = (UniqueConstraint("action_type", "indicator", name="uq_soil_rule"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    action_type: Mapped[str] = mapped_column()
    indicator: Mapped[str] = mapped_column()
    effect_coeff: Mapped[Decimal] = mapped_column(Numeric)
    decay_days: Mapped[int | None] = mapped_column()
    source_ref: Mapped[str] = mapped_column()
