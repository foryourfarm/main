"""생육단계 resolver의 경계·겹침·범위밖·모드 분기 검증(순수 pick_stage)."""
import unittest

from app.models import CropGrowthStage
from app.services.growth_stage_service import pick_stage


def stage(name: str, mode: str, start: int, end: int, priority: int) -> CropGrowthStage:
    return CropGrowthStage(
        crop_id=1, growth_stage=name, mode=mode, range_start=start, range_end=end, priority=priority
    )


# 시드와 동일한 사과(연중일자) / 감자(파종후경과일) 구성.
APPLE = [
    stage("fruit_growth", "day_of_year", 111, 263, 1),
    stage("coloring", "day_of_year", 233, 293, 2),
    stage("maturity", "day_of_year", 294, 314, 3),
]
POTATO = [
    stage("early", "days_after_planting", 0, 45, 1),
    stage("tuber", "days_after_planting", 46, 120, 2),
]


class TestPickStage(unittest.TestCase):
    def test_day_of_year_mode_ignores_dap(self):
        # 6월(DOY 160) → 생장비대. dap는 무시돼야 한다.
        self.assertEqual(pick_stage(APPLE, day_of_year=160, days_after_planting=999), "fruit_growth")

    def test_overlap_picks_higher_priority_stage(self):
        # DOY 250은 fruit_growth(111-263)와 coloring(233-293) 둘 다 든다 → 진행된 coloring.
        self.assertEqual(pick_stage(APPLE, day_of_year=250, days_after_planting=0), "coloring")

    def test_boundaries_are_inclusive(self):
        self.assertEqual(pick_stage(APPLE, 314, 0), "maturity")  # 끝점 포함
        self.assertEqual(pick_stage(APPLE, 111, 0), "fruit_growth")  # 시작점 포함

    def test_out_of_all_ranges_returns_none(self):
        # 1월(DOY 15)은 사과 어느 단계에도 안 듦 → None(전기간 폴백).
        self.assertIsNone(pick_stage(APPLE, day_of_year=15, days_after_planting=0))

    def test_days_after_planting_mode(self):
        self.assertEqual(pick_stage(POTATO, day_of_year=1, days_after_planting=10), "early")
        self.assertEqual(pick_stage(POTATO, day_of_year=1, days_after_planting=45), "early")
        self.assertEqual(pick_stage(POTATO, day_of_year=1, days_after_planting=46), "tuber")
        self.assertIsNone(pick_stage(POTATO, day_of_year=1, days_after_planting=200))

    def test_no_stage_rows_returns_none(self):
        # 오이·상추: 시드 행 없음 → None.
        self.assertIsNone(pick_stage([], day_of_year=160, days_after_planting=30))


if __name__ == "__main__":
    unittest.main()
