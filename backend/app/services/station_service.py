"""구역 → 관측지점 해석 (MappingReport.md §6.3).

**왜 이 계층이 필요한가**: 관측망이 두 개인데 지점 수(농업기상 215 / AWS 533)와 구역 수(256)가
다르고 지점코드도 조인되지 않는다(`230802A001` vs `108`). 그래서 "이 구역의 날씨를 어디서
받는가"를 한 곳에서 결정한다.

**결정 규칙** (사람이 확정한 것 — 임의 선택이 아니다):
1. **최근접 지점 1개**를 쓴다. 한 구역에 지점이 15개까지 있는 경우가 있어(태백 등) 평균을
   쓰면 산지·평지가 섞여 왜곡되고, 무엇보다 "어느 값을 썼는지"가 불명확해진다.
   최근접 1개는 결정론적이고 근거를 설명할 수 있다(§2 결정론 우선).
2. **1차(농업기상) 우선.** 일사량·일조시간이 여기에만 있어 장기 탭 일조 지표가 이 계층에
   의존한다. 1차가 없거나 결측이면 2차(AWS)로 내려간다.
3. **거리를 반드시 함께 반환한다.** 구역 안에 지점이 없어 15km 떨어진 값을 쓰는 경우가 있고,
   그것을 그 구역 실측처럼 보이게 하면 안 된다(§18-4, §1-4 정직한 한계 표기).

거리 계산은 위경도가 아니라 **격자(nx, ny) 정수 거리**로 한다 — 농업기상 지점은 위경도가
없고(지점정보 API 명세서 미확보) 격자만 있기 때문이다. 5km 격자라 칸 차이 × 5km로 근사한다.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import KmaObservationPoint, RegionGrid

GRID_KM = 5.0  # 기상청 단기예보 격자 간격

AGRI = "agri"  # 1차: 농업기상 — 일사량·일조시간 보유
KMA_AWS = "kma_aws"  # 2차: 기상청 AWS — 결측 보완

# 구역 밖 지점을 쓸 때 허용할 최대 거리. 실측 최대가 15.8km라 여유를 두고 40km로 둔다.
# 이보다 멀면 "그 구역 날씨"라고 부를 수 없어 결측으로 처리한다 — 아무 값이나 주는 것보다
# 데이터 없음이 정직하다(§18-4).
MAX_DISTANCE_KM = 40.0


@dataclass(frozen=True)
class StationMatch:
    """구역에 배정된 관측지점과 그 한계."""

    point_code: str
    name: str
    network: str
    distance_km: float
    """구역 격자 중심에서의 거리. 0이면 구역 안의 지점이다."""

    @property
    def is_inside_region(self) -> bool:
        return self.distance_km == 0.0

    @property
    def has_solar_radiation(self) -> bool:
        """일사량·일조시간을 기대할 수 있는가 — 1차 관측망만 보유한다."""
        return self.network == AGRI

    def limitation_note(self) -> str | None:
        """사용자에게 보일 한계 문구. 구역 안 1차 지점이면 표기할 것이 없다."""
        if self.network != AGRI:
            if self.is_inside_region:
                return f"{self.name} 관측소(기상청 AWS) 값입니다 — 일조 자료는 제공되지 않습니다."
            return (
                f"이 지역에 관측소가 없어 약 {self.distance_km:.0f}km 떨어진 "
                f"{self.name} 관측소(기상청 AWS) 값을 사용했습니다."
            )
        if not self.is_inside_region:
            return (
                f"이 지역에 관측소가 없어 약 {self.distance_km:.0f}km 떨어진 "
                f"{self.name} 관측소 값을 사용했습니다."
            )
        return None


def _distance_km(a_nx: int, a_ny: int, b_nx: int, b_ny: int) -> float:
    return (((a_nx - b_nx) ** 2 + (a_ny - b_ny) ** 2) ** 0.5) * GRID_KM


def resolve_station(
    db: Session,
    region_id: int,
    prefer: str = AGRI,
    allowed_codes: set[str] | None = None,
) -> StationMatch | None:
    """구역이 쓸 관측지점 1개. 없으면 None(값을 만들어내지 않는다).

    `prefer` 관측망에서 최근접 지점을 먼저 찾고, 없으면 다른 관측망으로 내려간다.
    격자 매핑이 없는 구역은 거리를 잴 수 없어 None이다 — 조용히 아무 지점이나 주지 않는다.

    Args:
        allowed_codes: 후보를 이 지점코드들로 제한한다. **"최근접"이 아니라 "쓸 수 있는 것 중
            최근접"을 골라야 하는 경우**에 쓴다 — 지점이 마스터에 있어도 특정 지표(예: 일사량)
            관측값이 없을 수 있고, 그런 지점을 골라 놓으면 그 구역은 값을 못 받는다.
            실측: 116개 구역 중 20개가 최근접 지점에 일사량이 없어 비어 있었다.
    """
    region_grid = db.query(RegionGrid).filter(RegionGrid.region_id == region_id).first()
    if region_grid is None:
        return None  # 격자 매핑 없음 → 거리 비교 불가

    # 격자가 있는 지점만 후보다. 전국 748개라 메모리 비교로 충분하다 — 지점 마스터는
    # 거의 바뀌지 않으므로 공간 인덱스를 도입할 이유가 없다(YAGNI).
    candidates = (
        db.query(KmaObservationPoint)
        .filter(KmaObservationPoint.nx.isnot(None), KmaObservationPoint.ny.isnot(None))
        .all()
    )

    order = [prefer] + [n for n in (AGRI, KMA_AWS) if n != prefer]
    for network in order:
        best: StationMatch | None = None
        for station in candidates:
            if station.network != network or station.nx is None or station.ny is None:
                continue
            if allowed_codes is not None and station.point_code not in allowed_codes:
                continue
            distance = _distance_km(region_grid.nx, region_grid.ny, station.nx, station.ny)
            if distance > MAX_DISTANCE_KM:
                continue
            # 동거리면 point_code 순으로 고정해 결정론을 보장한다(§2).
            if best is None or (distance, station.point_code) < (best.distance_km, best.point_code):
                best = StationMatch(
                    point_code=station.point_code,
                    name=station.name,
                    network=station.network,
                    distance_km=distance,
                )
        if best is not None:
            return best
    return None
