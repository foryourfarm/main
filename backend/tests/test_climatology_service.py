"""평년치 인접 지역 대체 검증. 순수 계산부(거리)는 DB 없이, 나머지는 실 DB로.

부천시 원미구·고창군처럼 관측지점이 없는 지역이 여전히 많다(확장 후에도 140개).
격자 거리 최근접 대체가 "데이터 부족" 12칸보다 나은 유일한 방법이라 이 경로가 핵심이다.
"""
import unittest
from unittest.mock import MagicMock

from app.services.climatology_service import (
    ClimatologySource,
    _grid_distance_km,
    substitution_limitation,
)


class FakeGrid:
    def __init__(self, nx: int, ny: int, region_id: int = 0):
        self.nx = nx
        self.ny = ny
        self.region_id = region_id


class TestGridDistance(unittest.TestCase):
    def test_same_cell_is_zero(self):
        self.assertEqual(_grid_distance_km(FakeGrid(60, 127), FakeGrid(60, 127)), 0.0)

    def test_adjacent_cell_is_one_grid_unit(self):
        self.assertEqual(_grid_distance_km(FakeGrid(60, 127), FakeGrid(61, 127)), 5.0)

    def test_diagonal_uses_euclidean_not_manhattan(self):
        # 실측: 부천 원미구(격자 대략) vs 인접 지역 — 대각선은 5km*sqrt(2) 근사
        dist = _grid_distance_km(FakeGrid(0, 0), FakeGrid(1, 1))
        self.assertAlmostEqual(dist, 5.0 * 2**0.5, places=2)


class TestSubstitutionLimitation(unittest.TestCase):
    def test_no_substitution_returns_none(self):
        source = ClimatologySource(by_month={})
        self.assertIsNone(substitution_limitation(source))

    def test_substitution_names_source_and_distance(self):
        source = ClimatologySource(by_month={}, substituted_from="순천시", distance_km=12.3)
        msg = substitution_limitation(source)
        self.assertIn("순천시", msg)
        self.assertIn("12", msg)  # 거리 근사 표기

    def test_is_substituted_flag(self):
        self.assertFalse(ClimatologySource(by_month={}).is_substituted)
        self.assertTrue(
            ClimatologySource(by_month={}, substituted_from="x", distance_km=1.0).is_substituted
        )


class TestStationInterpolatedLimitation(unittest.TestCase):
    """AWS 적재분은 구역 자기 행이지만 주변 지점을 섞은 값이라 실측이 아니다(§18-4).

    종전엔 `is_substituted`만 봤기 때문에 이 행들에 아무 문구도 뜨지 않았다.
    """

    def test_농업기상_실측은_문구가_없다(self):
        source = ClimatologySource(by_month={}, source="obs_mean_2021_2025")
        self.assertFalse(source.is_station_interpolated)
        self.assertIsNone(substitution_limitation(source))

    def test_AWS_보간분은_추정치임을_밝힌다(self):
        source = ClimatologySource(by_month={}, source="aws_mean_2021_2025")

        self.assertTrue(source.is_station_interpolated)
        msg = substitution_limitation(source)
        self.assertIsNotNone(msg)
        self.assertIn("주변 관측지점", msg)
        self.assertIn("추정치", msg)

    def test_source가_없으면_종전대로_판정한다(self):
        """소스 컬럼이 비어 있는 기존 행(하위호환)이 오탐되면 안 된다."""
        self.assertFalse(ClimatologySource(by_month={}).is_station_interpolated)
        self.assertIsNone(substitution_limitation(ClimatologySource(by_month={})))


if __name__ == "__main__":
    unittest.main()
