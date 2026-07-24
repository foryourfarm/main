from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Numeric, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SoilStateSnapshot(Base):
    """밭별 토양 실측 이력(append-only, 핸드오프 §6.2).

    기존 `soil_state`(밭당 1행 현재값 캐시)와 달리 실측 시각(`measured_at`)을 보존해
    토양변화 추론의 안전한 `feature_as_of`를 잡는다. `soil_state.computed_at`은 계산시각이라
    실측시각으로 쓸 수 없다(핸드오프 §2.1). 수정하지 않고 새 실측마다 행을 추가한다.
    """

    __tablename__ = "soil_state_snapshot"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_farm_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user_farm.id", ondelete="CASCADE")
    )
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ph: Mapped[Decimal | None] = mapped_column(Numeric)
    organic_matter: Mapped[Decimal | None] = mapped_column(Numeric)
    available_p: Mapped[Decimal | None] = mapped_column(Numeric)
    source: Mapped[str] = mapped_column()
    is_measured: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    is_imputed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
