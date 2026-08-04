from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CropGrowthGuide(Base):
    """작물×지표×생육단계별 생육 지침, 마스터·직접 제작(DB.md §3.5)."""

    __tablename__ = "crop_growth_guide"
    # 재배형이 키에 들어간다(0032) — 같은 지표에 노지·시설 두 밴드를 둘 수 있어야 한다.
    __table_args__ = (
        UniqueConstraint(
            "crop_id", "growth_stage", "indicator", "cultivation_type", name="uq_guide"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crop.id"))
    growth_stage: Mapped[str | None] = mapped_column()
    indicator: Mapped[str] = mapped_column()
    cultivation_type: Mapped[str] = mapped_column()
    """open_field | facility — 이 밴드가 어느 재배형 기준인가(0032).

    오이·감자·상추의 화학성 밴드는 RDA 처방 5차의 **「시설재배토양」** 진단기준표인데
    우리 채점 입력은 노지 실측이다. 그 불일치가 `source_ref` 문자열에만 있어 코드가 읽을
    수 없었다. 같은 지표에 두 행이 있으면 `load_guides()`가 `open_field`를 우선한다.
    """
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
    allowed_min_kind: Mapped[str | None] = mapped_column()
    allowed_max_kind: Mapped[str | None] = mapped_column()
    """허용경계 **방향별** 성격(0032). 값 도메인은 그 마이그레이션의 `ALLOWED_KINDS`.

    채점이 분기하는 것은 `literature_limit` 하나다 — 문헌이 준 생리적 절대한계(생장이 완전히
    멈추는 점)라 그 경계 점수가 60이 아니라 **0**이 된다. 나머지는 표기용이다.

    방향별로 나눈 이유: 한 행 안에서 두 경계의 성격이 갈린다. 사과 착과기 기온은
    `allowed_min 15.0`이 ±50% 휴리스틱이고 `allowed_max 31`은 출처가 특정되지 않았다.
    """
    method: Mapped[str | None] = mapped_column()
    """이 기준값이 어느 측정 프로토콜에서 나왔는가(0032). 기온·강수는 NULL.

    추출법이 다르면 같은 단위라도 비교 대상이 아니다 — EC는 보고 관행이 정확히 5배 갈리고
    pH는 H₂O법과 KCl법이 약 1.2 벌어진다. `unknown`인 지표는 단독으로 판정하지 않는다.
    """
