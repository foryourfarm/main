from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class WeatherClimatology(Base):
    """월별 평년값 캐시, 지역 최초 등록 시 확보(DB.md §3.11). 장기 탭 적합도 계산의 baseline."""

    __tablename__ = "weather_climatology"
    __table_args__ = (UniqueConstraint("region_id", "month", name="uq_climatology"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("region.id"))
    month: Mapped[int] = mapped_column()
    temp_avg_normal: Mapped[Decimal | None] = mapped_column(Numeric)
    temp_night_min_normal: Mapped[Decimal | None] = mapped_column(Numeric)
    rainfall_normal: Mapped[Decimal | None] = mapped_column(Numeric)
    sunlight_normal: Mapped[Decimal | None] = mapped_column(Numeric)
    solar_radiation_normal: Mapped[Decimal | None] = mapped_column(Numeric)
    """일사량 월평년(MJ/m²/day, 농업기상 V3 srqty). 일조시간 환산용 원자료 — 실측
    일조(sunlight_normal)가 없을 때 여기서 환산한다(services/sunlight_calculation.py)."""
    reference_altitude_m: Mapped[int | None] = mapped_column()
    """이 평년치가 대표하는 고도(m). 기온 감률 보정의 기준선이다.

    구역 대표 고도(`region.altitude_m`)와 다르다 — 관측지점은 대표점보다 높은 경향이 있어
    실측 비교에서 최대 370m(남원시) 벌어졌고, 그걸 기준선으로 쓰면 보정이 2.4℃ 틀어진다.
    농업기상=집계에 들어간 읍면동 고도 평균, AWS=도너 지점 고도의 거리가중 평균.
    """
    source: Mapped[str] = mapped_column()
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
