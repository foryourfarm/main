from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class WeatherClimatology(Base):
    """월별 기상 평균 캐시, 지역 최초 등록 시 확보(DB.md §3.11). 장기 탭 적합도의 baseline.

    ⚠️ **`*_normal` 컬럼은 기상청 "평년값"이 아니다.** 기상청 평년값은 30년(1991~2020)
    통계인데 여기 들어가는 것은 **5년(2021~2025) 관측 평균**이다 — `source`가
    `obs_mean_2021_2025`(농업기상) 또는 `aws_mean_2021_2025`(AWS)인 이유다.
    실측하니 30년 평년값보다 12개월 평균 **+0.95℃** 따뜻하고, 월별로 −0.30 ~ +2.04℃
    갈린다(2026-08-02, 같은 219지점 대조. `docs/temperature-open-decisions.md` §①).

    컬럼명은 마이그레이션 이력 때문에 `_normal`로 두지만, **유저에게 "평년값"이라고
    적으면 거짓이다.** 화면 문구는 `suitability_service.CLIMATOLOGY_PERIOD_LIMITATION`이
    실제 성격을 밝힌다 — 새 문구를 쓸 때 그쪽을 따를 것.
    """

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
