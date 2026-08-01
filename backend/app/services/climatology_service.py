"""평년치 조회 + 인접 지역 대체 (DB.md §3.11, §8.5 결측 대체).

왜 대체가 필요한가: 평년치가 256개 시/군 중 116개만 적재돼 있다(농업기상 관측지점이 있는
지역만 실측이 있다). 나머지 140개 지역은 장기 탭이 12개월 전부 "데이터 부족"으로 나와
화면이 아무 정보도 주지 못한다(예: 부천시 원미구, 고창군).

대체 방식: `region_grid`의 기상청 격자좌표(5km 격자) 거리로 가까운 평년치 보유 지역
KNN_K곳을 골라 **거리역수 가중평균**한다. 시/도 평균보다 지리적으로 정확하고(실측: 시/도
평균은 최근접 1개보다도 3.47% 나쁘다), 격자 단위라 거리에 실제 의미가 있다.
최근접 1개 복사에서 가중평균으로 바꾼 근거는 KNN_K 상수 주석 참고.

**대체는 반드시 표기한다** — 어느 지역 값을 빌렸는지, 몇 km 떨어졌는지 UI에 병기한다.
근사를 확정값처럼 보이게 하지 않는다(§18-4). 대체 없이 "데이터 없음"으로 두는 것보다
정보 가치가 크지만, 빌린 값임을 숨기면 오히려 더 나쁘다.
"""

from dataclasses import dataclass, field, replace
from decimal import Decimal

from sqlalchemy.orm import Session

from app.infra.public_api.kma_grid import grid_to_latlon
from app.models import District, Region, RegionGrid, WeatherClimatology
from app.services.sunlight_calculation import SunlightCalculation, SunlightResult

GRID_KM = 5.0  # 기상청 단기예보 격자 간격

# AWS 관측망으로 만든 평년치의 source 접두어(`scripts/load_aws_climatology.py`).
# 이 행들은 구역 자기 행이지만 주변 지점(≤10km, 최대 5곳)을 섞은 값이라 실측이 아니다.
AWS_SOURCE_PREFIX = "aws_mean_"

# 일조시간을 적합도 채점에 쓰기 위한 최소 신뢰도. 실측 검증치가 이 기준을 넘는 경로만
# 통과한다(실측 0.95, 일사량 환산 0.90 / 기온 추정 0.50은 탈락) — §18-4.
SUNLIGHT_MIN_CONFIDENCE = 0.90

# 대체 시 섞을 도너 수. 임의값이 아니라 측정으로 고른 값이다 —
# AWS 평년치 적재로 보유 지역이 116→255개가 되면서 도너가 촘촘해졌고, 그래서 최적 k가
# 10에서 3으로 내려왔다. leave-one-out 정규화 MAE(255구역, 아래 고도 필터 포함):
#     k=10 0.0901  /  k=5 0.0862  /  k=3 0.0846
# 근거 전체: docs/ml/climatology_knn_validation.json, 재현: scripts/validate_climatology_knn.py
KNN_K = 3

