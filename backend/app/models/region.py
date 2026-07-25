from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Region(Base):
    """지역(전국 시/군) 마스터 — 시드로만 적재(DB.md §3.2). id는 시드가 고정 부여."""

    __tablename__ = "region"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column()
    sido: Mapped[str] = mapped_column()
