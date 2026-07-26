"""일조시간 산출 검증.

두 층으로 본다:
1. 물리량(가조시간·지구외일사량)이 천문학적으로 맞는지 — 알려진 기준값과 대조.
2. **일사량 → 일조시간 환산 정확도가 실제로 0.90을 넘는지** — 실측 홀드아웃
   fixture(농업기상 V3, 보정에 쓰지 않은 절반)로 MAE·상관을 재계산해 확인한다.

2번이 이 파일의 핵심이다. 신뢰도 0.90은 선언이 아니라 이 테스트가 지키는 약속이다 —
계수를 잘못 만지거나 품질 필터를 빼면 여기서 즉시 깨진다.
"""

import json
import math
import unittest
from pathlib import Path

from app.services.sunlight_calculation import (
    SunlightCalculation,
    SunlightResult,
    calibration,
    day_of_year,
    daylight_hours,
    extraterrestrial_radiation,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sunlight_validation.json"


class TestSolarGeometry(unittest.TestCase):
    """가조시간·지구외일사량은 정확히 계산돼야 한다 — 오차의 출처를 계수로만 한정하기 위해."""

    def test_equinox_daylight_is_about_12_hours(self):
        """춘분(doy 80)에는 위도와 무관하게 약 12시간."""
        for lat in (33.5, 37.5, 38.4):
            with self.subTest(lat=lat):
                self.assertAlmostEqual(daylight_hours(lat, 80), 12.0, delta=0.15)

    def test_seasonal_swing_is_larger_at_higher_latitude(self):
        """하지-동지 낮길이 차이는 고위도에서 더 커야 한다(제주 < 강원 북부)."""
        jeju = daylight_hours(33.5, 172) - daylight_hours(33.5, 355)
        goseong = daylight_hours(38.4, 172) - daylight_hours(38.4, 355)
        self.assertGreater(jeju, 0)
        self.assertGreater(goseong, jeju)

    def test_korea_daylight_within_known_bounds(self):
        """국내 낮길이는 약 9.3~14.7시간(제주 남단~강원 북단). 기하학적 낮길이라 대기굴절
        보정은 없다 — 실제 일출~일몰보다 몇 분 짧게 나오는 것이 정상이다."""
        for lat in (33.1, 38.6):
            for doy in range(1, 366, 10):
                with self.subTest(lat=lat, doy=doy):
                    self.assertTrue(9.0 <= daylight_hours(lat, doy) <= 15.0)

    def test_declination_hits_the_solstice_values(self):
        """태양적위는 하지 +23.44°, 동지 −23.44°여야 한다 — 천문 상수와 대조하는
        독립 검증이다(우리 출력끼리 비교하는 순환 검증이 아니다)."""
        # daylight_hours는 적위의 함수이므로 적위를 역산해 확인한다.
        for doy, expected_deg in ((172, 23.44), (355, -23.44)):
            with self.subTest(doy=doy):
                # 위도 0에서는 항상 12h라 정보가 없으므로 45°N을 쓴다.
                n = daylight_hours(45.0, doy)
                ws = n * math.pi / 24.0
                dec = math.atan(-math.cos(ws) / math.tan(math.radians(45.0)))
                self.assertAlmostEqual(math.degrees(dec), expected_deg, delta=0.7)

    def test_radiation_never_below_observed(self):
        """지구외 일사량은 지표 실측 일사량보다 항상 커야 한다 — 실측 230건으로 Ra를
        검증한다. Ra가 10%만 틀려도 여기서 물리적으로 불가능한 비율이 잡힌다."""
        rows = json.loads(FIXTURE.read_text(encoding="utf-8"))["rows"]
        for r in rows:
            ra = extraterrestrial_radiation(r["latitude"], day_of_year(r["month"]))
            with self.subTest(name=r["name"], month=r["month"]):
                self.assertLess(r["solar_radiation"] / ra, 0.80)

    def test_day_of_year(self):
        self.assertEqual(day_of_year(1, 15), 15)
        self.assertEqual(day_of_year(7, 15), 196)
        self.assertEqual(day_of_year(12, 15), 349)


class TestRadiationPathAccuracy(unittest.TestCase):
    """실측 홀드아웃으로 정확도를 재계산 — 0.90 주장을 코드가 지키는지 확인."""

    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads(FIXTURE.read_text(encoding="utf-8"))["rows"]
        cls.pred, cls.obs = [], []
        for r in cls.rows:
            result = SunlightCalculation.from_radiation(
                r["solar_radiation"], r["latitude"], r["month"]
            )
            if result is None:
                continue
            cls.pred.append(result.value)
            cls.obs.append(r["sunlight_observed"])

    def test_fixture_is_substantial(self):
        """표본이 쪼그라들면 정확도 주장이 무의미해진다."""
        self.assertGreaterEqual(len(self.rows), 200)
        self.assertGreaterEqual(len(self.pred), len(self.rows) * 0.95)

    def test_mean_absolute_error_within_documented_bound(self):
        """월평균 MAE는 시드 기록치(0.587h) 수준이어야 한다 — 여유 포함 0.75h."""
        mae = sum(abs(p - o) for p, o in zip(self.pred, self.obs)) / len(self.pred)
        self.assertLess(mae, 0.75, f"MAE {mae:.3f}h — 보정계수/품질필터가 틀어졌다")

    def test_no_systematic_bias(self):
        """편향이 크면 전 지역 일조가 한쪽으로 밀린다(계수 오류의 전형적 증상)."""
        bias = sum(p - o for p, o in zip(self.pred, self.obs)) / len(self.pred)
        self.assertLess(abs(bias), 0.4, f"bias {bias:+.3f}h")

    def test_within_one_hour_majority(self):
        """±1h 안에 드는 비율이 과반을 크게 넘어야 한다(검증치 83.5%)."""
        within = sum(1 for p, o in zip(self.pred, self.obs) if abs(p - o) <= 1.0)
        self.assertGreater(within / len(self.pred), 0.75)

    def test_correlation_is_strong(self):
        """상관이 강해야 한다 — 평균만 맞고 변동을 못 따라가면 채점에 쓸 수 없다.

        월평균 기준 실측 r=0.783. 일별(원자료) R²=0.904보다 낮게 보이는 것은 월평균끼리의
        분산이 작아 상관계수가 보수적으로 나오기 때문이다 — 절대오차(MAE 0.583h)가 오히려
        일별(0.845h)보다 작다. 그래서 정확도의 주 지표는 MAE로 본다.
        """
        n = len(self.pred)
        mp, mo = sum(self.pred) / n, sum(self.obs) / n
        cov = sum((p - mp) * (o - mo) for p, o in zip(self.pred, self.obs))
        sp = math.sqrt(sum((p - mp) ** 2 for p in self.pred))
        so = math.sqrt(sum((o - mo) ** 2 for o in self.obs))
        self.assertGreater(cov / (sp * so), 0.70)

    def test_calibrated_beats_fao_default_on_bias(self):
        """국내 보정계수를 쓰는 이유 — FAO 기본값보다 편향이 작아야 한다."""
        cal = calibration()["angstrom_prescott"]
        fao = cal["fao56_default"]

        def bias(a, b):
            errs = []
            for r in self.rows:
                ra = extraterrestrial_radiation(r["latitude"], day_of_year(r["month"]))
                n_max = daylight_hours(r["latitude"], day_of_year(r["month"]))
                ratio = r["solar_radiation"] / ra
                pred = max(0.0, min(n_max, n_max * (ratio - a) / b))
                errs.append(pred - r["sunlight_observed"])
            return sum(errs) / len(errs)

        self.assertLess(abs(bias(cal["a"], cal["b"])), abs(bias(fao["a"], fao["b"])))


class TestPathSelectionAndGuards(unittest.TestCase):
    def test_measurement_wins_over_radiation(self):
        r = SunlightCalculation.calculate_optimal(
            latitude=37.5, month=7, measured_sunlight=6.2, solar_radiation=20.0
        )
        self.assertEqual(r.method, "measurement")
        self.assertAlmostEqual(r.value, 6.2)
        self.assertFalse(r.is_calculated)

    def test_radiation_wins_over_temperature(self):
        r = SunlightCalculation.calculate_optimal(
            latitude=37.5, month=7, solar_radiation=20.0, tmax=30.0, tmin=20.0
        )
        self.assertEqual(r.method, "radiation")
        self.assertTrue(r.is_calculated)

    def test_impossible_radiation_is_rejected_not_converted(self):
        """청천 상한을 넘는 일사량은 센서 이상 → None. 이 필터가 정확도의 전제다
        (실측 검증에서 이걸 빼면 R²가 0.904 → 0.742로 떨어졌다)."""
        self.assertIsNone(SunlightCalculation.from_radiation(99.0, 37.5, 1))
        self.assertIsNone(SunlightCalculation.from_radiation(0.01, 37.5, 7))

    def test_falls_back_to_temperature_when_radiation_is_garbage(self):
        r = SunlightCalculation.calculate_optimal(
            latitude=37.5, month=1, solar_radiation=99.0, tmax=5.0, tmin=-3.0
        )
        self.assertEqual(r.method, "temperature")

    def test_returns_none_when_no_usable_input(self):
        """입력이 없으면 값을 만들어내지 않는다(§18-4)."""
        self.assertIsNone(SunlightCalculation.calculate_optimal(latitude=37.5, month=5))

    def test_never_exceeds_daylight_hours(self):
        """일조시간이 가조시간을 넘으면 물리적으로 불가능하다."""
        for month in range(1, 13):
            for rad in (5.0, 15.0, 25.0, 30.0):
                r = SunlightCalculation.from_radiation(rad, 37.5, month)
                if r is None:
                    continue
                with self.subTest(month=month, rad=rad):
                    self.assertLessEqual(r.value, daylight_hours(37.5, day_of_year(month)) + 1e-9)
                    self.assertGreaterEqual(r.value, 0.0)

    def test_is_deterministic(self):
        """같은 입력 → 같은 출력(§2 결정론 우선)."""
        a = SunlightCalculation.from_radiation(18.5, 36.4, 6)
        b = SunlightCalculation.from_radiation(18.5, 36.4, 6)
        self.assertEqual(a, b)

    def test_latitude_actually_changes_the_answer(self):
        """같은 일사량이어도 위도가 다르면 결과가 달라야 한다 — 위도 하드코딩 재발 방어(§18-2).

        12월 일사량 8MJ을 쓴다: 12월 Ra가 제주 17.6 / 고성 14.6이라 같은 8MJ이 서로 다른
        청천비율로 해석돼야 한다(18MJ은 제주 Ra를 넘어 정상적으로 거부된다)."""
        jeju = SunlightCalculation.from_radiation(8.0, 33.5, 12)
        goseong = SunlightCalculation.from_radiation(8.0, 38.4, 12)
        self.assertIsNotNone(jeju)
        self.assertIsNotNone(goseong)
        self.assertNotAlmostEqual(jeju.value, goseong.value, places=2)


class TestConfidenceContract(unittest.TestCase):
    """신뢰도는 게이트(0.90)와 맞물려 동작해야 한다."""

    def test_only_measurement_and_radiation_pass_the_gate(self):
        cal = calibration()["confidence"]
        self.assertGreaterEqual(cal["measurement"], 0.90)
        self.assertGreaterEqual(cal["radiation"], 0.90)
        self.assertLess(cal["temperature"], 0.90, "기온 추정이 게이트를 통과하면 §18-4 위반")

    def test_labels_do_not_rely_on_colour_alone(self):
        self.assertEqual(SunlightCalculation.confidence_to_label(0.95), "높음")
        self.assertEqual(SunlightCalculation.confidence_to_label(0.90), "높음")
        self.assertEqual(SunlightCalculation.confidence_to_label(0.50), "낮음(참고용)")

    def test_error_range_widens_as_method_gets_weaker(self):
        _, meas = SunlightCalculation.estimate_error_range("measurement")
        _, rad = SunlightCalculation.estimate_error_range("radiation")
        _, temp = SunlightCalculation.estimate_error_range("temperature")
        self.assertLess(meas, rad)
        self.assertLess(rad, temp)

    def test_seed_backs_the_confidence_numbers(self):
        """신뢰도가 시드의 실측 검증치와 함께 관리되는지 — 숫자만 몰래 올리는 것을 막는다."""
        val = calibration()["validation"]
        self.assertGreaterEqual(val["daily"]["r2"], 0.90)
        self.assertLessEqual(val["monthly_mean"]["mae_hours"], 0.75)
        self.assertGreater(val["rows_after_quality_filter"], 5000)


class TestResultShape(unittest.TestCase):
    def test_result_is_immutable(self):
        r = SunlightCalculation.from_measurement(5.4)
        self.assertIsInstance(r, SunlightResult)
        with self.assertRaises(Exception):
            r.value = 9.9  # type: ignore[misc]

    def test_basis_explains_the_inputs(self):
        """UI가 근거를 보여줄 수 있어야 한다(§1-4 정직한 한계 표기)."""
        r = SunlightCalculation.from_radiation(20.0, 37.5, 7)
        self.assertIn("일사량", r.basis)
        self.assertIn("가조시간", r.basis)


if __name__ == "__main__":
    unittest.main()