# 고도가 이보다 벌어진 도너는 뺀다. 기온은 고도에 직접 지배되기 때문이다(환경감률
# 약 0.65℃/100m) — 수평거리만 보면 한라산 지점과 해안 지점이 같은 후보에 든다.
# 100m 근거는 두 갈래다: (1) 지점쌍 실측에서 0~100m 구간 MAE(0.98~1.07℃)가 지점 고유
# 잡음과 구분되지 않는다. (2) leave-one-out에서 k=3 기준 무필터 대비 temp_avg MAE가
# 0.4924 → 0.4667로 5.2% 좋아진다. `load_aws_climatology.ALTITUDE_TOLERANCE_M`과 같은 값이다.
#
# **트레이드오프(숨기지 않는다)**: 필터는 기온을 좋게 하지만 일사량은 약간 나쁘게 한다
# (solar_radiation MAE 0.6734 → 0.6822, 1.3%). 고도가 일사량을 기온만큼 직접 지배하지
# 않기 때문이다. 4개 필드 총합으로도 무필터(0.0842)와 0.5% 차이라 사실상 동률인데,
# **고도가 물리적으로 지배하는 지표를 기준으로 정했다** — 이 프로젝트가 좁히려는 괴리가
# 기온이고(문제정의서 A씨 실패 원인이 야간 저온), 총합은 필드 간 오차 여유에 휘둘린다.
# 지표별로 다른 설정을 두는 건 이 차이가 측정으로 문제가 될 때 하면 된다.
#
# 고도를 수평거리로 환산해 가중에 섞는 "페널티" 방식도 재봤고 총합이 0.5~1% 나았지만,
# 그 정도 차이는 데이터를 다시 적재할 때마다 뒤집혔다(재실행 간 순위가 바뀐다).
# 재실행에 걸쳐 안정적인 신호는 "100m 필터가 temp_avg를 개선한다" 하나뿐이라 거기서
# 멈췄고, 필터를 택한 건 `load_aws_climatology`가 이미 쓰는 방식이어서다 — 같은 개념을
# 두 가지로 두지 않는다.
KNN_ALTITUDE_TOLERANCE_M = 100.0

# 필터 후 도너가 이 수 밑으로 떨어지면 필터를 포기한다. 근사가 없는 것보다는 낫다 —
# 고립된 고지대 구역이 통째로 "데이터 없음"이 되는 걸 막는다.
MIN_DONORS_AFTER_ALTITUDE_FILTER = 3

# 환경감률(℃/100m). 표준대기 기온감률로 널리 쓰이는 값이며, 우리 지점쌍 실측과도 맞는다
# (고도차 200~500m 구간 MAE 2.29℃ ≈ 350m × 0.65).
LAPSE_RATE_C_PER_100M = 0.65

# 감률 보정을 적용할 필드. 기온만이다 — 강수·일사는 고도와 이렇게 단순한 관계가 아니라
# 같은 식으로 보정하면 근거 없는 값을 만들어내게 된다(§18-4).
LAPSE_FIELDS = ("temp_avg_normal", "temp_night_min_normal")

# 이보다 작은 고도차는 보정하지 않는다. SRTM 표고의 검증 오차가 MAE 8.8m라 그 언저리를
# 보정하면 잡음을 증폭할 뿐이고, 20m는 0.13℃로 표기할 의미도 없다.
MIN_LAPSE_DELTA_M = 20.0

# 거리역수 가중의 0 나눗셈 방지. 같은 격자칸(거리 0) 도너가 있으면 사실상 그 도너가 전부를
# 가져간다 — 같은 칸이면 그게 맞는 동작이다.
MIN_DISTANCE_KM = 0.001

# 대체 대상 수치 필드. temp_night_min_normal·sunlight_normal은 2026-07-30 현재 DB 전 행이
# NULL이지만(적재 소스에 없음) 나중에 채워질 수 있어 코드는 5개를 모두 다룬다.
NORMAL_FIELDS = (
    "temp_avg_normal",
    "temp_night_min_normal",
    "rainfall_normal",
    "sunlight_normal",
    "solar_radiation_normal",
)

# 대체 시 함께 섞어야 하는 부가 필드. 채점 지표가 아니라 감률 보정의 기준선이라
# NORMAL_FIELDS(결측 보충·한계 표기 대상)와 분리한다. 섞을 때는 값과 같은 가중을 써야
# 기준선이 그 합성값을 실제로 대표한다.
BLENDED_FIELDS = (*NORMAL_FIELDS, "reference_altitude_m")


def _as_float(value: Decimal | None) -> float | None:
    """Numeric 컬럼 → float. 0.0을 결측으로 잘못 보지 않도록 `is None`으로만 판정한다.

    (이전 코드는 `if clim.temp_avg_normal else None`이라 평년 기온 0.0℃인 1월을 결측으로
    떨어뜨렸다 — 강원 산간에서 실제로 발생 가능한 값이다.)
    """
    return None if value is None else float(value)


