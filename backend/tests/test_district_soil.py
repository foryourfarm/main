"""읍면동 토양 기준값 요약(경지구분 필터 + 평균) 검증. 순수 함수만 — 네트워크·DB 불필요.

표본 값은 2026-07-25 순천시 삼거동(4615010100) 실제 조회 결과에서 가져왔다.
"""
import unittest
from decimal import Decimal

import httpx

from app.infra.public_api.base import PublicApiError
from app.infra.public_api.soil_exam_client import SoilExam
from app.models import DistrictSoil
from app.services import district_soil_service
from app.services.district_soil_service import (
    effective_source,
    is_leaf_bjd,
    ri_codes,
    source_label,
    summarize,
)


def _exam(field_type_code: str, ph: float | None, om: float | None, p: float | None = None,
          ec: float | None = None, k: float | None = None, ca: float | None = None,
          mg: float | None = None) -> SoilExam:
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
        mg=mg,
        k=k,
        ca=ca,
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


class TestSummarizeCations(unittest.TestCase):
    """치환성 양이온(K·Ca·Mg) 집계 — 0024에서 채점 대상이 됐다.

    흙토람이 `POSIFERT_K/CA/MG`를 주고 있었는데 저장할 컬럼이 없어 버려지던 값이다. 그
    경로가 실제로 이어졌는지 본다 — 아래 값은 고창 공음면 구암리 실호출 표본에서 가져왔다
    (2026-08-01, K 0.314~2.469 / Ca 1.94~12.16 / Mg 0.76~4.92 범위 안).

    `_avg`가 소수 2자리로 반올림하므로 여유(delta)를 두고 비교한다. 그 정밀도로 충분하다 —
    가장 좁은 밴드가 K optimal 0.6~0.9(폭 0.3)라 0.01은 폭의 3%이고, 등급 컷을 뒤집지 못한다.
    """

    def _cation_exam(self, field_type_code: str, k, ca, mg) -> SoilExam:
        return _exam(field_type_code, ph=6.1, om=14.7, p=182.4, ec=1.35, k=k, ca=ca, mg=mg)

    def test_cations_are_averaged_per_field_type(self):
        samples = [
            self._cation_exam("4", 0.886, 4.24, 1.44),
            self._cation_exam("4", 0.564, 8.37, 2.85),
            self._cation_exam("2", 2.469, 9.53, 3.32),  # 밭 표본 — 과수 평균에 섞이면 안 된다
        ]
        result = summarize(samples, "4")
        self.assertAlmostEqual(float(result["k"]), (0.886 + 0.564) / 2, delta=0.01)
        self.assertAlmostEqual(float(result["ca"]), (4.24 + 8.37) / 2, delta=0.01)
        self.assertAlmostEqual(float(result["mg"]), (1.44 + 2.85) / 2, delta=0.01)

    def test_cations_are_none_when_all_samples_lack_them(self):
        """전부 결측이면 값을 지어내지 않는다 — 룰 엔진이 그 지표를 제외한다(§12)."""
        result = summarize(SAMPLES, "4")  # 기존 픽스처는 양이온이 전부 None
        for name in ("k", "ca", "mg"):
            with self.subTest(indicator=name):
                self.assertIsNone(result[name])

    def test_partial_missing_cations_are_excluded_from_average(self):
        samples = [
            self._cation_exam("4", 0.886, None, 1.44),
            self._cation_exam("4", None, 8.37, 2.85),
        ]
        result = summarize(samples, "4")
        self.assertAlmostEqual(float(result["k"]), 0.886, delta=0.01)
        self.assertAlmostEqual(float(result["ca"]), 8.37, delta=0.01)
        self.assertAlmostEqual(float(result["mg"]), (1.44 + 2.85) / 2, delta=0.01)


