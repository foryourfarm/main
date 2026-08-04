from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class WeatherSnapshot(Base):
    """기상 실황/예보 캐시(DB.md §3.10). kind='OBS'는 작년 실측 백필도 재사용(새 테이블 불필요).

    **기온 컬럼 3개의 쓰임이 다르다**(0032에서 분리).
      - `temp_avg`(일평균) → 채점 지표 `temp_day`의 입력. 화면 표시용이 아니다.
      - `temp_max`(일최고) → 화면 "낮 최고기온". 종전엔 이 값이 없어 일평균을 "낮 기온"이라
        불렀는데, 실측에서 6.7℃까지 벌어졌다(일평균 31.3 vs 일최고 38).
      - `temp_night_min`(일최저) → 화면 "야간 최저" + 채점 지표 `temp_night_min`.
    """

    __tablename__ = "weather_snapshot"
    __table_args__ = (
        UniqueConstraint("region_id", "kind", "base_at", "target_date", name="uq_weather"),
        Index("ix_weather_region_target", "region_id", "target_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("region.id"))
    kind: Mapped[str] = mapped_column()
    """'OBS' | 'FORECAST' — DB CHECK 제약으로 강제(DB.md §3.10)."""
    base_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    target_date: Mapped[date] = mapped_column()
    temp_avg: Mapped[Decimal | None] = mapped_column(Numeric)
    """일평균기온. **채점(`temp_day`) 입력이며 화면의 '낮 최고기온'이 아니다**(위 docstring)."""
    temp_max: Mapped[Decimal | None] = mapped_column(Numeric)
    """일최고기온(0032 신규). TMX 우선, 첫날은 TMX가 오지 않아 TMP 최고로 폴백.
    이전 발표분 캐시는 NULL이므로 읽는 쪽이 방어해야 한다."""
    temp_night_min: Mapped[Decimal | None] = mapped_column(Numeric)
    rainfall: Mapped[Decimal | None] = mapped_column(Numeric)
    sunlight: Mapped[Decimal | None] = mapped_column(Numeric)
    hourly_temp: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    """시간별 기온 `[{"h": 15, "t": "29.5"}, …]`(시각 오름차순, 0032 신규). 모달 그래프용."""
    is_imputed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    """그날 예보 표본이 하루를 온전히 덮지 못함 — 집계값이 편향돼 있다는 뜻.

    종전엔 항상 false로 박혀 있었다(쓰는 코드가 없었다). 단기예보는 첫날이 발표시각 이후
    시간대만 오고(실측: 14시 발표 → 15~23시 9개) 예보 지평 끝날은 앞부분만 와서, 그 표본으로
    낸 평균·최고·최저가 하루 전체를 대표하지 못한다. CLAUDE.md §12가 요구하는 "대체됨 플래그"에
    해당하므로 새 컬럼을 만들지 않고 이 컬럼의 의미를 확장했다."""
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