@dataclass(frozen=True)
class MonthlyNormals:
    """도너 여러 곳을 가중평균해 합성한 월별 평년치.

    `WeatherClimatology`(ORM)와 **같은 속성 이름**을 갖는 비영속 값 객체다. 합성값을 ORM
    인스턴스로 조립해 세션에 붙이면 안 되므로(존재하지 않는 행이 DB에 새는 것을 막는다)
    같은 모양의 별도 타입을 쓴다.

    타입이 `Decimal | None`인 것은 호출부(`suitability_service.gather_indicator_values`)가
    ORM 값을 그대로 통과시키기 때문이다 — float로 바꾸면 하류 산술·직렬화 거동이 달라진다.
    """

    temp_avg_normal: Decimal | None = None
    temp_night_min_normal: Decimal | None = None
    rainfall_normal: Decimal | None = None
    sunlight_normal: Decimal | None = None
    solar_radiation_normal: Decimal | None = None
    reference_altitude_m: int | None = None
    """이 값이 대표하는 고도(m) — 감률 보정 기준선. ORM과 같은 이름·의미다."""


# 자기 지역 평년치는 ORM 행 그대로, 대체는 합성 값 객체다. 읽는 쪽은 둘을 구분하지 않고
# 같은 5개 속성만 본다(소비처 전수: climatology_service 일조 환산, suitability_service
# :313·:462 → gather_indicator_values).
ClimatologyMonth = WeatherClimatology | MonthlyNormals


@dataclass(frozen=True)
class ClimatologySource:
    """평년치와 그 출처. substituted_from이 있으면 다른 지역 값을 빌린 것이다."""

    by_month: dict[int, ClimatologyMonth]
    # 일조시간(실측/계산). 없으면 None이 아니라 **빈 dict**다 — None을 허용하면 호출부가
    # `month in clim_source.sunlight_by_month`처럼 순회할 때 TypeError로 죽는다(§18-5).
    # 비어 있음을 한 곳에서 dict로 통일해 호출부마다 None 가드를 두지 않는다.
    sunlight_by_month: dict[int, SunlightResult] = field(default_factory=dict)
    # 하위호환으로 유지한다 — 1순위(가장 가까운) 도너의 이름·거리.
    substituted_from: str | None = None
    distance_km: float | None = None
    # 실제로 섞인 도너 전체 (지역명, 거리km). 거리 오름차순.
    # frozen dataclass라 새 필드에는 기본값이 필요하다.
    donors: tuple[tuple[str, float], ...] = ()
    # 이 구역 행이 어느 관측망에서 왔는지(weather_climatology.source). 구역 자기 행이라도
    # AWS 적재분은 **그 구역에서 잰 값이 아니라 주변 지점을 섞은 값**이라 표기가 필요하다.
    source: str | None = None
    # 자기 행에 없어서 다른 지역에서 보충한 필드 이름들(예: solar_radiation_normal).
    # 한 지역 안에서도 지표마다 출처가 다를 수 있다 — AWS엔 일사량이 없기 때문이다.
    interpolated_fields: tuple[str, ...] = ()
    # 감률 보정에 쓴 고도차(밭 - 평년치 기준선, m). None이면 보정하지 않았다.
    lapse_delta_m: float | None = None
    # 밭 고도를 어느 점에서 땄는지(`district.altitude_source`). 근사 정도가 다르다.
    farm_altitude_source: str | None = None

    @property
    def is_lapse_corrected(self) -> bool:
        return self.lapse_delta_m is not None

    @property
    def is_substituted(self) -> bool:
        return self.substituted_from is not None

    @property
    def is_station_interpolated(self) -> bool:
        """구역 자기 행이지만 주변 관측지점을 섞어 만든 값인가.

        `is_substituted`(다른 구역에서 빌림)와 다르다 — 이쪽은 행이 자기 구역에 있어서
        종전 로직이 '실측'으로 취급했고, 그래서 한계 문구가 아예 뜨지 않았다(§18-4 위반).
        """
        return (self.source or "").startswith(AWS_SOURCE_PREFIX)


