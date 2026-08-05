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
    k: Mapped[Decimal | None] = mapped_column(Numeric)
    ca: Mapped[Decimal | None] = mapped_column(Numeric)
    mg: Mapped[Decimal | None] = mapped_column(Numeric)
    """치환성 양이온(cmol/kg). 흙토람 POSIFERT_K/CA/MG. 사과·배·상추 채점에 쓴다(0024).

    단위가 문헌 밴드(RDA 교본 cmol/kg)와 같은 척도임을 실호출로 확인했다 — 유효인산이
    Bray-1과 교본에서 6배 갈렸던 것과 달리 여기서는 척도 불일치가 없다."""
    base_source: Mapped[str] = mapped_column()
    is_estimated: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
