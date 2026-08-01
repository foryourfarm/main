"""WKB 폴리곤 파싱·코드 되짚기 검증 (`scripts/bjd_polygon.py`).

원본 CSV 292MB는 리포에 없으므로 **손으로 만든 WKB**로 검사한다 — 파서가 깨지면
리 15,209건의 좌표가 통째로 틀어지는데, 그건 시드 CSV만 봐선 안 보인다.
"""

import binascii
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from bjd_polygon import _centroid, _exterior_rings, augment_by_name, resolve  # noqa: E402


def _ring_wkb(rings: list[list[tuple[float, float]]], multi: bool = False) -> str:
    """테스트용 WKB 조립. 실제 데이터셋과 같은 little-endian이다."""
    if multi:
        body = struct.pack("<BII", 1, 6, len(rings))
        for ring in rings:
            body += struct.pack("<BII", 1, 3, 1)
            body += struct.pack("<I", len(ring))
            for x, y in ring:
                body += struct.pack("<2d", x, y)
    else:
        body = struct.pack("<BII", 1, 3, len(rings))
        for ring in rings:
            body += struct.pack("<I", len(ring))
            for x, y in ring:
                body += struct.pack("<2d", x, y)
    return binascii.hexlify(body).decode()


SQUARE = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0), (0.0, 0.0)]


class TestWkbParsing(unittest.TestCase):
    def test_simple_polygon(self):
        rings = _exterior_rings(_ring_wkb([SQUARE]))
        self.assertEqual(len(rings), 1)
        self.assertEqual(rings[0], SQUARE)

    def test_multipolygon_returns_every_piece(self):
        """섬처럼 조각이 여러 개인 리가 1,120건 있다 — 하나만 읽으면 그 리가 틀어진다."""
        far = [(10.0, 10.0), (11.0, 10.0), (11.0, 11.0), (10.0, 10.0)]
        rings = _exterior_rings(_ring_wkb([SQUARE, far], multi=True))
        self.assertEqual(len(rings), 2)

    def test_interior_ring_is_skipped(self):
        """구멍(내부 링)은 대표점에 거의 영향이 없어 버린다 — 버리다가 외곽까지
        놓치면 안 되므로 고정한다."""
        hole = [(0.5, 0.5), (1.5, 0.5), (1.5, 1.5), (0.5, 0.5)]
        rings = _exterior_rings(_ring_wkb([SQUARE, hole]))
        self.assertEqual(rings, [SQUARE])


class TestCentroid(unittest.TestCase):
    def test_square_centre(self):
        x, y, area = _centroid(SQUARE)
        self.assertAlmostEqual(x, 1.0)
        self.assertAlmostEqual(y, 1.0)
        self.assertAlmostEqual(area, 4.0)

    def test_dense_vertices_do_not_pull_the_centre(self):
        """정점 단순평균이면 촘촘한 변으로 끌린다(해안선이 실제로 그렇다).
        면적 기준이라 정사각형 중심이 유지돼야 한다."""
        dense = [(0.0, 0.0)]
        dense += [(i / 50, 0.0) for i in range(1, 100)]  # 아랫변에 정점 99개
        dense += [(2.0, 0.0), (2.0, 2.0), (0.0, 2.0), (0.0, 0.0)]
        x, y, _ = _centroid(dense)
        self.assertAlmostEqual(x, 1.0, places=6)
        self.assertAlmostEqual(y, 1.0, places=6)

    def test_degenerate_polygon_does_not_divide_by_zero(self):
        """면적 0 도형 하나가 전체 적재를 죽이지 않게 한다(§12)."""
        line = [(1.0, 1.0), (2.0, 1.0), (1.0, 1.0)]
        x, y, area = _centroid(line)
        self.assertEqual(area, 0.0)
        self.assertTrue(1.0 <= x <= 2.0)


