from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CropGrowthStage(Base):
    """작물별 생육단계 → 날짜 매핑(마스터·시드). planting_date/달력에서 단계를 파생하는 근거.

    농업 기준값이므로 코드가 아니라 시드로만 적재한다(CLAUDE.md §18-2). 근거: 농촌진흥청 농사로.

    mode:
      - `day_of_year`: 다년생(사과·배) — 연중 일자(1~366)로 단계 판정. planting_date와 무관.
      - `days_after_planting`: 1년생(감자) — 파종 후 경과일로 판정(재배작형마다 파종일이 달라 경과일이 옳음).
    range_start/range_end는 mode 값의 포함 구간. priority가 높을수록 진행된 단계(겹치면 우선).
    상추는 하위 단계 문헌이 연중 전체를 다뤄 사실상 전기간과 같아 행을 두지 않는다
    → resolver가 None(전기간 공통 지침) 반환. 오이는 노지 재배기간(4~9월)이 문헌으로
    확인돼(0019) 단일 단계 행을 둔다 — 그 밖 달은 사과·배처럼 "단계 없음"이 된다.
    """

    __tablename__ = "crop_growth_stage"
    __table_args__ = (
        UniqueConstraint("crop_id", "growth_stage", name="uq_crop_growth_stage"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crop.id"))
    growth_stage: Mapped[str] = mapped_column()
    mode: Mapped[str] = mapped_column()  # day_of_year | days_after_planting
    range_start: Mapped[int] = mapped_column()
    range_end: Mapped[int] = mapped_column()
    priority: Mapped[int] = mapped_column()
