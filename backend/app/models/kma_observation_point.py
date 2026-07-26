"""관측지점 마스터 (농업기상 1차 + 기상청 AWS 2차)."""

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class KmaObservationPoint(Base):
    """관측지점 마스터. **두 관측망을 함께 담는다** (`network`로 구분).

    | network | 관측망 | 지점 수 | 코드 예 | 역할 |
    |---|---|---|---|---|
    | `agri` | 농업기상(농진청) | 216 | `230802A001` | 1차. 일사량·일조시간 보유 |
    | `kma_aws` | 기상청 AWS | 534 | `108` | 2차. 1차 결측 보완 + 미커버 구역 |

    두 관측망의 지점코드는 조인되지 않으므로 계층을 잇는 키는 `region_id`다.
    적재: `scripts/gen_observation_point_seed.py` → `docs/seed/observation_point_seed.csv`
    → `scripts/load_observation_points.py`. 설계 근거는 `MappingReport.md`.
    """

    __tablename__ = "kma_observation_point"

    point_code: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()  # 지점명 (예: "서울", "영월군 영월읍")
    lat: Mapped[float] = mapped_column()  # 위도
    lon: Mapped[float] = mapped_column()  # 경도
    altitude: Mapped[int] = mapped_column()  # 해발고도 (m)
    nx: Mapped[int | None] = mapped_column()
    ny: Mapped[int | None] = mapped_column()
    """기상청 격자좌표. 구역-지점 거리 비교에 위경도 대신 이 정수 격자를 쓴다 —
    5km 격자라 칸 차이 × 5km로 거리를 근사하며, `region_grid`와 같은 좌표계라 바로 비교된다."""
    region_id: Mapped[int | None] = mapped_column(ForeignKey("region.id"))
    """지점이 속한 시군구. NULL이면 배정 실패 — 행정구역 격자 밖 도서(독도·격렬비도 등)다.
    조회에서 제외한다(§12 — NOT NULL로 묶으면 적재가 통째로 실패한다)."""
    network: Mapped[str] = mapped_column()  # 'agri' | 'kma_aws'
