from sqlalchemy import Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RegionOutlookZone(Base):
    """시/군 → 기상청 장기예보 권역 매핑(마스터·시드, DB.md §3.12).

    3개월전망 RSS는 13개 권역 단위로만 나와 시/군 256개에 붙이려면 매핑이 필요하다.
    is_fallback=true는 권역을 특정하지 못해 전국 권역값을 쓰는 지역(현재 태백시 1건) —
    UI에 '권역 미특정'을 병기해야 한다.
    """

    __tablename__ = "region_outlook_zone"

    region_id: Mapped[int] = mapped_column(ForeignKey("region.id"), primary_key=True)
    zone_name: Mapped[str] = mapped_column()
    is_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
