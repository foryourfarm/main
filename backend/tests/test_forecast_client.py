"""단기예보 파싱·발표시각 규칙 검증. 네트워크 불필요.

items 샘플은 2026-07-25 순천 격자(70,70) 실제 응답 형태를 그대로 따른다.
"""
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.infra.public_api.forecast_client import (
    KST,
    fold_daily,
    latest_base,
    latest_base_at,
    parse_number,
)


def _item(d: str, t: str, cat: str, val: str) -> dict[str, object]:
    return {"baseDate": "20260724", "baseTime": "2300", "category": cat,
            "fcstDate": d, "fcstTime": t, "fcstValue": val, "nx": 70, "ny": 70}


class TestParseNumber(unittest.TestCase):
    def test_plain_numbers(self):
        self.assertEqual(parse_number("26"), Decimal("26"))
        self.assertEqual(parse_number("0.4"), Decimal("0.4"))

    def test_no_value_tokens_become_zero(self):
        """실측: PCP/SNO는 숫자가 아니라 '강수없음'/'적설없음'으로 온다 — 없다는 뜻이니 0."""
        self.assertEqual(parse_number("강수없음"), Decimal(0))
        self.assertEqual(parse_number("적설없음"), Decimal(0))
        self.assertEqual(parse_number(""), Decimal(0))

    def test_range_and_unit_notation_takes_leading_number(self):
        """'1.0mm 미만', '30.0~50.0mm' 같은 구간·단위 표기도 온다."""
        self.assertEqual(parse_number("1.0mm 미만"), Decimal("1.0"))
        self.assertEqual(parse_number("30.0~50.0mm"), Decimal("30.0"))

    def test_unparseable_is_missing_not_crash(self):
        self.assertIsNone(parse_number("알수없음"))
        self.assertIsNone(parse_number(None))


class TestLatestBase(unittest.TestCase):
    def test_picks_most_recent_published_slot(self):
        # 14:30 → 45분 여유를 빼면 13:45 → 11시 발표가 최신
        self.assertEqual(latest_base(datetime(2026, 7, 25, 14, 30, tzinfo=KST)), ("20260725", "1100"))

    def test_waits_for_publish_lag(self):
        """14:10은 14시 발표가 아직 안 올라왔을 수 있어 11시분을 쓴다."""
        self.assertEqual(latest_base(datetime(2026, 7, 25, 14, 10, tzinfo=KST)), ("20260725", "1100"))

    def test_after_midnight_falls_back_to_previous_day(self):
        # 00:30 → 여유 빼면 전날 23:45 → 전날 23시 발표
        self.assertEqual(latest_base(datetime(2026, 7, 25, 0, 30, tzinfo=KST)), ("20260724", "2300"))

    def test_is_deterministic(self):
        moment = datetime(2026, 7, 25, 9, 0, tzinfo=KST)
        self.assertEqual(latest_base(moment), latest_base(moment))


class TestLatestBaseAt(unittest.TestCase):
    """캐시 신선도 판정용. `latest_base`와 같은 슬롯을 datetime으로 돌려줘야 한다."""

    def test_matches_latest_base(self):
        moment = datetime(2026, 7, 25, 14, 30, tzinfo=KST)
        self.assertEqual(latest_base_at(moment), datetime(2026, 7, 25, 11, 0, tzinfo=KST))

    def test_after_midnight_falls_back_to_previous_day(self):
        moment = datetime(2026, 7, 25, 0, 30, tzinfo=KST)
        self.assertEqual(latest_base_at(moment), datetime(2026, 7, 24, 23, 0, tzinfo=KST))

    def test_cached_stays_fresh_across_whole_publish_gap(self):
        """회귀: 벽시계 3시간 TTL이면 발표 후 3시간부터 매 요청이 같은 발표분을 재조회했다.

        11시 발표를 받아둔 캐시는 다음 발표(14시)가 올라오기 전까지 계속 신선해야 한다.
        """
        cached_base_at = datetime(2026, 7, 25, 11, 0, tzinfo=KST)
        for hour, minute in ((11, 50), (13, 0), (14, 30), (14, 44)):
            moment = datetime(2026, 7, 25, hour, minute, tzinfo=KST)
            self.assertGreaterEqual(cached_base_at, latest_base_at(moment), f"{hour}:{minute}")
        # 14시 발표가 올라오면(14:45 이후) 비로소 만료된다.
        stale_at = datetime(2026, 7, 25, 14, 45, tzinfo=KST)
        self.assertLess(cached_base_at, latest_base_at(stale_at))


class TestFoldDaily(unittest.TestCase):
    def test_folds_long_format_into_days(self):
        items = [
            _item("20260725", "0000", "TMP", "26"),
            _item("20260725", "0300", "TMP", "24"),
            _item("20260725", "0600", "TMN", "23"),
            _item("20260725", "0000", "PCP", "강수없음"),
            _item("20260725", "0300", "PCP", "1.5"),
            _item("20260725", "0000", "POP", "0"),
            _item("20260725", "0300", "POP", "60"),
            _item("20260725", "0000", "REH", "95"),
            _item("20260726", "0000", "TMP", "20"),
            _item("20260726", "0600", "TMN", "15"),
        ]
        days = fold_daily(items)
        self.assertEqual([d.target_date for d in days], [date(2026, 7, 25), date(2026, 7, 26)])
        first = days[0]
        self.assertEqual(first.temp_avg, Decimal("25.0"))  # (26+24)/2
        self.assertEqual(first.temp_night_min, Decimal("23"))  # TMN 사용
        self.assertEqual(first.rainfall, Decimal("1.5"))  # 강수없음(0) + 1.5
        self.assertEqual(first.precip_prob_max, 60)  # 그날 최대
        self.assertEqual(first.humidity_max, 95)

    def test_night_min_falls_back_to_hourly_min(self):
        """첫날은 TMN 발표시각이 지나 빠질 수 있다 — TMP 최저로 폴백해야 한다."""
        items = [_item("20260725", "0000", "TMP", "26"), _item("20260725", "0300", "TMP", "21")]
        day = fold_daily(items)[0]
        self.assertEqual(day.temp_night_min, Decimal("21"))

    def test_ignores_unused_categories(self):
        items = [_item("20260725", "0000", "WSD", "0.4"), _item("20260725", "0000", "VEC", "270")]
        self.assertEqual(fold_daily(items), [])

    def test_missing_category_yields_none_not_zero(self):
        """강수 항목이 아예 없으면 0이 아니라 결측이어야 한다(0mm와 '모름'은 다르다)."""
        items = [_item("20260725", "0000", "TMP", "26")]
        day = fold_daily(items)[0]
        self.assertIsNone(day.rainfall)
        self.assertIsNone(day.precip_prob_max)

    def test_is_deterministic(self):
        items = [_item("20260725", "0000", "TMP", "26"), _item("20260725", "0300", "TMP", "24")]
        self.assertEqual(fold_daily(items), fold_daily(items))


class TestTimezone(unittest.TestCase):
    def test_kst_is_utc_plus_nine(self):
        self.assertEqual(KST.utcoffset(None), timedelta(hours=9))
        self.assertNotEqual(KST, timezone.utc)


if __name__ == "__main__":
    unittest.main()