class TestGetOrFetchRefresh(unittest.TestCase):
    """`refresh=True`가 캐시를 무시하는지(0024 후속).

    **왜 필요한가**: `get_or_fetch`는 `sample_count > 0`이면 캐시를 그대로 준다. 0024로
    양이온 컬럼이 생겼지만 그 전에 캐시된 행은 그 값이 NULL이고, 평소 경로로는 영구히
    갱신되지 않는다 — **그 읍면동에 새로 등록하는 밭도 양이온이 빈 채로 시작한다.**
    `scripts/repair_empty_soil_state.py`가 이 인자로 캐시를 훑는다.

    상시 경로가 바뀌지 않는 것(기본값 False)도 같이 고정한다 — 무분별 재조회는 §18-1 위반이다.
    """

    def setUp(self):
        self.cached = DistrictSoil(
            bjd_code="4615012300",
            field_type="4",
            ph=Decimal("6.0"),
            ec=Decimal("0.3"),
            p2o5=Decimal("400"),
            organic_matter=Decimal("30"),
            sample_count=5,  # > 0 이므로 평소엔 캐시가 그대로 반환된다
            source="옛 캐시",
        )
        self.fetch_calls = 0
        self._real_fetch = district_soil_service._fetch_exams

        def _fake_fetch(bjd_code: str):
            self.fetch_calls += 1
            # 3번째 값은 조회 실패 여부 — 성공 경로라 False.
            return [_exam("4", 6.1, 14.7, p=182.4, ec=1.35, k=0.9, ca=6.0, mg=2.0)], bjd_code, False

        district_soil_service._fetch_exams = _fake_fetch

    def tearDown(self):
        district_soil_service._fetch_exams = self._real_fetch

    def _db(self):
        cached = self.cached

        class _Query:
            def filter(self, *a, **k):
                return self

            def first(self):
                return cached

        class _Db:
            def query(self, *a, **k):
                return _Query()

            def add(self, _obj):
                raise AssertionError("캐시가 있으면 새 행을 넣으면 안 된다(유니크 충돌)")

            def flush(self):
                pass

        return _Db()

    def test_default_uses_cache_and_does_not_call_api(self):
        got = district_soil_service.get_or_fetch(self._db(), "4615012300", "4")
        self.assertEqual(self.fetch_calls, 0)
        self.assertIsNone(got.k)  # 옛 캐시 그대로 — 양이온 없음

    def test_refresh_refetches_and_fills_cations(self):
        got = district_soil_service.get_or_fetch(
            self._db(), "4615012300", "4", refresh=True
        )
        self.assertEqual(self.fetch_calls, 1)
        self.assertAlmostEqual(float(got.k), 0.9, delta=0.01)
        self.assertAlmostEqual(float(got.ca), 6.0, delta=0.01)
        self.assertAlmostEqual(float(got.mg), 2.0, delta=0.01)

    def test_refresh_updates_the_same_row_not_a_new_one(self):
        """같은 행을 갱신해야 한다 — 새 행을 add하면 (bjd_code, field_type) 유니크에 걸린다.
        위 _Db.add가 실패를 던지므로 새 행을 만들면 이 테스트가 깨진다."""
        got = district_soil_service.get_or_fetch(
            self._db(), "4615012300", "4", refresh=True
        )
        self.assertIs(got, self.cached)


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


