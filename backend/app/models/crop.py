from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Crop(Base):
    """작물 마스터(5종) — 시드로만 적재(DB.md §3.4). 게임식 crop_type/season_weeks 없음."""

    __tablename__ = "crop"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column()
