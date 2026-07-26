"""농경지화학성 통계정보 V2 구간통계 가중평균 검증. 네트워크·API키 불필요(캔드 item만).

구간표는 기술명세서(농경지화학성-통계정보_V2_API기술명세서.md)의 응답 항목 구간을 그대로
옮긴 것이라, 이 테스트는 "구간 경계가 명세서와 어긋나지 않는지"를 잡는 목적이다.
"""

import unittest
from unittest.mock import patch

from app.infra.public_api.soil_chem_stat_client import (
    AP_RANGES_FIELD,
    AP_RANGES_PADDY,
    OM_RANGES,
    PH_RANGES,
    _weighted_avg,
    get_region_soil_chem_stat,
)


class TestBinRangeTables(unittest.TestCase):
    def test_ranges_are_ascending_and_non_overlapping(self):
        """구간 경계가 뒤집히거나 겹치면 중점이 엉뚱한 값이 된다.

        실제로 명세서 표기가 "논251~250이하"인 오타를 그대로 베낀 버그가 있었다
        (하한 251 > 상한 250 → 중점 250.5, 정상은 201~250의 225.5).
        """
        for name, ranges in [
            ("pH", PH_RANGES),
            ("유기물", OM_RANGES),
            ("유효인산-논", AP_RANGES_PADDY),
            ("유효인산-밭", AP_RANGES_FIELD),
        ]:
            with self.subTest(name=name):
                for lo, hi in ranges:
                    self.assertLessEqual(lo, hi, f"{name}: 하한 {lo} > 상한 {hi}")
                for (_, prev_hi), (next_lo, _) in zip(ranges, ranges[1:]):
                    self.assertLess(prev_hi, next_lo, f"{name}: 구간 {prev_hi}~{next_lo} 겹침")

    def test_paddy_avail_p_fifth_bin_midpoint(self):
        """논 유효인산 5번째 구간(201~250)의 중점은 225.5여야 한다(명세서 오타 방어)."""
        lo, hi = AP_RANGES_PADDY[4]
        self.assertEqual((lo + hi) / 2, 225.5)


class TestWeightedAvg(unittest.TestCase):
    def test_single_bin_returns_its_midpoint(self):
        areas = [None, None, 100.0, None, None, None]
        self.assertAlmostEqual(_weighted_avg(areas, PH_RANGES), 5.3)  # (5.1+5.5)/2

    def test_area_weights_the_result(self):
        """면적이 큰 구간으로 평균이 끌려가야 한다."""
        low_heavy = _weighted_avg([900.0, None, 100.0, None, None, None], PH_RANGES)
        high_heavy = _weighted_avg([100.0, None, 900.0, None, None, None], PH_RANGES)
        self.assertLess(low_heavy, high_heavy)

    def test_returns_none_when_all_areas_missing_or_zero(self):
        """면적이 없으면 0이 아니라 결측(None)이다 — 0을 반환하면 pH 0으로 오해된다."""
        self.assertIsNone(_weighted_avg([None] * 6, PH_RANGES))
        self.assertIsNone(_weighted_avg([0.0] * 6, PH_RANGES))

    def test_ignores_negative_area(self):
        """음수 면적은 이상치 → 가중치에서 제외(§12 경계 방어)."""
        self.assertAlmostEqual(
            _weighted_avg([-50.0, None, 100.0, None, None, None], PH_RANGES), 5.3
        )


class TestGetRegionSoilChemStat(unittest.TestCase):
    """3개 엔드포인트를 순서대로 호출하므로 side_effect로 응답을 차례로 준다."""

    PH_ITEM = {
        "stdg_Cd": "5279000000",
        "bjd_Nm": "전라북도 고창군",
        "acid_Rfld3_Area": "100",  # 논 5.1~5.5 → 5.3
        "acid_Pfld3_Area": "100",  # 밭 5.1~5.5 → 5.3
    }
    OM_ITEM = {"om_Rfld2_Area": "100", "om_Pfld2_Area": "100"}  # 11~20 → 15.5 g/kg
    AP_ITEM = {"vldpha_Rfld5_Area": "100"}  # 논 201~250 → 225.5 (밭 결측)

    def test_parses_all_three_indicators(self):
        with patch(
            "app.infra.public_api.soil_chem_stat_client.fetch_items",
            side_effect=[[self.PH_ITEM], [self.OM_ITEM], [self.AP_ITEM]],
        ):
            stat = get_region_soil_chem_stat("5279000000")

        self.assertIsNotNone(stat)
        self.assertEqual(stat.bjd_code, "5279000000")
        self.assertEqual(stat.bjd_name, "전라북도 고창군")
        self.assertAlmostEqual(stat.ph_avg, 5.3)
        self.assertAlmostEqual(stat.organic_matter_avg, 15.5)
        # 논만 있으면 논 값을 그대로 쓴다. 251~250 오타면 여기서 250.5가 나온다.
        self.assertAlmostEqual(stat.avail_p_avg, 225.5)

    def test_survives_missing_optional_endpoints(self):
        """유기물·유효인산이 비어도 pH만으로 산출이 죽지 않는다(§18-5)."""
        with patch(
            "app.infra.public_api.soil_chem_stat_client.fetch_items",
            side_effect=[[self.PH_ITEM], [], []],
        ):
            stat = get_region_soil_chem_stat("5279000000")

        self.assertAlmostEqual(stat.ph_avg, 5.3)
        self.assertIsNone(stat.organic_matter_avg)
        self.assertIsNone(stat.avail_p_avg)

    def test_returns_none_when_region_has_no_data(self):
        with patch(
            "app.infra.public_api.soil_chem_stat_client.fetch_items", side_effect=[[]]
        ):
            self.assertIsNone(get_region_soil_chem_stat("9999999999"))

    def test_open_top_bin_stays_realistic(self):
        """최상단 개방구간("pH 6.6이상")만 있는 지역도 현실적인 pH가 나와야 한다.

        이론 상한 14를 쓰면 중점이 10.3이 되는데, 한국 농경지에 pH 10 지역은 없다.
        직전 구간 폭(0.5)을 가정해 6.85로 잡는다 — 실측 여러 지역 검증에서 pH 5.7~5.9로
        수렴했고, 상한 14를 쓰던 시절엔 유효인산이 2008 mg/kg까지 튀었다.
        """
        with patch(
            "app.infra.public_api.soil_chem_stat_client.fetch_items",
            side_effect=[[{"stdg_Cd": "1", "bjd_Nm": "x", "acid_Rfld6_Area": "100"}], [], []],
        ):
            stat = get_region_soil_chem_stat("1")
        self.assertAlmostEqual(stat.ph_avg, 6.85)
        self.assertLess(stat.ph_avg, 8.0, "국내 농경지 pH 상한을 넘는 값이 새 나갔다")

    def test_open_top_bins_do_not_blow_up_avail_p(self):
        """유효인산 밭 최상단(601이상)만 있어도 현실 범위(400~700)를 지켜야 한다."""
        with patch(
            "app.infra.public_api.soil_chem_stat_client.fetch_items",
            side_effect=[
                [{"stdg_Cd": "1", "bjd_Nm": "x", "acid_Rfld3_Area": "10"}],
                [],
                [{"vldpha_Pfld6_Area": "100"}],
            ],
        ):
            stat = get_region_soil_chem_stat("1")
        self.assertLess(stat.avail_p_avg, 800.0, "개방구간 상한이 다시 폭주했다")
        self.assertGreater(stat.avail_p_avg, 600.0)


if __name__ == "__main__":
    unittest.main()
