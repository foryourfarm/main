"""기상청 AWS 관측지점 (마스터)."""

from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class KmaObservationPoint(Base):
    """기상청 510개 자동기상관측소(AWS) 지점 정보.

    출처: 기상청 API (getAwsStnLstTbl) 또는 공개 데이터
    역할: weather_snapshot 조회 시 지점 정보, region 매핑
    """

    __tablename__ = "kma_observation_point"

    point_code: Mapped[str] = mapped_column(primary_key=True)  # 지점번호 (예: "108" = 서울)
    name: Mapped[str] = mapped_column()  # 지점명 (예: "서울")
    lat: Mapped[float] = mapped_column()  # 위도
    lon: Mapped[float] = mapped_column()  # 경도
    altitude: Mapped[int] = mapped_column()  # 해발고도 (m)
