"""관측지점 ↔ 구역 매핑 검증 (MappingReport.md).

두 가지를 본다:
1. **커밋된 시드 CSV**가 실제로 쓸 만한 상태인지 — 커버리지·중복·좌표 범위.
   시드는 API 조회로 만들지만 결과를 커밋하므로, 테스트는 네트워크 없이 산출물을 검증한다.
2. **구역 → 지점 조회 서비스**가 확정된 규칙(최근접 1개, 1차 우선, 거리 표기)을 지키는지.

이 테스트가 지키는 약속: 행정구역 개편이나 시드 재생성으로 매핑이 깨지면 여기서 드러난다.
"""

import csv
import unittest
from dataclasses import dataclass
from pathlib import Path

from app.services.station_service import (
    AGRI,
    KMA_AWS,
    MAX_DISTANCE_KM,
    StationMatch,
    resolve_station,
)

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "docs" / "seed" / "observation_point_seed.csv"
REGION_GRID_SEED = ROOT / "docs" / "seed" / "region_grid_seed.csv"
REGION_SEED = ROOT / "docs" / "seed" / "region_seed.csv"

GRID_KM = 5.0


def _load(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class TestSeedIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _load(SEED)
        cls.regions = {int(r["id"]) for r in _load(REGION_SEED)}

    def test_both_networks_present(self):
        """한 관측망만 들어 있으면 결측 보완 구조가 성립하지 않는다."""
        networks = {r["network"] for r in self.rows}
        self.assertEqual(networks, {AGRI, KMA_AWS})

    def test_station_counts_are_plausible(self):
        """지점 수가 급감하면 시드 생성이 조용히 실패한 것이다."""
        counts = {n: sum(1 for r in self.rows if r["network"] == n) for n in (AGRI, KMA_AWS)}
        self.assertGreater(counts[AGRI], 200, "농업기상 지점이 너무 적다")  # 실측 218
        self.assertGreater(counts[KMA_AWS], 500, "AWS 지점이 너무 적다")

    def test_point_codes_are_unique(self):
        """PK 충돌 — 두 관측망 코드 체계가 겹치면 적재가 서로를 덮어쓴다."""
        codes = [r["point_code"] for r in self.rows]
        self.assertEqual(len(codes), len(set(codes)))

    def test_test_station_is_excluded(self):
        """응답에 섞여 있는 `동방로거테스트`는 실제 관측소가 아니다."""
        self.assertNotIn("동방로거테스트", {r["name"] for r in self.rows})

    def test_assigned_region_ids_exist(self):
        """존재하지 않는 region_id는 적재 시 FK 위반으로 죽는다."""
        for r in self.rows:
            if r["region_id"]:
                with self.subTest(point=r["name"]):
                    self.assertIn(int(r["region_id"]), self.regions)

    def test_all_stations_have_korean_coordinates(self):
        """두 관측망 모두 좌표 기반으로 배정한다 — 좌표가 틀리면 엉뚱한 구역 날씨를 준다.

        농업기상 좌표는 getObsrSpotList(Instl_La/Instl_Lo)에서 온다. 이 API를 쓰기 전에는
        지점명 문자열을 파싱했고 광역시·통합시에서 깨졌다(MappingReport.md §4).
        """
        for r in self.rows:
            with self.subTest(point=r["name"], network=r["network"]):
                self.assertTrue(32.0 <= float(r["lat"]) <= 39.5)
                self.assertTrue(124.0 <= float(r["lon"]) <= 132.5)

    def test_stations_have_grid_coordinates(self):
        """격자가 없으면 거리 계산이 불가능해 조회에서 빠진다."""
        with_grid = [r for r in self.rows if r["nx"] and r["ny"]]
        self.assertGreater(len(with_grid) / len(self.rows), 0.98)

    def test_every_mapped_region_can_reach_a_station(self):
        """**핵심**: 격자 매핑이 있는 모든 구역이 최근접 지점을 가져야 한다.

        구역 '안'에 지점이 있는 경우만 세면 203/256이지만, 확정 규칙(최근접 지점)을 적용하면
        전부 커버된다. 이 테스트가 깨지면 어떤 구역이 날씨를 못 받는다는 뜻이다.
        """
        grids = [(int(r["nx"]), int(r["ny"])) for r in self.rows if r["nx"] and r["ny"]]
        self.assertTrue(grids)
        worst = 0.0
        for rg in _load(REGION_GRID_SEED):
            rnx, rny = int(rg["nx"]), int(rg["ny"])
            nearest = min(
                (((rnx - nx) ** 2 + (rny - ny) ** 2) ** 0.5 * GRID_KM for nx, ny in grids)
            )
            with self.subTest(region=rg["name"]):
                self.assertLessEqual(nearest, MAX_DISTANCE_KM)
            worst = max(worst, nearest)
        self.assertLess(worst, 25.0, f"최원거리 {worst:.1f}km — 커버리지가 나빠졌다")

    def test_unassigned_stations_are_the_far_islands(self):
        """미배정 지점이 많아지면 배정 로직이 망가진 것이다(도서 몇 개만 정상)."""
        unassigned = [r for r in self.rows if not r["region_id"]]
        self.assertLess(len(unassigned), 40, f"미배정 {len(unassigned)}건 — 너무 많다")


@dataclass
class _Grid:
    region_id: int
    nx: int
    ny: int


class _FakeQuery:
    """SQLAlchemy 쿼리 흉내 — DB 없이 서비스 규칙만 검증한다."""

    def __init__(self, rows):
        self._rows = rows

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return self._rows


class _FakeDb:
    def __init__(self, grid, stations):
        self._grid, self._stations = grid, stations

    def query(self, model):
        name = getattr(model, "__name__", "")
        if name == "RegionGrid":
            return _FakeQuery([self._grid] if self._grid else [])
        return _FakeQuery(self._stations)


@dataclass
class _Station:
    point_code: str
    name: str
    network: str
    nx: int | None
    ny: int | None


class TestResolveStation(unittest.TestCase):
    GRID = _Grid(region_id=1, nx=60, ny=127)

    def _db(self, stations, grid=GRID):
        return _FakeDb(grid, stations)

    def test_prefers_agri_even_when_aws_is_closer(self):
        """1차(농업기상)에만 일사량이 있어 더 멀어도 우선한다 — 계층 우선순위."""
        stations = [
            _Station("108", "서울", KMA_AWS, 60, 127),  # 거리 0
            _Station("A1", "농업기상A", AGRI, 61, 127),  # 거리 5km
        ]
        match = resolve_station(self._db(stations), region_id=1)
        self.assertEqual(match.network, AGRI)
        self.assertAlmostEqual(match.distance_km, 5.0)
        self.assertTrue(match.has_solar_radiation)

    def test_falls_back_to_aws_when_no_agri(self):
        stations = [_Station("108", "서울", KMA_AWS, 60, 127)]
        match = resolve_station(self._db(stations), region_id=1)
        self.assertEqual(match.network, KMA_AWS)
        self.assertFalse(match.has_solar_radiation)

    def test_picks_nearest_within_a_network(self):
        """확정 규칙: 최근접 1개. 평균이 아니다."""
        stations = [
            _Station("A1", "먼곳", AGRI, 64, 127),  # 20km
            _Station("A2", "가까운곳", AGRI, 61, 127),  # 5km
            _Station("A3", "중간", AGRI, 62, 127),  # 10km
        ]
        match = resolve_station(self._db(stations), region_id=1)
        self.assertEqual(match.point_code, "A2")

    def test_tie_is_broken_deterministically(self):
        """같은 거리면 항상 같은 지점을 골라야 한다(§2 결정론)."""
        stations = [
            _Station("B", "우", AGRI, 61, 127),
            _Station("A", "좌", AGRI, 59, 127),
        ]
        first = resolve_station(self._db(stations), region_id=1)
        second = resolve_station(self._db(list(reversed(stations))), region_id=1)
        self.assertEqual(first.point_code, second.point_code)
        self.assertEqual(first.point_code, "A")

    def test_rejects_stations_beyond_max_distance(self):
        """너무 먼 지점은 그 구역 날씨가 아니다 — 아무 값이나 주는 것보다 결측이 정직하다."""
        stations = [_Station("A1", "제주", AGRI, 60, 40)]  # 435km
        self.assertIsNone(resolve_station(self._db(stations), region_id=1))

    def test_returns_none_without_region_grid(self):
        stations = [_Station("A1", "x", AGRI, 60, 127)]
        self.assertIsNone(resolve_station(self._db(stations, grid=None), region_id=1))

    def test_ignores_stations_without_grid(self):
        stations = [_Station("A1", "격자없음", AGRI, None, None)]
        self.assertIsNone(resolve_station(self._db(stations), region_id=1))


class TestLimitationNote(unittest.TestCase):
    """근사를 확정 실측처럼 보이게 하지 않는다(§18-4, §1-4)."""

    def test_inside_agri_station_needs_no_note(self):
        m = StationMatch("A1", "영월군 영월읍", AGRI, 0.0)
        self.assertIsNone(m.limitation_note())
        self.assertTrue(m.is_inside_region)

    def test_distant_station_discloses_distance(self):
        m = StationMatch("A1", "영월군 영월읍", AGRI, 15.8)
        note = m.limitation_note()
        self.assertIn("16km", note)
        self.assertIn("관측소", note)

    def test_aws_station_discloses_missing_sunlight(self):
        """2차 관측망은 일조 자료가 없다 — 그 사실을 숨기면 안 된다."""
        m = StationMatch("108", "서울", KMA_AWS, 0.0)
        self.assertIn("일조", m.limitation_note())


if __name__ == "__main__":
    unittest.main()