class TestCodeResolution(unittest.TestCase):
    """데이터셋이 2023-09 기준이라 그 뒤 개편을 되짚어야 한다. 이 3단계가 92.6%를 만든다."""

    LEGACY = {"12110": "46110"}  # 전남광주통합 목포시

    def test_direct_hit(self):
        self.assertEqual(resolve("4211038021", {"4211038021": (37.0, 128.0)}, {}), (37.0, 128.0))

    def test_merged_sgg_code_retry(self):
        centroids = {"4611010100": (34.8, 126.4)}
        self.assertEqual(resolve("1211010100", centroids, self.LEGACY), (34.8, 126.4))

    def test_sido_renumbering_retry(self):
        """강원 51↔42, 전북 52↔45 — 이 대응 하나로 리 2,562건이 붙는다."""
        centroids = {"4276038021": (37.7, 128.7)}
        self.assertEqual(resolve("5176038021", centroids, {}), (37.7, 128.7))
        centroids = {"4519025021": (35.4, 127.5)}
        self.assertEqual(resolve("5219025021", centroids, {}), (35.4, 127.5))

    def test_unknown_code_returns_none(self):
        """못 찾으면 None — 호출부가 상위 단위로 폴백하고 그 사실을 표기한다(§18-4).
        엉뚱한 좌표를 지어내지 않는다."""
        self.assertIsNone(resolve("9999999999", {"4211038021": (37.0, 128.0)}, {}))


class TestNameFallback(unittest.TestCase):
    """구(區) 신설처럼 읍면동·리 코드까지 재부여되면 코드 규칙이 통째로 깨진다.
    그때 이름으로 이어 붙이되, 확신할 수 없으면 붙이지 않는다."""

    # 옛 화성시(41590)에 리 4개가 있고, 새 화성시효행구(41593)는 코드가 전부 재부여됐다.
    OLD = {f"415903002{i}": (37.0 + i / 100, 126.9) for i in range(1, 5)}
    OLD_NAMES = {
        "4159030021": "가리", "4159030022": "나리",
        "4159030023": "다리", "4159030024": "라리",
    }

    def test_recovers_when_every_code_digit_changed(self):
        rows = [("4159370011", "가리"), ("4159370012", "나리"), ("4159370013", "다리")]
        added = augment_by_name(rows, self.OLD, self.OLD_NAMES, {})
        self.assertEqual(set(added), {"4159370011", "4159370012", "4159370013"})
        self.assertEqual(added["4159370011"], self.OLD["4159030021"])

    def test_already_resolvable_rows_are_left_alone(self):
        """코드로 찾히는 행은 건드리지 않는다 — 이름 매칭은 폴백이지 대체가 아니다."""
        added = augment_by_name(
            [("4159030021", "가리")], self.OLD, self.OLD_NAMES, {}
        )
        self.assertEqual(added, {})

    def test_duplicate_name_in_same_sgg_is_dropped(self):
        """같은 시군구에 같은 이름 리가 둘이면 어느 쪽인지 알 수 없다. 찍지 않는다 —
        엉뚱한 골짜기 고도가 들어가면 폴백보다 나쁘다(§18-4)."""
        centroids = dict(self.OLD) | {"4159040021": (37.5, 127.2)}
        names = dict(self.OLD_NAMES) | {"4159040021": "가리"}  # '가리'가 두 곳
        rows = [("4159370011", "가리"), ("4159370012", "나리"), ("4159370013", "다리")]
        added = augment_by_name(rows, centroids, names, {})
        self.assertNotIn("4159370011", added)  # 모호한 것만 빠지고
        self.assertIn("4159370012", added)  # 나머지는 붙는다

    def test_weak_vote_maps_nothing(self):
        """이름 하나가 우연히 겹쳤다고 시군구 대응을 만들면 전국이 뒤섞인다."""
        rows = [("9999900011", "가리"), ("9999900012", "없는리"), ("9999900013", "또없는리")]
        self.assertEqual(augment_by_name(rows, self.OLD, self.OLD_NAMES, {}), {})


if __name__ == "__main__":
    unittest.main()
