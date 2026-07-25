"""단기 탭 지속 위험 판정 검증(DB 없는 순수부).

"봄철 야간저온 3일 지속"이 A씨 사례의 실패 원인이라, 하루짜리 노이즈와 지속 위험을
구분하는 규칙이 이 탭의 핵심이다(PRD.md §4.5, §7-4).
"""
import unittest

from app.services.short_term_service import persistent_risks


def _day(d: str, *flags: str) -> dict[str, object]:
    return {"target_date": d, "risk_flags": list(flags)}


class TestPersistentRisks(unittest.TestCase):
    def test_flags_repeated_risk(self):
        days = [
            _day("2026-04-01", "temp_night_min:outside_allowed"),
            _day("2026-04-02", "temp_night_min:outside_allowed"),
            _day("2026-04-03", "temp_night_min:outside_allowed"),
        ]
        risks = persistent_risks(days)
        self.assertEqual(len(risks), 1)
        self.assertEqual(risks[0]["flag"], "temp_night_min:outside_allowed")
        self.assertEqual(risks[0]["days"], 3)
        self.assertEqual(risks[0]["dates"], ["2026-04-01", "2026-04-02", "2026-04-03"])

    def test_single_day_risk_is_not_persistent(self):
        """하루만 스치는 값으로 경보를 울리면 신뢰를 잃는다."""
        days = [_day("2026-04-01", "rainfall:outside_allowed"), _day("2026-04-02")]
        self.assertEqual(persistent_risks(days), [])

    def test_only_outside_allowed_counts(self):
        """결측(missing)은 위험이 아니라 데이터 없음이다 — 경보 대상이 아니다."""
        days = [
            _day("2026-04-01", "temp_night_min:missing", "sunlight:missing"),
            _day("2026-04-02", "temp_night_min:missing", "sunlight:missing"),
        ]
        self.assertEqual(persistent_risks(days), [])

    def test_soil_risks_are_excluded(self):
        """토양은 며칠 안에 변하지 않아 매일 뜬다 — "유기물 5일 지속"은 정보가 없는 경보다.

        실측 사례: 순천 사과밭 조회 시 organic/p2o5만 5일 지속으로 올라와 기상 위험을 가렸다.
        """
        days = [
            _day("2026-07-25", "organic:outside_allowed", "p2o5:outside_allowed"),
            _day("2026-07-26", "organic:outside_allowed", "p2o5:outside_allowed"),
            _day("2026-07-27", "organic:outside_allowed", "p2o5:outside_allowed"),
        ]
        self.assertEqual(persistent_risks(days), [])

    def test_weather_risk_survives_alongside_soil_risk(self):
        days = [
            _day("2026-04-01", "organic:outside_allowed", "temp_night_min:outside_allowed"),
            _day("2026-04-02", "organic:outside_allowed", "temp_night_min:outside_allowed"),
        ]
        risks = persistent_risks(days)
        self.assertEqual([r["flag"] for r in risks], ["temp_night_min:outside_allowed"])

    def test_multiple_risks_sorted_by_duration(self):
        days = [
            _day("2026-04-01", "temp_night_min:outside_allowed", "rainfall:outside_allowed"),
            _day("2026-04-02", "temp_night_min:outside_allowed", "rainfall:outside_allowed"),
            _day("2026-04-03", "temp_night_min:outside_allowed"),
        ]
        risks = persistent_risks(days)
        self.assertEqual([r["flag"] for r in risks], [
            "temp_night_min:outside_allowed",
            "rainfall:outside_allowed",
        ])
        self.assertEqual([r["days"] for r in risks], [3, 2])

    def test_duplicate_flags_within_a_day_count_once(self):
        """같은 날 같은 플래그가 중복돼도 하루로 센다(지속 일수가 부풀지 않게)."""
        days = [
            _day("2026-04-01", "temp_night_min:outside_allowed", "temp_night_min:outside_allowed"),
            _day("2026-04-02", "temp_night_min:outside_allowed"),
        ]
        self.assertEqual(persistent_risks(days)[0]["days"], 2)

    def test_empty_input_is_safe(self):
        self.assertEqual(persistent_risks([]), [])

    def test_is_deterministic(self):
        days = [
            _day("2026-04-01", "temp_night_min:outside_allowed"),
            _day("2026-04-02", "temp_night_min:outside_allowed"),
        ]
        self.assertEqual(persistent_risks(days), persistent_risks(days))


if __name__ == "__main__":
    unittest.main()
