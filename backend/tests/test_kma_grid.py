"""위경도 → 기상청 격자 변환 검증.

기상청이 공개한 행정구역↔격자 대응 중 널리 인용되는 기준값으로 구현을 검증한다.
이 테스트가 통과하면 투영 파라미터가 맞다는 뜻이다(구현 실수 방어).
"""
import unittest

from app.infra.public_api.kma_grid import latlon_to_grid

# (지점명, 위도, 경도, 기대 nx, 기대 ny) — 공개된 기상청 격자 대응값.
# 5km 격자라 좌표가 1km만 밀려도 칸이 바뀐다. 그래서 시청 좌표가 격자 경계에 걸치는
# 대구는 행정 중심(중구)을 쓴다 — 대구시청(35.8714)은 경계 바로 위라 (89,91)이 된다.
REFERENCE = [
    ("서울시청", 37.5665, 126.9780, 60, 127),
    ("부산시청", 35.1796, 129.0756, 98, 76),
    ("인천시청", 37.4563, 126.7052, 55, 124),
    ("대구 중구청", 35.8694, 128.6062, 89, 90),
    ("광주시청", 35.1595, 126.8526, 58, 74),
    ("대전시청", 36.3504, 127.3845, 67, 100),
    ("울산시청", 35.5384, 129.3114, 102, 84),
    ("제주시청", 33.4996, 126.5312, 53, 38),
]


class TestLatLonToGrid(unittest.TestCase):
    def test_matches_published_reference_points(self):
        for name, lat, lon, nx, ny in REFERENCE:
            with self.subTest(name=name):
                self.assertEqual(latlon_to_grid(lat, lon), (nx, ny))

    def test_is_deterministic(self):
        self.assertEqual(latlon_to_grid(37.5665, 126.9780), latlon_to_grid(37.5665, 126.9780))

    def test_rejects_out_of_range_coordinates(self):
        """(0,0)처럼 잘못된 좌표가 조용히 유효 격자로 둔갑하면 엉뚱한 지역 예보를 가져온다."""
        for lat, lon in [(0.0, 0.0), (90.0, 0.0), (-33.0, 151.0)]:
            with self.subTest(lat=lat, lon=lon), self.assertRaises(ValueError):
                latlon_to_grid(lat, lon)

    def test_nearby_points_share_or_neighbor_grid(self):
        """5km 격자라 가까운 두 점은 같거나 인접 격자여야 한다(변환이 폭주하지 않음)."""
        a = latlon_to_grid(37.5665, 126.9780)
        b = latlon_to_grid(37.5700, 126.9800)
        self.assertLessEqual(abs(a[0] - b[0]), 1)
        self.assertLessEqual(abs(a[1] - b[1]), 1)


if __name__ == "__main__":
    unittest.main()
