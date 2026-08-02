from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class District(Base):
    """법정동 마스터(10자리) — 읍면동 + 리. 온보딩 선택지 + 흙토람 조회 키(PRD.md §5).

    시/군(region)은 기상·적합도·ML 단위, 법정동은 토양 단위 — 층이 다르다.

    선택지로 노출되는 건 **말단**만이다(리가 있으면 리, 없으면 동·읍·면). 리를 가진 읍·면 행도
    테이블에는 남아 있다 — 리 전환 전에 면 코드로 등록된 밭이 FK를 걸고 있어서다.
    노출 필터는 farm_service.list_districts. 설계: docs/design/ri-level-district.md
    """

    __tablename__ = "district"

    bjd_code: Mapped[str] = mapped_column(primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("region.id"))
    name: Mapped[str] = mapped_column()
    altitude_m: Mapped[int | None] = mapped_column()
    """밭 위치 대표 고도(m). 기온 감률 보정 기준(0.65℃/100m)."""
    altitude_source: Mapped[str | None] = mapped_column()
    """고도를 어느 점에서 땄는지. 근사 정도가 달라 한계 문구가 이걸 보고 갈린다(§18-4).

    `ri_polygon`=리 경계 중심점 / `emd_point`=읍·면·동 대표점(취락) /
    `emd_polygon`=동 경계 중심점 / `region_point`=시군구 대표점(최종 폴백).

    층마다 우선순위가 다르다 — 리는 폴리곤이 1순위지만 읍면동은 취락 점이 1순위다.
    읍면동은 영역이 넓어 기하 중심이 사람 없는 고지대로 올라가기 때문이다(실측 편향 +53m).
    근거·규칙: scripts/gen_altitude_seed.py. 적재: scripts/load_altitudes.py
    """


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
    ca: Mapped[Decimal | None] = mapped_column(Numeric)
    mg: Mapped[Decimal | None] = mapped_column(Numeric)
    """치환성 양이온(cmol/kg). 흙토람 POSIFERT_K/CA/MG — 파싱은 되고 있었으나 저장할 곳이
    없어 버려지던 값이다(0024에서 컬럼 추가). 사과·배·상추 채점에 쓴다."""
    sample_count: Mapped[int] = mapped_column()
    """평균에 쓴 표본 수. 0이면 그 경지구분 표본이 없다는 뜻(값은 전부 NULL)."""
    source: Mapped[str] = mapped_column()
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
