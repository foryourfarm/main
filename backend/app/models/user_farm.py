from datetime import date, datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserFarm(Base):
    """유저의 밭 = 실제 농사 단위(DB.md §3.7). 생육 단계는 저장하지 않고 planting_date로 파생 계산(§8.3)."""

    __tablename__ = "user_farm"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    region_id: Mapped[int] = mapped_column(ForeignKey("region.id"))
    bjd_code: Mapped[str | None] = mapped_column(ForeignKey("district.bjd_code"))
    """읍면동 = 토양 기준값 조회 단위(PRD.md §5). 0014 이전에 등록된 밭은 NULL일 수 있다."""
    crop_id: Mapped[int] = mapped_column(ForeignKey("crop.id"))
    planting_date: Mapped[date] = mapped_column()
    label: Mapped[str | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