def _grid_distance_km(a: RegionGrid, b: RegionGrid) -> float:
    """격자 좌표 유클리드 거리(km). 5km 격자라 칸 차이 × 5로 근사한다."""
    return (((a.nx - b.nx) ** 2 + (a.ny - b.ny) ** 2) ** 0.5) * GRID_KM


def _rank_donors(
    my_grid: RegionGrid,
    candidates: list[tuple[RegionGrid, str, int | None]],
    my_altitude: int | None = None,
    k: int = KNN_K,
) -> list[tuple[RegionGrid, str, int | None]]:
    """거리 오름차순 상위 k개 도너. 고도가 동떨어진 후보는 먼저 걷어낸다.

    동거리면 `region_id` 작은 쪽 — 같은 입력이 항상 같은 도너 집합을 내야 한다(§2 결정론).
    격자가 5km 단위라 동거리 동점은 실제로 흔하다.

    고도를 모르는 쪽이 있으면 그 후보는 거리만으로 판정한다 — 없는 정보로 도너를 버리면
    그 구역이 통째로 비어버린다. 필터가 너무 많이 걷어내도 마찬가지라 포기한다.
    """
    pool = candidates
    if my_altitude is not None:
        near_altitude = [
            c
            for c in candidates
            if c[2] is None or abs(c[2] - my_altitude) <= KNN_ALTITUDE_TOLERANCE_M
        ]
        if len(near_altitude) >= MIN_DONORS_AFTER_ALTITUDE_FILTER:
            pool = near_altitude

    return sorted(
        pool, key=lambda c: (_grid_distance_km(my_grid, c[0]), c[0].region_id)
    )[:k]


def _weighted_normals(
    rows_with_weight: list[tuple[WeatherClimatology, float]],
) -> MonthlyNormals:
    """도너 행들을 거리 가중평균해 한 달치 평년치를 만든다.

    **필드별로 독립 처리한다.** 어떤 도너가 특정 필드만 결측이면 그 필드에서만 제외하고
    남은 도너의 가중치를 재정규화한다 — 도너 행 전체를 버리면 그 도너가 가진 다른 필드의
    정보까지 잃는다.

    모든 도너가 결측인 필드는 `None`이다. 값을 지어내지 않는다(§18-4).
    """
    values: dict[str, Decimal | int | None] = {}
    for field_name in BLENDED_FIELDS:
        # `is None`으로만 판정한다 — 0.0을 결측으로 떨어뜨리면 강원 산간 1월 평년기온
        # 0.0℃가 사라진다(_as_float 주석의 기존 버그).
        pairs = [
            (float(getattr(row, field_name)), weight)
            for row, weight in rows_with_weight
            if getattr(row, field_name) is not None
        ]
        total_weight = sum(w for _, w in pairs)
        if not pairs or total_weight <= 0:
            values[field_name] = None
            continue
        mean = sum(v * w for v, w in pairs) / total_weight
        if field_name == "reference_altitude_m":
            values[field_name] = round(mean)  # ORM과 같은 int
            continue
        # Decimal로 되돌린다(호출부가 ORM Numeric과 같은 타입을 기대). 4자리면 기온 0.0001℃
        # 해상도라 충분하고, float 이진오차가 그대로 노출되는 것을 막는다.
        values[field_name] = Decimal(str(round(mean, 4)))
    return MonthlyNormals(**values)