class TestFetchExamsSwallowsNetworkErrors(unittest.TestCase):
    """`_fetch_exams`가 네트워크 예외를 실제로 잡는지.

    **종전엔 못 잡았다.** `except (PublicApiError, OSError)`로 적혀 있었는데 httpx 예외는
    `OSError` 하위가 아니라 `httpx.HTTPError` 계열이다. 그래서 타임아웃·401·5xx가 그대로
    위로 튀어 **밭 등록이 500으로 죽었다** — §12 "산출이 예외로 죽지 않게 한다" 위반.
    2026-08-03 data.go.kr이 평문 http를 중단했을 때 실제로 이 경로를 탔다.
    """

    def setUp(self):
        self._real = district_soil_service.get_soil_exam_list

    def tearDown(self):
        district_soil_service.get_soil_exam_list = self._real

    def _raise(self, exc: Exception):
        def _stub(*args, **kwargs):
            raise exc

        district_soil_service.get_soil_exam_list = _stub

    def test_timeout_does_not_propagate(self):
        self._raise(httpx.ConnectTimeout("타임아웃"))
        exams, code, failed = district_soil_service._fetch_exams("1215010100")
        self.assertEqual(exams, [])
        self.assertIsNone(code)
        self.assertTrue(failed, "네트워크 실패인데 fetch_failed가 False다")

    def test_http_status_error_does_not_propagate(self):
        self._raise(httpx.HTTPStatusError("401", request=None, response=None))
        exams, code, failed = district_soil_service._fetch_exams("1215010100")
        self.assertEqual(exams, [])
        self.assertTrue(failed)

    def test_no_data_301_is_not_a_failure(self):
        """301은 상대가 '기록 없다'고 답한 것 — 조회는 성공했으므로 우리 장애가 아니다."""
        self._raise(PublicApiError(district_soil_service.NO_DATA_CODE, "요청 데이터 없음"))
        exams, code, failed = district_soil_service._fetch_exams("1215010100")
        self.assertEqual(exams, [])
        self.assertFalse(failed, "301을 장애로 셌다 — 데이터 한계를 우리 잘못이라 말하게 된다")

    def test_other_api_error_counts_as_failure(self):
        """201(파라미터 오류) 등은 우리 잘못일 수 있으니 '기록 없음'이라 단정하지 않는다."""
        self._raise(PublicApiError("201", "파라미터 오류"))
        _, _, failed = district_soil_service._fetch_exams("1215010100")
        self.assertTrue(failed)


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
        self.assertIn("기록 없음", label)
        self.assertNotIn("리를 선택", label)
        # 우리 장애가 아니므로 "가져오지 못했습니다"라고 말하면 안 된다.
        self.assertNotIn("가져오지 못", label)

    def test_fetch_failure_is_not_reported_as_missing_data(self):
        """네트워크·API 실패를 '표본 없음'이라 말하면 우리 장애를 지역 데이터 한계로
        둔갑시킨다 — 없는 사실을 단정하는 §18-4 위반이다(2026-08-03 data.go.kr http 중단)."""
        label = source_label("1215010100", None, "4", fetch_failed=True)
        self.assertIn("가져오지 못", label)
        self.assertNotIn("기록 없음", label)
        # 유저가 다음 행동을 알 수 있어야 한다 — 기다리면 되는 상황이다.
        self.assertIn("다시 시도", label)

    def test_failure_and_no_data_never_share_wording(self):
        """두 문구가 같아지면 구분이 무의미해진다 — 회귀 방지."""
        no_data = source_label("1215010100", None, "4", fetch_failed=False)
        failed = source_label("1215010100", None, "4", fetch_failed=True)
        self.assertNotEqual(no_data, failed)

    def test_non_leaf_failure_prefers_failure_wording(self):
        """리 안내는 '조회는 됐는데 기록이 없다'는 전제 위에 선다 — 못 받은 상황엔 맞지 않는다."""
        label = source_label("5279034000", None, "3", fetch_failed=True)
        self.assertIn("가져오지 못", label)
        self.assertNotIn("리를 선택", label)

    def test_never_claims_a_unit_it_did_not_query(self):
        """폴백 시절 버그 회귀 방지 — 리 코드를 면처럼 적어 이웃 값을 내 땅 값으로 보이게 했다."""
        for bjd in ("5279034023", "5279034000", "1215010100"):
            for queried in (bjd, None):
                with self.subTest(bjd=bjd, queried=queried):
                    self.assertNotIn("리 5곳", source_label(bjd, queried, "3"))


class TestEffectiveSource(unittest.TestCase):
    """저장된 문구는 등록 시점에 굳는다 — 응답 시점에 다시 보는 규칙(§18-4)."""

    STALE = "흙토람 토양검정(조회 실패 — 표본 없음), 표본 0건"

    def test_stale_myeon_farm_gets_the_actionable_message(self):
        """리 전환 전 등록된 면 코드 밭 — '조회 실패'는 다음 행동이 없는 막다른 문구다."""
        out = effective_source("5279034000", self.STALE, has_values=False)
        self.assertIn("리를 선택", out)
        self.assertNotIn("조회 실패", out)

    def test_real_values_are_never_overwritten(self):
        """값이 있으면 그 문구가 실제 조회 근거다 — 덮으면 없는 결측을 지어내는 셈이다."""
        real = "흙토람 토양검정(법정동 5279034023, 경지구분 3), 표본 12건"
        self.assertEqual(effective_source("5279034000", real, has_values=True), real)

    def test_leaf_farm_with_no_samples_keeps_the_honest_failure(self):
        """리 없는 도시 동은 진짜로 표본이 없다 — 리를 고르라고 하면 거짓 안내가 된다."""
        self.assertEqual(effective_source("1215010100", self.STALE, has_values=False), self.STALE)

    def test_legacy_farm_without_bjd_code_is_left_alone(self):
        """0014 이전 등록 밭은 bjd_code가 없어 말단 판정 자체가 불가능하다."""
        self.assertEqual(effective_source(None, self.STALE, has_values=False), self.STALE)


if __name__ == "__main__":
    unittest.main()
