from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Crop(Base):
    """작물 마스터(5종) — 시드로만 적재(DB.md §3.4). 게임식 crop_type/season_weeks 없음."""

    __tablename__ = "crop"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column()
    exam_field_type: Mapped[str | None] = mapped_column()
    """흙토람 경지구분 코드(1=논 2=밭 3=시설 4=과수). 토양 표본을 이 값으로 걸러 평균한다.

    같은 읍면동에서도 경지구분에 따라 값이 크게 다르다(실측: 밭 유기물 20 vs 과수 51~62).
    농업 기준값이라 코드가 아니라 마스터로 관리(CLAUDE.md §18-2).
    """
