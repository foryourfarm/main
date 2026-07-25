"""평년치 조회 + 인접 지역 대체 (DB.md §3.11, §8.5 결측 대체).

왜 대체가 필요한가: 평년치가 256개 시/군 중 102개만 적재돼 있다(관측 5년 근사 CSV의 커버
범위 한계). 나머지 154개 지역은 장기 탭이 12개월 전부 "데이터 부족"으로 나와 화면이
아무 정보도 주지 못한다(예: 부천시 원미구, 고창군).

대체 방식: `region_grid`의 기상청 격자좌표(5km 격자) 거리로 가장 가까운 평년치 보유
지역의 값을 쓴다. 시/도 평균보다 지리적으로 정확하고, 격자 단위라 거리에 실제 의미가 있다.

**대체는 반드시 표기한다** — 어느 지역 값을 빌렸는지, 몇 km 떨어졌는지 UI에 병기한다.
근사를 확정값처럼 보이게 하지 않는다(§18-4). 대체 없이 "데이터 없음"으로 두는 것보다
정보 가치가 크지만, 빌린 값임을 숨기면 오히려 더 나쁘다.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Region, RegionGrid, WeatherClimatology

GRID_KM = 5.0  # 기상청 단기예보 격자 간격


@dataclass(frozen=True)
class ClimatologySource:
    """평년치와 그 출처. substituted_from이 있으면 다른 지역 값을 빌린 것이다."""

    by_month: dict[int, WeatherClimatology]
    substituted_from: str | None = None
    distance_km: float | None = None

    @property
    def is_substituted(self) -> bool:
        return self.substituted_from is not None


def _grid_distance_km(a: RegionGrid, b: RegionGrid) -> float:
    """격자 좌표 유클리드 거리(km). 5km 격자라 칸 차이 × 5로 근사한다."""
    return (((a.nx - b.nx) ** 2 + (a.ny - b.ny) ** 2) ** 0.5) * GRID_KM


def load_climatology(db: Session, region_id: int) -> ClimatologySource:
    """지역 평년치. 없으면 격자상 최근접 보유 지역으로 대체한다.

    대체 후보도 없거나 격자 매핑이 없으면 빈 결과(결측) — 조용히 값을 만들어내지 않는다.
    """
    own = list(
        db.query(WeatherClimatology).filter(WeatherClimatology.region_id == region_id)
    )
    if own:
        return ClimatologySource(by_month={c.month: c for c in own})

    my_grid = db.query(RegionGrid).filter(RegionGrid.region_id == region_id).first()
    if my_grid is None:
        return ClimatologySource(by_month={})

    # 평년치 보유 지역 + 격자를 한 번에 가져와 메모리에서 최근접을 찾는다(지역당 재조회 방지).
    candidates = (
        db.query(RegionGrid, Region.name)
        .join(Region, Region.id == RegionGrid.region_id)
        .filter(
            RegionGrid.region_id.in_(
                db.query(WeatherClimatology.region_id).distinct()
            )
        )
        .all()
    )
    if not candidates:
        return ClimatologySource(by_month={})

    # 동거리 후보가 있으면 region_id 작은 쪽 — 결정론 보장(같은 입력 → 같은 출력).
    best_grid, best_name = min(
        candidates, key=lambda c: (_grid_distance_km(my_grid, c[0]), c[0].region_id)
    )
    rows = list(
        db.query(WeatherClimatology).filter(
            WeatherClimatology.region_id == best_grid.region_id
        )
    )
    if not rows:
        return ClimatologySource(by_month={})

    return ClimatologySource(
        by_month={c.month: c for c in rows},
        substituted_from=best_name,
        distance_km=round(_grid_distance_km(my_grid, best_grid), 1),
    )


def substitution_limitation(source: ClimatologySource) -> str | None:
    """대체 사실을 알리는 한계 문구. 대체가 아니면 None."""
    if not source.is_substituted:
        return None
    return (
        f"이 지역 평년치가 없어 가장 가까운 {source.substituted_from}"
        f"(약 {source.distance_km:.0f}km) 평년치로 대체했습니다 — 실제와 차이가 있을 수 있습니다."
    )
