"""단기 탭 지속 위험 판정 검증(DB 없는 순수부).

"봄철 야간저온 3일 지속"이 A씨 사례의 실패 원인이라, 하루짜리 노이즈와 지속 위험을
구분하는 규칙이 이 탭의 핵심이다(PRD.md §4.5, §7-4).
"""
import unittest
from datetime import date, datetime
from decimal import Decimal

from app.infra.public_api.forecast_client import KST, DailyForecast
from app.services.short_term_service import _to_snapshot_rows, persistent_risks


def _day(d: str, *flags: str) -> dict[str, object]:
    return {"target_date": d, "risk_flags": list(flags)}


def _forecast(**over: object) -> DailyForecast:
    base: dict[str, object] = {
        "target_date": date(2026, 8, 4),
        "temp_avg": Decimal("31.3"),
        "temp_max": Decimal("38"),
        "temp_night_min": Decimal("27"),
        "rainfall": Decimal("0"),
        "precip_prob_max": 20,
        "humidity_max": 80,
        "hourly_temp": [{"h": 15, "t": "38"}],
        "is_partial": False,
    }
    base.update(over)
    return DailyForecast(**base)  # type: ignore[arg-type]


class TestToSnapshotRows(unittest.TestCase):
    """DailyForecast → weather_snapshot 행 매핑. 컬럼을 빠뜨리면 조용히 NULL로 저장된다."""

    def test_maps_new_temperature_columns(self):
        row = _to_snapshot_rows(7, datetime(2026, 8, 4, 14, tzinfo=KST), [_forecast()])[0]
        self.assertEqual(row["temp_avg"], Decimal("31.3"))
        self.assertEqual(row["temp_max"], Decimal("38"))
        self.assertEqual(row["temp_night_min"], Decimal("27"))
        self.assertEqual(row["hourly_temp"], [{"h": 15, "t": "38"}])

    def test_partial_flag_lands_in_is_imputed(self):
        """부분 표본으로 낸 집계는 §12의 "대체됨"이다 — 기존 컬럼을 재사용한다."""
        rows = _to_snapshot_rows(
            7,
            datetime(2026, 8, 4, 14, tzinfo=KST),
            [_forecast(is_partial=True), _forecast(target_date=date(2026, 8, 5))],
        )
        self.assertEqual([r["is_imputed"] for r in rows], [True, False])

    def test_sunlight_stays_null(self):
        """단기예보는 일조를 주지 않는다 — 0으로 채우면 '일조 없음'으로 오해된다."""
        row = _to_snapshot_rows(7, datetime(2026, 8, 4, 14, tzinfo=KST), [_forecast()])[0]
        self.assertIsNone(row["sunlight"])


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
        days = [_day("2026-04-01", "rainfall_daily:outside_allowed"), _day("2026-04-02")]
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
            _day("2026-04-01", "temp_night_min:outside_allowed", "rainfall_daily:outside_allowed"),
            _day("2026-04-02", "temp_night_min:outside_allowed", "rainfall_daily:outside_allowed"),
            _day("2026-04-03", "temp_night_min:outside_allowed"),
        ]
        risks = persistent_risks(days)
        self.assertEqual([r["flag"] for r in risks], [
            "temp_night_min:outside_allowed",
            "rainfall_daily:outside_allowed",
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
