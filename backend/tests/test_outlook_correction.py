"""장기예보 tercile 보정 계산 검증(DB.md §8.1). 순수 함수만 — DB 불필요."""
import unittest
from decimal import Decimal

from app.services.outlook_correction import (
    INDICATOR_TO_OUTLOOK,
    apply_corrections,
    correction_delta,
)


class TestCorrectionDelta(unittest.TestCase):
    def test_equal_probabilities_yield_no_correction(self):
        """§8.1 불변식: 33/33/33이면 보정치 0 — 정보가 없으면 평년치를 움직이지 않는다."""
        delta = correction_delta(
            Decimal("33.3"), Decimal("33.3"), Decimal("24.9"), Decimal("25.9")
        )
        self.assertEqual(delta, Decimal(0))

    def test_above_skew_shifts_upward(self):
        # 실측값(고창 8월 기온): 낮음10/비슷30/높음60, 비슷구간 24.9~25.9 → δ=0.5
        delta = correction_delta(
            Decimal("10"), Decimal("60"), Decimal("24.9"), Decimal("25.9")
        )
        self.assertEqual(delta, Decimal("0.25"))  # (0.6-0.1) × 0.5

    def test_below_skew_shifts_downward(self):
        delta = correction_delta(
            Decimal("60"), Decimal("10"), Decimal("24.9"), Decimal("25.9")
        )
        self.assertEqual(delta, Decimal("-0.25"))

    def test_rainfall_uses_its_own_wide_interval(self):
        # 실측값(고창 8월 강수): 적음30/비슷50/많음20, 구간 209.3~374.4 → δ=82.55
        delta = correction_delta(
            Decimal("30"), Decimal("20"), Decimal("209.3"), Decimal("374.4")
        )
        self.assertEqual(delta, Decimal("-8.255"))  # (0.2-0.3) × 82.55

    def test_missing_inputs_mean_no_correction(self):
        self.assertIsNone(correction_delta(None, Decimal("60"), Decimal(1), Decimal(2)))
        self.assertIsNone(correction_delta(Decimal("10"), Decimal("60"), None, Decimal(2)))

    def test_zero_width_interval_is_treated_as_no_signal(self):
        self.assertIsNone(
            correction_delta(Decimal("10"), Decimal("60"), Decimal("25"), Decimal("25"))
        )


class TestIndicatorMapping(unittest.TestCase):
    def test_only_temp_and_rainfall_are_corrected(self):
        """§8.1 B3: outlook은 기온·강수만 제공 — 야간최저·일조·토양은 보정 대상 아님."""
        # 강수는 월/일 단위로 분리돼 있고, 3개월전망은 월 신호이므로 월 지표만 대응한다.
        self.assertEqual(set(INDICATOR_TO_OUTLOOK), {"temp_day", "rainfall_monthly"})
        self.assertNotIn("rainfall_daily", INDICATOR_TO_OUTLOOK)
        for uncovered in ("temp_night_min", "sunlight", "ph", "ec", "p2o5", "organic"):
            self.assertNotIn(uncovered, INDICATOR_TO_OUTLOOK)


class TestApplyCorrections(unittest.TestCase):
    def setUp(self):
        self.values: dict[str, float | Decimal | None] = {
            "temp_day": Decimal("25.4"),
            "temp_night_min": Decimal("18"),
            "rainfall_monthly": Decimal("296.6"),
            "ph": Decimal("6.3"),
        }

    def test_applies_only_matching_month(self):
        corrections = {(8, "temp_day"): Decimal("0.25")}
        corrected, applied = apply_corrections(self.values, corrections, month=8)
        self.assertEqual(corrected["temp_day"], Decimal("25.65"))
        self.assertEqual(applied["temp_day"], (Decimal("25.4"), Decimal("0.25")))

        # 다른 달엔 적용되지 않는다
        corrected9, applied9 = apply_corrections(self.values, corrections, month=9)
        self.assertEqual(corrected9["temp_day"], Decimal("25.4"))
        self.assertEqual(applied9, {})

    def test_uncovered_indicators_pass_through_untouched(self):
        corrections = {(8, "temp_day"): Decimal("0.25")}
        corrected, applied = apply_corrections(self.values, corrections, month=8)
        self.assertEqual(corrected["temp_night_min"], Decimal("18"))  # 보정 대상 아님
        self.assertEqual(corrected["ph"], Decimal("6.3"))
        self.assertNotIn("temp_night_min", applied)

    def test_missing_baseline_is_not_invented(self):
        """평년치가 없는 지표에 보정치만으로 값을 만들어내지 않는다(§12 결측 방어)."""
        values: dict[str, float | Decimal | None] = {"temp_day": None}
        corrected, applied = apply_corrections(values, {(8, "temp_day"): Decimal("0.25")}, 8)
        self.assertIsNone(corrected["temp_day"])
        self.assertEqual(applied, {})

    def test_no_corrections_returns_values_unchanged(self):
        corrected, applied = apply_corrections(self.values, {}, month=8)
        self.assertEqual(corrected, self.values)
        self.assertEqual(applied, {})

    def test_does_not_mutate_input(self):
        corrections = {(8, "temp_day"): Decimal("0.25")}
        apply_corrections(self.values, corrections, month=8)
        self.assertEqual(self.values["temp_day"], Decimal("25.4"))


if __name__ == "__main__":
    unittest.main()
