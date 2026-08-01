"""읍면동 토양 기준값 요약(경지구분 필터 + 평균) 검증. 순수 함수만 — 네트워크·DB 불필요.

표본 값은 2026-07-25 순천시 삼거동(4615010100) 실제 조회 결과에서 가져왔다.
"""
import unittest
from decimal import Decimal

from app.infra.public_api.soil_exam_client import SoilExam
from app.services.district_soil_service import (
    is_leaf_bjd,
    ri_codes,
    source_label,
    summarize,
)


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


class TestRiCodes(unittest.TestCase):
    """읍·면 검정 기록은 리 코드로만 조회된다 — 시드에서 리를 찾아오는지(네트워크 불필요)."""

    def test_myeon_resolves_to_its_ri_codes(self):
        # 실측: 부여 장암면 4476042000은 301, 점상리 4476042021은 100건.
        codes = ri_codes("4476042000")
        self.assertIn("4476042021", codes)
        self.assertTrue(all(c.startswith("44760420") for c in codes))

    def test_dong_without_ri_returns_empty(self):
        # 순천 삼거동은 리가 없어 읍면동 코드가 곧 말단이다 — 리 조회 경로를 타면 안 된다.
        # 코드는 시드 기준 신코드(전남광주통합 12150)다. 구코드 4615010100을 쓰면 "리가 없어서"가
        # 아니라 "시드에 그 코드가 없어서" 빈 리스트가 나와 아무것도 검증하지 못한다.
        self.assertEqual(ri_codes("1215010100"), [])

    def test_ri_code_returns_its_siblings_including_itself(self):
        """리 코드를 넣으면 형제 리가 나온다 — 앞 8자리를 공유하기 때문(독스트링의 주의 사항).

        말단 판정·폴백이 이 성질을 모르고 쓰면 리를 면으로 착각한다. 고정해 둔다.
        """
        codes = ri_codes("4476042021")
        self.assertIn("4476042021", codes)
        self.assertEqual(codes, ri_codes("4476042000"))


class TestIsLeafBjd(unittest.TestCase):
    """선택지로 노출할 말단 판정. 리가 있으면 리까지, 없으면 그 윗선(docs/design/ri-level-district.md)."""

    def test_myeon_with_ri_is_not_leaf(self):
        """부여 장암면 — 이 코드로는 흙토람이 301을 주므로 고르게 하면 안 된다."""
        self.assertFalse(is_leaf_bjd("4476042000"))
        self.assertFalse(is_leaf_bjd("5279034000"))  # 고창 공음면

    def test_ri_is_leaf(self):
        """리는 항상 말단 — ri_codes가 형제를 물고 와도 말단 판정이 흔들리면 안 된다."""
        self.assertTrue(is_leaf_bjd("4476042021"))  # 장암면 점상리
        self.assertTrue(is_leaf_bjd("5279034023"))  # 공음면 구암리

    def test_dong_without_ri_is_leaf(self):
        """리 없는 동은 지금처럼 그 자체가 말단이다(순천 삼거동)."""
        self.assertTrue(is_leaf_bjd("1215010100"))

    def test_unknown_code_is_treated_as_leaf(self):
        """시드에 없는 코드는 걸러내지 않는다 — 조용히 선택지에서 사라지는 게 더 나쁘다."""
        self.assertTrue(is_leaf_bjd("9999999900"))


class TestSourceLabel(unittest.TestCase):
    """출처 문구는 화면 footer까지 그대로 나간다 — 유저와의 약속이므로 고정한다(§18-4)."""

    def test_leaf_code_names_the_code_it_queried(self):
        label = source_label("5279034023", "5279034023", "3")
        self.assertIn("5279034023", label)
        self.assertIn("경지구분 3", label)

    def test_merged_region_discloses_the_legacy_code(self):
        """통합전 코드로 받아왔으면 그 사실을 밝힌다 — 유저가 고른 코드와 다르다."""
        label = source_label("1274038021", "4677038021", "2")
        self.assertIn("4677038021", label)
        self.assertIn("통합전", label)

    def test_non_leaf_tells_the_user_what_to_do(self):
        """리를 가진 읍·면은 '조회 실패'로 뭉개지 않는다 — 리를 고르면 해결된다는 걸 알려야 한다."""
        label = source_label("5279034000", None, "3")
        self.assertIn("리", label)
        self.assertNotIn("조회 실패", label)

    def test_leaf_with_no_samples_says_so_plainly(self):
        """리 없는 도시 동에 표본이 진짜 없는 경우 — 리 안내를 붙이면 거짓말이 된다."""
        label = source_label("1215010100", None, "4")
        self.assertIn("조회 실패", label)
        self.assertNotIn("리를 선택", label)

    def test_never_claims_a_unit_it_did_not_query(self):
        """폴백 시절 버그 회귀 방지 — 리 코드를 면처럼 적어 이웃 값을 내 땅 값으로 보이게 했다."""
        for bjd in ("5279034023", "5279034000", "1215010100"):
            for queried in (bjd, None):
                with self.subTest(bjd=bjd, queried=queried):
                    self.assertNotIn("리 5곳", source_label(bjd, queried, "3"))


if __name__ == "__main__":
    unittest.main()
