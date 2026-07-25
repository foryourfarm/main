"""대시보드 단계 라벨 매핑 검증(순수 부분)."""
import unittest

from app.services.dashboard_service import _stage_label


class TestStageLabel(unittest.TestCase):
    def test_known_stage_maps_to_korean(self):
        self.assertEqual(_stage_label("tuber", "ok"), "괴경비대기")
        self.assertEqual(_stage_label("coloring", "ok"), "착색기")

    def test_none_stage_ok_is_all_period(self):
        self.assertEqual(_stage_label(None, "insufficient_data"), "전기간")

    def test_none_stage_out_of_season(self):
        self.assertEqual(_stage_label(None, "out_of_season"), "제철 아님")

    def test_unknown_code_passes_through(self):
        self.assertEqual(_stage_label("weird", "ok"), "weird")


if __name__ == "__main__":
    unittest.main()