def _missing_fields(by_month: dict[int, ClimatologyMonth]) -> list[str]:
    """자기 행이 한 달도 채우지 못한 필드. 이것만 도너로 보충한다.

    한 달이라도 값이 있으면 보충하지 않는다 — 같은 지역 안에서 어떤 달은 실측, 어떤 달은
    남의 값이 섞이면 월별 비교(장기 탭 히트맵)가 뒤틀린다.
    """
    return [
        name
        for name in NORMAL_FIELDS
        if all(getattr(row, name, None) is None for row in by_month.values())
    ]


def _fill_missing_fields(
    db: Session,
    my_grid: RegionGrid | None,
    by_month: dict[int, ClimatologyMonth],
    fields: list[str],
    my_altitude: int | None = None,
) -> tuple[dict[int, MonthlyNormals], list[str]]:
    """자기 행에 없는 필드를 **그 필드를 가진 지역들**에서만 KNN으로 보충한다.

    도너 풀을 필드별로 잡는 것이 핵심이다. 종전엔 "행이 있는 모든 지역"을 후보로 삼았는데,
    AWS 적재로 행은 있지만 일사량이 없는 지역이 139개 생기면서 그 방식이 깨졌다 — 가까운
    10곳이 전부 일사량 NULL이면 보충이 통째로 실패한다.

    Returns:
        (필드가 채워진 월별 평년치, 실제로 보충된 필드 이름들)
    """
    merged = {
        month: MonthlyNormals(
            **{name: getattr(row, name, None) for name in BLENDED_FIELDS}
        )
        for month, row in by_month.items()
    }
    if my_grid is None or not fields:
        return merged, []

    filled: list[str] = []
    for name in fields:
        column = getattr(WeatherClimatology, name)
        holder_ids = {
            row[0]
            for row in db.query(WeatherClimatology.region_id)
            .filter(column.isnot(None))
            .distinct()
        }
        holder_ids.discard(my_grid.region_id)
        if not holder_ids:
            continue

        candidates = (
            db.query(RegionGrid, Region.name, Region.altitude_m)
            .join(Region, Region.id == RegionGrid.region_id)
            .filter(RegionGrid.region_id.in_(holder_ids))
            .all()
        )
        if not candidates:
            continue

        ranked = _rank_donors(my_grid, candidates, my_altitude)
        weight_by_region = {
            grid.region_id: 1.0 / max(_grid_distance_km(my_grid, grid), MIN_DISTANCE_KM)
            for grid, _, _ in ranked
        }
        donor_rows = db.query(WeatherClimatology).filter(
            WeatherClimatology.region_id.in_(weight_by_region),
            column.isnot(None),
        )

        by_month_pairs: dict[int, list[tuple[float, float]]] = {}
        for row in donor_rows:
            weight = weight_by_region.get(row.region_id)
            if weight is None:
                continue
            by_month_pairs.setdefault(row.month, []).append(
                (float(getattr(row, name)), weight)
            )

        wrote = False
        for month, pairs in by_month_pairs.items():
            if month not in merged:
                continue
            total = sum(w for _, w in pairs)
            if total <= 0:
                continue
            mean = sum(v * w for v, w in pairs) / total
            merged[month] = replace(
                merged[month], **{name: Decimal(str(round(mean, 4)))}
            )
            wrote = True
        if wrote:
            filled.append(name)

    return merged, filled


