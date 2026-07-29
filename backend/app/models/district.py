from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class District(Base):
    """읍면동 마스터(법정동 10자리). 온보딩 드롭다운 + 흙토람 조회 키(PRD.md §5).

    시/군(region)은 기상·적합도·ML 단위, 읍면동은 토양 단위 — 층이 다르다.
    """

    __tablename__ = "district"

    bjd_code: Mapped[str] = mapped_column(primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("region.id"))
    name: Mapped[str] = mapped_column()


class DistrictSoil(Base):
    """읍면동×경지구분 토양 기준값 캐시(DB.md §3.9).

    같은 동네에 여러 밭이 등록돼도 외부 API를 다시 부르지 않는다(§12). 경지구분을 키에
    포함하는 이유: 같은 읍면동에서도 밭/과수/시설 값이 크게 다르다(실측 유기물 20 vs 62).
    """

    __tablename__ = "district_soil"
    __table_args__ = (UniqueConstraint("bjd_code", "field_type", name="uq_district_soil"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bjd_code: Mapped[str] = mapped_column(ForeignKey("district.bjd_code"))
    field_type: Mapped[str] = mapped_column()
    """흙토람 경지구분 코드(1=논 2=밭 3=시설 4=과수 ...). crop.exam_field_type과 대응."""
    ph: Mapped[Decimal | None] = mapped_column(Numeric)
    ec: Mapped[Decimal | None] = mapped_column(Numeric)
    p2o5: Mapped[Decimal | None] = mapped_column(Numeric)
    organic_matter: Mapped[Decimal | None] = mapped_column(Numeric)
    k: Mapped[Decimal | None] = mapped_column(Numeric)
    """치환성 칼륨 cmol+/kg (흙토람 POSIFERT_K, 0023)."""
    ca: Mapped[Decimal | None] = mapped_column(Numeric)
    """치환성 칼슘 cmol+/kg (흙토람 POSIFERT_CA, 0023)."""
    mg: Mapped[Decimal | None] = mapped_column(Numeric)
    """치환성 마그네슘 cmol+/kg (흙토람 POSIFERT_MG, 0023)."""
    sample_count: Mapped[int] = mapped_column()
    """평균에 쓴 표본 수. 0이면 그 경지구분 표본이 없다는 뜻(값은 전부 NULL)."""
    source: Mapped[str] = mapped_column()
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
