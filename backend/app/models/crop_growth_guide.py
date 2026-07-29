from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CropGrowthGuide(Base):
    """작물×지표×생육단계별 생육 지침, 마스터·직접 제작(DB.md §3.5)."""

    __tablename__ = "crop_growth_guide"
    __table_args__ = (UniqueConstraint("crop_id", "growth_stage", "indicator", name="uq_guide"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crop.id"))
    growth_stage: Mapped[str | None] = mapped_column()
    indicator: Mapped[str] = mapped_column()
    optimal_min: Mapped[Decimal | None] = mapped_column(Numeric)
    optimal_max: Mapped[Decimal | None] = mapped_column(Numeric)
    allowed_min: Mapped[Decimal | None] = mapped_column(Numeric)
    allowed_max: Mapped[Decimal | None] = mapped_column(Numeric)
    weight: Mapped[Decimal] = mapped_column(Numeric)
    # 위험구간(허용경계 밖) 감쇠폭. 전국 실측 산포도 기반 절대폭(마이그레이션 0020).
    # NULL이면 룰 엔진이 종전 완충폭 1배로 폴백한다 — 척도를 지어내지 않는다.
    risk_width: Mapped[Decimal | None] = mapped_column(Numeric)
    risk_width_source: Mapped[str | None] = mapped_column()
    source_ref: Mapped[str | None] = mapped_column()
    """이 기준값의 근거(문헌·시드 출처). "이 숫자 어디서 왔나"에 답할 수 있어야 한다."""
    confidence: Mapped[str | None] = mapped_column()
    """domestic_measured | foreign_literature | provisional.

    국내 실측과 해외 문헌 잠정치를 구분해 UI 표현 강도를 조절한다("국내 실측" vs
    "이론 추정") — 근사를 확정값처럼 보이게 하지 않기 위한 장치(§18-4).
    """