def _apply_lapse_rate(
    by_month: dict[int, ClimatologyMonth], farm_altitude: int
) -> tuple[dict[int, ClimatologyMonth], float | None]:
    """밭 고도와 평년치 기준 고도의 차이만큼 기온을 감률 보정한다. (보정된 값, 고도차 m).

    평년치는 시군구 단위인데 밭 위치는 읍면동까지 안다 — 토양 때문에 이미 그 해상도로
    받고 있어서다. 서귀포 평년치를 해안 기준으로 잘 만들어도 밭이 중산간 400m면 2.6℃
    틀리는데, 그 격차를 여기서 좁힌다.

    기준선은 `reference_altitude_m`(그 값이 실제로 대표하는 고도)이지 구역 대표 고도가
    아니다 — 관측지점은 대표점보다 높은 경향이 있어 최대 370m(남원시) 벌어지고, 그걸
    기준으로 잡으면 보정이 2.4℃ 틀어진다.

    기준선을 모르는 달은 건드리지 않는다. 보정할 수 없는 값을 보정한 척하지 않는다(§18-4).
    """
    adjusted: dict[int, ClimatologyMonth] = {}
    deltas: list[float] = []
    for month, row in by_month.items():
        reference = getattr(row, "reference_altitude_m", None)
        delta = None if reference is None else farm_altitude - float(reference)
        if delta is None or abs(delta) < MIN_LAPSE_DELTA_M:
            adjusted[month] = row
            continue

        shift = Decimal(str(round(-LAPSE_RATE_C_PER_100M * delta / 100, 4)))
        values = {name: getattr(row, name, None) for name in BLENDED_FIELDS}
        for name in LAPSE_FIELDS:
            if values[name] is not None:
                values[name] = Decimal(str(values[name])) + shift
        adjusted[month] = MonthlyNormals(**values)
        deltas.append(delta)

    # 달마다 기준선이 같으므로 대표값 하나면 충분하다(다르면 평균이 정직한 요약이다).
    return adjusted, (sum(deltas) / len(deltas) if deltas else None)


def _lapse_for_farm(
    db: Session, by_month: dict[int, ClimatologyMonth], bjd_code: str | None
) -> tuple[dict[int, ClimatologyMonth], float | None, str | None]:
    """밭 읍면동 고도를 찾아 감률 보정을 적용한다. (보정된 값, 고도차, 고도 출처).

    밭이 없거나(구역 단위 조회) 그 읍면동 고도를 모르면 아무것도 하지 않는다.
    """
    if bjd_code is None:
        return by_month, None, None
    district = db.query(District).filter(District.bjd_code == bjd_code).first()
    if district is None or district.altitude_m is None:
        return by_month, None, None
    adjusted, delta = _apply_lapse_rate(by_month, district.altitude_m)
    return adjusted, delta, district.altitude_source


