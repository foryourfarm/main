"""기상청 3개월전망 RSS 파싱·탐색 검증. 네트워크 없이 실제 KMA XML fixture만 사용.

fixture는 2026-07-23 실제 발표분에서 권역 2개(전북자치도·강원도 영동)만 남긴 것이다.
"""
import unittest
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree

from app.infra.public_api.outlook_client import (
    OutlookFetchError,
    _category,
    _parse_range,
    _target_months,
    fetch_latest_outlook,
    parse_outlook_xml,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_outlook_rss.xml"
PUBLISHED = date(2026, 7, 23)

# 실측된 실패 케이스: 없는 날짜인데 HTTP 200으로 HTML 에러페이지가 온다.
HTML_ERROR_PAGE = b'<!DOCTYPE html>\r\n<html lang="ko">\r\n<head><title>\xea\xb8\xb0\xec\x83\x81\xec\xb2\xad</title></head>\r\n<body>not found</body>\r\n</html>'


class FakeResponse:
    def __init__(self, content: bytes, status_code: int = 200):
        self.content = content
        self.status_code = status_code


class TestParseRealFixture(unittest.TestCase):
    def setUp(self):
        self.records = parse_outlook_xml(FIXTURE.read_bytes(), PUBLISHED)

    def test_record_count_is_zones_times_months_times_indicators(self):
        # 권역 2 × 대상월 3 × 지표 2(기온·강수)
        self.assertEqual(len(self.records), 12)

    def test_temperature_tercile_matches_source(self):
        aug = next(
            r for r in self.records
            if r.zone_name == "전북자치도" and r.indicator == "temp"
            and r.target_month == date(2026, 8, 1)
        )
        self.assertEqual(aug.prob_below, Decimal("10"))
        self.assertEqual(aug.prob_normal, Decimal("30"))
        self.assertEqual(aug.prob_above, Decimal("60"))
        self.assertEqual(aug.category, "ABOVE")  # 최대 확률 tercile
        self.assertEqual(aug.normal_value, Decimal("25.4"))
        self.assertEqual(aug.similar_low, Decimal("24.9"))
        self.assertEqual(aug.similar_high, Decimal("25.9"))
        self.assertEqual(aug.published_at.date(), PUBLISHED)

    def test_rainfall_section_is_parsed_too(self):
        rain = [r for r in self.records if r.indicator == "rainfall"]
        self.assertEqual(len(rain), 6)  # 권역 2 × 월 3
        self.assertTrue(all(r.prob_normal is not None for r in rain))

    def test_target_months_are_normalized_to_first_day(self):
        self.assertEqual(
            sorted({r.target_month for r in self.records}),
            [date(2026, 8, 1), date(2026, 9, 1), date(2026, 10, 1)],
        )

    def test_is_deterministic(self):
        again = parse_outlook_xml(FIXTURE.read_bytes(), PUBLISHED)
        self.assertEqual(self.records, again)


class TestValidationDefenses(unittest.TestCase):
    """HTML 에러페이지는 두 경로로 걸린다: XML 파싱 실패(ParseError) 또는 루트태그 불일치(ValueError).

    실제 22KB 응답은 닫히지 않은 태그가 있어 ParseError였고, 아래 축약본은 XML로도
    유효해 루트태그에서 걸린다. 어느 쪽이든 적재되지 않는 것이 요구사항이다.
    """

    def test_html_error_page_is_rejected(self):
        with self.assertRaises((ElementTree.ParseError, ValueError)):
            parse_outlook_xml(HTML_ERROR_PAGE, PUBLISHED)

    def test_malformed_html_is_rejected(self):
        with self.assertRaises(ElementTree.ParseError):
            parse_outlook_xml(b"<html><head><title>x</head></html>", PUBLISHED)

    def test_unexpected_root_tag_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_outlook_xml(b"<notrss><local_ta/></notrss>", PUBLISHED)

    def test_missing_zone_blocks_are_rejected(self):
        with self.assertRaises(ValueError):
            parse_outlook_xml(b"<rss><channel/></rss>", PUBLISHED)


class TestTargetMonths(unittest.TestCase):
    def test_covers_next_three_months(self):
        self.assertEqual(
            _target_months(date(2026, 7, 23)),
            [date(2026, 8, 1), date(2026, 9, 1), date(2026, 10, 1)],
        )

    def test_rolls_over_year_end(self):
        # 11월 발표 → 12월·다음해 1월·2월
        self.assertEqual(
            _target_months(date(2026, 11, 23)),
            [date(2026, 12, 1), date(2027, 1, 1), date(2027, 2, 1)],
        )


class TestCategory(unittest.TestCase):
    def test_picks_max_probability(self):
        self.assertEqual(_category(Decimal(10), Decimal(30), Decimal(60)), "ABOVE")
        self.assertEqual(_category(Decimal(50), Decimal(30), Decimal(20)), "BELOW")

    def test_tie_falls_back_to_normal(self):
        self.assertEqual(_category(Decimal(40), Decimal(20), Decimal(40)), "NORMAL")

    def test_all_missing_is_normal(self):
        self.assertEqual(_category(None, None, None), "NORMAL")


class TestParseRange(unittest.TestCase):
    def test_parses_tilde_range(self):
        self.assertEqual(_parse_range("24.6~25.6"), (Decimal("24.6"), Decimal("25.6")))

    def test_handles_negative_bounds(self):
        self.assertEqual(_parse_range("-2.1~0.4"), (Decimal("-2.1"), Decimal("0.4")))

    def test_unexpected_format_is_missing_not_error(self):
        self.assertEqual(_parse_range("알 수 없음"), (None, None))
        self.assertEqual(_parse_range(None), (None, None))


class TestFetchProbesShiftedReleaseDate(unittest.TestCase):
    """2026-05 실제 사례: 23일이 아니라 22일에 발표됐고 23·24일은 HTML을 반환했다."""

    def test_falls_back_to_day_22_when_23_is_html(self):
        xml = FIXTURE.read_bytes()
        seen: list[str] = []

        def fake_get(url: str, timeout: float = 0):
            stamp = url.rsplit("_", 1)[-1].removesuffix(".xml")
            seen.append(stamp)
            if stamp == "20260522":
                return FakeResponse(xml)
            return FakeResponse(HTML_ERROR_PAGE)

        with patch("httpx.get", side_effect=fake_get):
            records, published = fetch_latest_outlook(date(2026, 5, 31))

        self.assertEqual(published, date(2026, 5, 22))
        self.assertTrue(records)
        self.assertIn("20260523", seen)  # 원칙일을 먼저 시도했음
        self.assertIn("20260522", seen)

    def test_raises_when_nothing_valid_found(self):
        with patch("httpx.get", return_value=FakeResponse(HTML_ERROR_PAGE)):
            with self.assertRaises(OutlookFetchError):
                fetch_latest_outlook(date(2026, 5, 31))

    def test_does_not_request_future_dates(self):
        seen: list[str] = []

        def fake_get(url: str, timeout: float = 0):
            seen.append(url.rsplit("_", 1)[-1].removesuffix(".xml"))
            return FakeResponse(HTML_ERROR_PAGE)

        # 7월 24일 기준이면 7월 25일 이후 발표분은 아직 없다.
        with patch("httpx.get", side_effect=fake_get):
            with self.assertRaises(OutlookFetchError):
                fetch_latest_outlook(date(2026, 7, 24))
        self.assertTrue(all(s <= "20260724" for s in seen), seen)


if __name__ == "__main__":
    unittest.main()
