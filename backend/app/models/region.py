from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Region(Base):
    """지역(전국 시/군) 마스터 — 시드로만 적재(DB.md §3.2). id는 시드가 고정 부여."""

    __tablename__ = "region"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column()
    sido: Mapped[str] = mapped_column()
    altitude_m: Mapped[int | None] = mapped_column()
    """구역 대표 고도(m) — 관청 소재지 대표점의 SRTM 표고. 평년치 도너 필터 기준(§8.5).

    격자중심이 아니라 대표점인 이유: 격자중심(5km)은 산비탈에 떨어진다(서귀포시 209m vs
    대표점 76m). 대표점은 사람·농지가 있는 저지대라 "대표 농지 고도"에 가깝다.
    적재: scripts/load_altitudes.py
    """