def load_climatology(
    db: Session, region_id: int, bjd_code: str | None = None
) -> ClimatologySource:
    """지역 평년치. 없으면 격자상 가까운 지역들의 거리 가중평균으로 대체한다.

    `bjd_code`(밭의 읍면동)를 주면 그 고도로 기온을 감률 보정한다. 안 주면 종전과 같다 —
    구역 단위로 평년치를 보는 호출부(지역 개요 등)는 밭이 없어서 보정할 기준이 없다.

    대체 후보도 없거나 격자 매핑이 없으면 빈 결과(결측) — 조용히 값을 만들어내지 않는다.
    """
    my_altitude = (
        db.query(Region.altitude_m).filter(Region.id == region_id).scalar()
    )
    own = list(
        db.query(WeatherClimatology).filter(WeatherClimatology.region_id == region_id)
    )
    if own:
        by_month: dict[int, ClimatologyMonth] = {c.month: c for c in own}
        # 관측망마다 가진 지표가 다르다 — AWS엔 일사량·일조가 없다. 그래서 "자기 행이 있으면
        # 통째로 실측"이라는 종전 전제가 깨졌다. 행 단위가 아니라 **필드 단위로** 본다.
        missing = _missing_fields(by_month)
        if missing:
            my_grid = db.query(RegionGrid).filter(RegionGrid.region_id == region_id).first()
            filled_by_month, filled = _fill_missing_fields(
                db, my_grid, by_month, missing, my_altitude
            )
            if filled:
                by_month = dict(filled_by_month)
        else:
            filled = []

        by_month, lapse_delta_m, farm_altitude_source = _lapse_for_farm(
            db, by_month, bjd_code
        )
        clim_source = ClimatologySource(
            by_month=by_month,
            # 행이 자기 구역에 있다고 다 실측은 아니다 — AWS 적재분은 주변 지점을 섞은 값이라
            # 화면에 그 사실을 알려야 한다(§18-4). 소스는 행마다 같으므로 하나만 본다.
            source=own[0].source,
            interpolated_fields=tuple(filled),
            lapse_delta_m=lapse_delta_m,
            farm_altitude_source=farm_altitude_source,
        )
        clim_source = _add_sunlight_to_climatology(db, clim_source, region_id)
        return clim_source

    my_grid = db.query(RegionGrid).filter(RegionGrid.region_id == region_id).first()
    if my_grid is None:
        return ClimatologySource(by_month={})

    # 평년치 보유 지역 + 격자를 한 번에 가져와 메모리에서 이웃을 찾는다(지역당 재조회 방지).
    candidates = (
        db.query(RegionGrid, Region.name, Region.altitude_m)
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

    ranked = _rank_donors(my_grid, candidates, my_altitude)

    rows = list(
        db.query(WeatherClimatology).filter(
            WeatherClimatology.region_id.in_([grid.region_id for grid, _, _ in ranked])
        )
    )
    if not rows:
        return ClimatologySource(by_month={})

    # 실제로 행이 있는 도너만 남긴다 — 이름 목록과 섞인 값이 어긋나면 한계 문구가 거짓이 된다.
    present = {row.region_id for row in rows}
    donors = [
        (grid, name, _grid_distance_km(my_grid, grid))
        for grid, name, _ in ranked
        if grid.region_id in present
    ]
    weight_by_region = {
        grid.region_id: 1.0 / max(distance, MIN_DISTANCE_KM)
        for grid, _, distance in donors
    }

    rows_by_month: dict[int, list[tuple[WeatherClimatology, float]]] = {}
    for row in rows:
        weight = weight_by_region.get(row.region_id)
        if weight is None:
            continue
        rows_by_month.setdefault(row.month, []).append((row, weight))

    by_month: dict[int, ClimatologyMonth] = {
        month: _weighted_normals(entries) for month, entries in rows_by_month.items()
    }

    by_month, lapse_delta_m, farm_altitude_source = _lapse_for_farm(
        db, by_month, bjd_code
    )
    clim_source = ClimatologySource(
        by_month=by_month,
        substituted_from=donors[0][1],
        distance_km=round(donors[0][2], 1),
        donors=tuple((name, round(distance, 1)) for _, name, distance in donors),
        lapse_delta_m=lapse_delta_m,
        farm_altitude_source=farm_altitude_source,
    )

    # 일조 환산은 **대체받는 지역 자신의** 위도로 한다. 가조시간은 값이 아니라 위치의 함수라
    # 도너 위도를 쓰면 틀린다. (도너가 1개였을 땐 도너 위도를 썼는데, k개를 섞는 지금은
    # 애초에 "그 도너"가 없다.)
    clim_source = _add_sunlight_to_climatology(db, clim_source, region_id)

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
        donors=clim_source.donors,
        source=clim_source.source,  # 빠뜨리면 한계 문구 판정이 조용히 실측으로 되돌아간다
        interpolated_fields=clim_source.interpolated_fields,
        lapse_delta_m=clim_source.lapse_delta_m,
        farm_altitude_source=clim_source.farm_altitude_source,
    )


# 한계 문구에 이름을 적을 도너 수. 10곳을 다 나열하면 200자가 넘어 화면에서 읽히지 않는다
# (실측: "고양시덕양구·양주시·시흥시·김포시·파주시·광주시·옹진군·포천시·용인시처인구·양평군").
# 가중치가 거리역수라 가까운 몇 곳이 가장 크게 기여하므로 그쪽을 이름으로 밝히고,
# 나머지는 **개수와 거리 범위**로 밝힌다 — 전체 목록은 `ClimatologySource.donors`에 있어
# 프론트가 펼쳐 보여줄 수 있다. 대체 사실 자체는 숨기지 않는다(§18-4).
LIMITATION_NAMED_DONORS = 3


