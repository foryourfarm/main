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

from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy.orm import Session

from app.infra.public_api.kma_grid import grid_to_latlon
from app.models import Region, RegionGrid, WeatherClimatology
from app.services.sunlight_calculation import SunlightCalculation, SunlightResult

GRID_KM = 5.0  # 기상청 단기예보 격자 간격

# 일조시간을 적합도 채점에 쓰기 위한 최소 신뢰도. 실측 검증치가 이 기준을 넘는 경로만
# 통과한다(실측 0.95, 일사량 환산 0.90 / 기온 추정 0.50은 탈락) — §18-4.
SUNLIGHT_MIN_CONFIDENCE = 0.90


def _as_float(value: Decimal | None) -> float | None:
    """Numeric 컬럼 → float. 0.0을 결측으로 잘못 보지 않도록 `is None`으로만 판정한다.

    (이전 코드는 `if clim.temp_avg_normal else None`이라 평년 기온 0.0℃인 1월을 결측으로
    떨어뜨렸다 — 강원 산간에서 실제로 발생 가능한 값이다.)
    """
    return None if value is None else float(value)


@dataclass(frozen=True)
class ClimatologySource:
    """평년치와 그 출처. substituted_from이 있으면 다른 지역 값을 빌린 것이다."""

    by_month: dict[int, WeatherClimatology]
    # 일조시간(실측/계산). 없으면 None이 아니라 **빈 dict**다 — None을 허용하면 호출부가
    # `month in clim_source.sunlight_by_month`처럼 순회할 때 TypeError로 죽는다(§18-5).
    # 비어 있음을 한 곳에서 dict로 통일해 호출부마다 None 가드를 두지 않는다.
    sunlight_by_month: dict[int, SunlightResult] = field(default_factory=dict)
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
        clim_source = ClimatologySource(by_month={c.month: c for c in own})
        clim_source = _add_sunlight_to_climatology(db, clim_source, region_id)
        return clim_source

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

    clim_source = ClimatologySource(
        by_month={c.month: c for c in rows},
        substituted_from=best_name,
        distance_km=round(_grid_distance_km(my_grid, best_grid), 1),
    )

    # 일조시간 계산 추가
    clim_source = _add_sunlight_to_climatology(db, clim_source, best_grid.region_id)

    return clim_source


def _add_sunlight_to_climatology(
    db: Session, clim_source: ClimatologySource, region_id: int
) -> ClimatologySource:
    """일조시간 산출 추가 (실측 → 일사량 환산). 정확도 게이트를 통과한 값만 담는다.

    게이트가 SUNLIGHT_MIN_CONFIDENCE(0.90)인 이유: 일조시간을 적합도 채점에 쓰려면 추정
    오차가 작아야 한다. 실측 검증 결과 일사량 환산은 R²=0.904/MAE 0.845h로 이 기준을
    만족하지만, 기온 일교차 추정은 R²=0.496/MAE 2.219h로 못 미친다 — 후자는 산출은 되지만
    게이트에서 걸러진다(§18-4 부정확한 추정치를 확정값처럼 쓰지 않는다).
    근거·계수: `docs/seed/sunlight_calibration.json`.

    Args:
        db: DB 세션
        clim_source: 기존 평년치 소스
        region_id: 지역 ID (평년치 보유 지역)

    Returns:
        게이트 통과 일조시간만 담은 ClimatologySource(없으면 빈 dict — None 아님)
    """
    sunlight_by_month: dict[int, SunlightResult] = {}

    # 위도는 격자좌표에서 되돌린다 — region_grid에 위경도 컬럼이 없다. 격자 중심이라
    # 약 ±0.023도 오차가 있지만 가조시간 계산에는 충분하다(kma_grid.grid_to_latlon 참고).
    region_grid = db.query(RegionGrid).filter(RegionGrid.region_id == region_id).first()
    if region_grid is None:
        # 격자 정보가 없으면 위도를 모른다 → 계산 불가. 실측값만이라도 담아 반환한다.
        # (예전엔 원본을 그대로 반환해 sunlight_by_month가 None이 됐고, 호출부가 그걸
        #  순회하다 TypeError로 죽었다 — §18-5.)
        latitude = None
    else:
        try:
            latitude, _ = grid_to_latlon(region_grid.nx, region_grid.ny)
        except ValueError:
            # 격자값이 손상된 지역(범위 밖)도 산출을 죽이지 않는다(§12 경계 방어).
            latitude = None

    for month in range(1, 13):
        clim = clim_source.by_month.get(month)
        if clim is None:
            continue

        # 실측 일조는 위도가 필요 없다 — 격자 매핑이 없는 지역도 이 경로는 살린다.
        if clim.sunlight_normal is not None:
            sunlight_by_month[month] = SunlightCalculation.from_measurement(
                float(clim.sunlight_normal)
            )
            continue

        if latitude is None:
            continue  # 위도를 모르면 환산 불가(가조시간·지구외일사량 계산에 필수)

        result = SunlightCalculation.calculate_optimal(
            latitude=latitude,
            month=month,
            solar_radiation=_as_float(clim.solar_radiation_normal),
            tmax=_as_float(clim.temp_avg_normal),
            tmin=_as_float(clim.temp_night_min_normal),
        )
        if result is not None and result.confidence >= SUNLIGHT_MIN_CONFIDENCE:
            sunlight_by_month[month] = result

    # 새 ClimatologySource 반환 (불변이므로 전체 재생성)
    return ClimatologySource(
        by_month=clim_source.by_month,
        sunlight_by_month=sunlight_by_month,
        substituted_from=clim_source.substituted_from,
        distance_km=clim_source.distance_km,
    )


def substitution_limitation(source: ClimatologySource) -> str | None:
    """대체 사실을 알리는 한계 문구. 대체가 아니면 None."""
    if not source.is_substituted:
        return None
    return (
        f"이 지역 평년치가 없어 가장 가까운 {source.substituted_from}"
        f"(약 {source.distance_km:.0f}km) 평년치로 대체했습니다 — 실제와 차이가 있을 수 있습니다."
    )
