"""읍면동 토양 기준값 요약(경지구분 필터 + 평균) 검증. 순수 함수만 — 네트워크·DB 불필요.

표본 값은 2026-07-25 순천시 삼거동(4615010100) 실제 조회 결과에서 가져왔다.
"""
import unittest
from decimal import Decimal

from app.infra.public_api.soil_exam_client import SoilExam
from app.services.district_soil_service import summarize


def _exam(field_type_code: str, ph: float | None, om: float | None, p: float | None = None,
          ec: float | None = None) -> SoilExam:
    return SoilExam(
        pnu_code="4615010100100010001",
        sample_year="2023",
        exam_day="20230623",
        field_type_code=field_type_code,
        field_type=None,
        address="전라남도 순천시 삼거동",
        ph=ph,
        avail_p=p,
        avail_silica=None,
        organic_matter=om,
        mg=None,
        k=None,
        ca=None,
        ec=ec,
    )


# 삼거동 실측: 밭 1건(유기물 20), 과수 4건(51/62/27/4)
SAMPLES = [
    _exam("2", 5.1, 20.0, p=2.0, ec=0.27),
    _exam("4", 5.7, 51.0, p=11.0, ec=0.20),
    _exam("4", 5.8, 62.0, p=8.0, ec=0.24),
    _exam("4", 5.6, 27.0, p=19.0, ec=0.24),
    _exam("4", 5.2, 4.0, p=4.0, ec=0.25),
]


class TestSummarize(unittest.TestCase):
    def test_filters_by_field_type(self):
        """과수 요청 시 밭 표본이 섞이면 안 된다 — 유기물이 20 vs 51~62로 크게 다르다."""
        result = summarize(SAMPLES, "4")
        self.assertEqual(result["sample_count"], 4)
        self.assertEqual(result["organic_matter"], Decimal("36.0"))  # (51+62+27+4)/4

    def test_field_crop_gets_only_field_samples(self):
        result = summarize(SAMPLES, "2")
        self.assertEqual(result["sample_count"], 1)
        self.assertEqual(result["organic_matter"], Decimal("20.0"))

    def test_filtering_actually_changes_the_answer(self):
        """필터 없이 전지 평균을 냈다면 나올 값과 달라야 한다(필터가 무의미하지 않음을 고정)."""
        orchard = summarize(SAMPLES, "4")["organic_matter"]
        all_avg = Decimal(str(round((20 + 51 + 62 + 27 + 4) / 5, 2)))
        self.assertNotEqual(orchard, all_avg)

    def test_no_matching_samples_yields_zero_count_and_nulls(self):
        """시설(3) 표본이 없는 동네 — 값을 만들어내지 않고 표본 0으로 남긴다(§12)."""
        result = summarize(SAMPLES, "3")
        self.assertEqual(result["sample_count"], 0)
        self.assertIsNone(result["ph"])
        self.assertIsNone(result["organic_matter"])

    def test_missing_values_are_excluded_from_average(self):
        """일부 표본에 결측이 있어도 나머지로 평균한다 — 결측을 0으로 취급하지 않는다."""
        samples = [_exam("2", 6.0, None), _exam("2", 7.0, 30.0)]
        result = summarize(samples, "2")
        self.assertEqual(result["sample_count"], 2)
        self.assertEqual(result["ph"], Decimal("6.5"))
        self.assertEqual(result["organic_matter"], Decimal("30.0"))  # 결측 1건 제외

    def test_empty_input_is_safe(self):
        result = summarize([], "4")
        self.assertEqual(result["sample_count"], 0)
        self.assertIsNone(result["ec"])

    def test_is_deterministic(self):
        self.assertEqual(summarize(SAMPLES, "4"), summarize(SAMPLES, "4"))


if __name__ == "__main__":
    unittest.main()