# `district.altitude_source` → 유저에게 보여줄 근거 표현. 값마다 근사 정도가 다르므로
# 뭉뚱그리지 않는다(§18-4). 값의 생성 규칙은 `scripts/gen_altitude_seed.py`.
# 모르는 값이 오면 가장 보수적인 문구로 폴백한다 — 시드가 앞서 나가도 거짓말은 안 하게.
# 문구가 "{basis}의 고도라"로 이어지므로 값 안에 "의"를 넣지 않는다(조사 겹침).
FARM_ALTITUDE_BASIS = {
    "ri_polygon": "리(里) 경계 중심점",
    "emd_polygon": "동 경계 중심점",
    "emd_point": "소속 읍·면·동 대표 지점",
    "region_point": "시·군 대표 지점",
}


def lapse_limitation(source: ClimatologySource) -> str | None:
    """감률 보정 사실을 알리는 한계 문구. 보정하지 않았으면 None.

    보정 자체가 근사다(환경감률 0.65℃/100m는 지형·계절·주야를 구분하지 않는다). 게다가
    밭 고도도 밭의 실측이 아니라 읍·면·동 대표점이다 — 숨기면 안 된다(§18-4).
    """
    if source.lapse_delta_m is None:
        return None

    delta = source.lapse_delta_m
    shift = -LAPSE_RATE_C_PER_100M * delta / 100
    direction = "높아" if delta > 0 else "낮아"
    basis = FARM_ALTITUDE_BASIS.get(source.farm_altitude_source, "상위 행정구역 대표 지점")
    return (
        f"밭 위치가 평년치 관측 기준보다 약 {abs(delta):.0f}m {direction} "
        f"기온을 {shift:+.1f}℃ 보정했습니다(감률 0.65℃/100m). "
        f"밭의 실측 고도가 아니라 {basis}의 고도라 실제와 차이가 있을 수 있습니다."
    )


def substitution_limitation(source: ClimatologySource) -> str | None:
    """대체 사실을 알리는 한계 문구. 대체가 아니면 None.

    한 곳에서 빌린 것처럼 적지 않는다 — 실제보다 출처가 좁아 보여서 근사의 성격을
    오히려 감추게 된다. 섞인 곳의 수와 거리 범위를 반드시 포함한다(§18-4).
    """
    if source.is_station_interpolated:
        # 다른 구역에서 빌린 게 아니라 **이 구역 주변 관측지점**을 섞은 값이다. 종전엔
        # 자기 구역 행이라는 이유로 아무 문구도 뜨지 않아 실측처럼 보였다(§18-4).
        return (
            "이 지역에 기상 관측지점이 없어 주변 관측지점(10km 이내 최대 5곳)의 값을 "
            "거리 가중으로 섞었습니다 — 실측이 아니라 추정치입니다."
        )

    if not source.is_substituted:
        return None

    # 도너가 1곳이거나 목록이 비어 있으면(하위호환 경로) 종전 단수 문구.
    if len(source.donors) <= 1:
        return (
            f"이 지역 평년치가 없어 가장 가까운 {source.substituted_from}"
            f"(약 {source.distance_km:.0f}km) 평년치로 대체했습니다 — 실제와 차이가 있을 수 있습니다."
        )

    named = [name for name, _ in source.donors[:LIMITATION_NAMED_DONORS]]
    listed = "·".join(named)
    remaining = len(source.donors) - len(named)
    if remaining > 0:
        listed = f"{listed} 외 {remaining}곳"
    nearest = source.donors[0][1]
    farthest = source.donors[-1][1]
    return (
        f"이 지역 평년치가 없어 가까운 {len(source.donors)}곳({listed}, 약 {nearest:.0f}~{farthest:.0f}km)의"
        f" 평년치를 거리 가중 평균했습니다 — 실제와 차이가 있을 수 있습니다."
    )
