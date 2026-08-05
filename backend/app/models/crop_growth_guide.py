from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
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
    cultivation_type: Mapped[str | None] = mapped_column()
    """open_field | facility. 이 지표 기준표의 출처가 노지/시설 중 어느 쪽인지 — 경계값
    자체와는 무관한 출처 속성이다(마이그레이션 0038)."""
    allowed_min_kind: Mapped[str | None] = mapped_column()
    allowed_max_kind: Mapped[str | None] = mapped_column()
    """literature_limit | cultivable_range | literature_threshold | derived | heuristic |
    not_applicable. 방향별로 컬럼을 나눈 이유: 한 지표 안에서 하한·상한의 성격이 다를 수
    있다(사과 기온은 하한이 cultivable_range, 상한이 heuristic) — 한 컬럼이면 반드시 한쪽이
    거짓 표기가 된다. 채점 반영(literature_limit이면 허용경계 0점)은 P2 몫이고 지금은
    표기만 갖는다(마이그레이션 0038)."""
    method: Mapped[str | None] = mapped_column(Text)
    """측정 프로토콜 서술(예: "1:5 물(H2O) 침출, pH meter"). 계약 서술이 길어 VARCHAR인
    source_ref와 달리 Text로 둔다(마이그레이션 0038)."""
    code_scores: Mapped[dict[str, float | None] | None] = mapped_column(JSONB)
    """범주형 등급코드 → 점수 배점표(예: 심토토성 1~6·99). 밴드가 아니라 조회형 채점용.
    subsoil_texture 지침 행 자체가 아직 없어(P4) 지금은 항상 NULL이다(마이그레이션 0038)."""
