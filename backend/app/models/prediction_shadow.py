from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Numeric, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PredictionShadow(Base):
    """토양변화 shadow 예측 로그(핸드오프 §4.2). 목표별 1행(ph/organic_matter/available_p).

    P0에서는 사용자에게 노출하지 않고 DB에만 기록한다(`is_exposed=false`). 실측이 쌓이면
    같은 밭의 `soil_state_snapshot`과 연결해 MAE·구간 포함률을 재계산한다.
    `point`는 예측 변화량(Δ), `lo/hi`는 conformal 구간(available_p·폴백은 null).
    `model_version`+`data_version`으로 refresh 전후 회귀 감시(가이드 §2.4).
    """

    __tablename__ = "prediction_shadow"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_farm_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user_farm.id", ondelete="CASCADE")
    )
    target: Mapped[str] = mapped_column()  # ph | organic_matter | available_p
    point: Mapped[Decimal | None] = mapped_column(Numeric)
    lo: Mapped[Decimal | None] = mapped_column(Numeric)
    hi: Mapped[Decimal | None] = mapped_column(Numeric)
    model_version: Mapped[str] = mapped_column()
    data_version: Mapped[str] = mapped_column()
    feature_as_of: Mapped[date] = mapped_column(Date)
    target_date: Mapped[date] = mapped_column(Date)
    prediction_type: Mapped[str] = mapped_column()  # delta_regression | unavailable
    fallback_used: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    is_exposed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
