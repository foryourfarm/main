from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Numeric, SmallInteger, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SoilState(Base):
    """밭별 현재 추정 토양 상태(DB.md §3.9). 밭당 1행, 갱신은 upsert(uq_soil_state)."""

    __tablename__ = "soil_state"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_farm_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user_farm.id", ondelete="CASCADE"), unique=True
    )
    soil_texture: Mapped[str | None] = mapped_column()
    ph: Mapped[Decimal | None] = mapped_column(Numeric)
    ec: Mapped[Decimal | None] = mapped_column(Numeric)
    p2o5: Mapped[Decimal | None] = mapped_column(Numeric)
    organic_matter: Mapped[Decimal | None] = mapped_column(Numeric)
    k: Mapped[Decimal | None] = mapped_column(Numeric)
    ca: Mapped[Decimal | None] = mapped_column(Numeric)
    mg: Mapped[Decimal | None] = mapped_column(Numeric)
    """치환성 양이온(cmol/kg). 흙토람 POSIFERT_K/CA/MG. 사과·배·상추 채점에 쓴다(0024).

    단위가 문헌 밴드(RDA 교본 cmol/kg)와 같은 척도임을 실호출로 확인했다 — 유효인산이
    Bray-1과 교본에서 6배 갈렸던 것과 달리 여기서는 척도 불일치가 없다."""
    base_source: Mapped[str] = mapped_column()
    is_estimated: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    subsoil_texture_code: Mapped[int | None] = mapped_column(SmallInteger)
    """심토토성 원본 등급코드(1~6 또는 99=기타), 한글 변환값이 아니다. 흙토람 심토단면정보
    API(`soil_profile_client.get_soil_profile`)가 주는 2자리 코드("01"~"06"/"99")를 그 함수가
    정규화(선행 0 제거)한 값을 그대로 저장한다 — `crop_growth_guide.code_scores`(마이그레이션
    0038, 등급코드→점수 배점표) 조회 키와 자료형을 맞추기 위함이다(마이그레이션 0040).

    ⚠️ 적재 배선은 아직 없다: `get_soil_profile`은 PNU(19자리 지번코드)를 요구하는데
    `user_farm`은 `bjd_code`(법정동코드)만 갖고 있어 지금은 호출자가 0건이다. 즉 이 컬럼은
    당장 프로덕션에서 채워지지 않는다 — 컬럼·모델만 먼저 두고, 적재 경로는 별도 작업이다."""
