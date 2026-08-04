"""app.infra.public_api 파싱/방어 로직 테스트. 네트워크·API키 불필요(캔드 XML만 사용).

soil_profile/soil_exam의 SUCCESS_XML은 각 API의 공식 OPEN API 기술명세서(ver1.0)에
실린 요청/응답 예제를 그대로 사용한다 — 실제 스펙과 어긋나지 않는지 검증하는 목적.
"""

import unittest
from unittest.mock import patch

from app.infra.public_api.base import PublicApiError, fetch_items
from app.infra.public_api.soil_exam_client import get_soil_exam, get_soil_exam_list
from app.infra.public_api import soil_profile_client, weather_client
from app.infra.public_api.soil_profile_client import get_soil_profile
from app.infra.public_api.weather_client import WeatherObservation

SUCCESS_XML = """<response>
  <header><Result_Code>200</Result_Code><Result_Msg>OK</Result_Msg></header>
  <body><items>
    <item><stnCode>abcd</stnCode><obsDate>20260101</obsDate><avgTemp>-2.3</avgTemp><sumRn>0</sumRn></item>
    <item><stnCode>bcde</stnCode><obsDate>20260102</obsDate><avgTemp>1.5</avgTemp><sumRn>-999</sumRn></item>
  </items></body>
</response>"""

ERROR_XML = """<response>
  <header><Result_Code>22</Result_Code><Result_Msg>LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR</Result_Msg></header>
  <body></body>
</response>"""

# 기술명세서 ver1.0, 요청/응답 메시지 예제 그대로(§3.1.d)
SOIL_PROFILE_XML = """<?xml version="1.0" encoding="UTF-8" standalone="true"?>
<response>
<header><Result_Code>200</Result_Code><Result_Msg>OK</Result_Msg></header>
<body><items><item>
<PNU_Cd>4215034022100050000</PNU_Cd>
<Deepsoil_Qlt_Cd>04</Deepsoil_Qlt_Cd>
<Deepsoil_Ston_Cd>02</Deepsoil_Ston_Cd>
<Soilslope_Cd>03</Soilslope_Cd>
</item></items></body>
</response>"""
# 🔴 이 픽스처는 2026-08-05까지 `*_Code`로 적혀 있었다. 실제 응답은 `*_Cd`인데 픽스처가 코드의
# 오해를 그대로 베껴 써서, **운영에서 전 호출이 결측으로 새는 동안 테스트는 계속 초록이었다.**
# 위 XML은 실호출 응답을 그대로 옮긴 것이다(PNU 4215034022100050000, 2026-08-05).

# 기술명세서 ver1.0, getSoilExam 응답 예제 그대로
SOIL_EXAM_XML = """<?xml version="1.0" encoding="UTF-8" standalone="true"?>
<response>
<header><Result_Code>200</Result_Code><Result_Msg>OK</Result_Msg></header>
<body><items><item>
<PNU_Code>4215034022100050000</PNU_Code>
<Any_Year>2019</Any_Year>
<Exam_Day>20190101</Exam_Day>
<Exam_Type>1</Exam_Type>
<Pnu_Nm>강원도 강릉시 강동면 모전리 5번지</Pnu_Nm>
<ACID>6.9</ACID>
<VLDPHA>36.2</VLDPHA>
<VLDSIA>72.1</VLDSIA>
<OM>13.2</OM>
<POSIFERT_MG>1.7</POSIFERT_MG>
<POSIFERT_K>0.19</POSIFERT_K>
<POSIFERT_CA>4.9</POSIFERT_CA>
<SELC>0.29</SELC>
</item></items></body>
</response>"""

# 기술명세서 ver1.0, getSoilExamList 응답 예제 중 이상치(pH 20) 하나를 섞어 방어 로직 검증
SOIL_EXAM_LIST_XML = """<?xml version="1.0" encoding="UTF-8" standalone="true"?>
<response>
<header><Result_Code>200</Result_Code><Result_Msg>OK</Result_Msg></header>
<body><Rcdcnt>2</Rcdcnt><Page_No>1</Page_No><Total_Count>2</Total_Count>
<items>
<item><No>1</No><BJD_Code>4215034022</BJD_Code><Any_Year>2019</Any_Year><Exam_Day>20190101</Exam_Day>
<Exam_Type>1</Exam_Type><Pnu_Nm>강원도 강릉시 강동면 모전리 5번지</Pnu_Nm>
<ACID>6.9</ACID><VLDPHA>36.2</VLDPHA><VLDSIA>72.1</VLDSIA><OM>13.2</OM>
<POSIFERT_MG>1.7</POSIFERT_MG><POSIFERT_K>0.19</POSIFERT_K><POSIFERT_CA>4.9</POSIFERT_CA><SELC>0.29</SELC></item>
<item><No>2</No><BJD_Code>4215034022</BJD_Code><Any_Year>2019</Any_Year><Exam_Day>20190201</Exam_Day>
<Exam_Type>1</Exam_Type><Pnu_Nm>강원도 강릉시 강동면 모전리 6번지</Pnu_Nm>
<ACID>20</ACID><VLDPHA>35.5</VLDPHA><VLDSIA>70.3</VLDSIA><OM>6.7</OM>
<POSIFERT_MG>2.5</POSIFERT_MG><POSIFERT_K>0.21</POSIFERT_K><POSIFERT_CA>5.0</POSIFERT_CA><SELC>0.13</SELC></item>
</items></body>
</response>"""


class FakeResponse:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self) -> None:
        pass


class TestFetchItems(unittest.TestCase):
    def test_parses_items_on_success(self):
        with patch("httpx.get", return_value=FakeResponse(SUCCESS_XML)):
            items = fetch_items("http://example.test", {})
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["obsDate"], "20260101")

    def test_raises_on_error_code(self):
        with patch("httpx.get", return_value=FakeResponse(ERROR_XML)):
            with self.assertRaises(PublicApiError) as ctx:
                fetch_items("http://example.test", {})
        self.assertEqual(ctx.exception.code, "22")


class TestWeatherObservationOutlierGuard(unittest.TestCase):
    """농업기상 V3 관측값의 경계 방어(§12). 결측·이상치를 None으로 눌러 산출이 죽지 않게 한다."""

    @staticmethod
    def _obs(**overrides):
        base = dict(
            point_code="230802A001",
            point_name="영월군 영월읍",
            obs_date="2024-07-01",
            temp_avg=25.6,
            temp_max=31.7,
            temp_min=20.6,
            humidity=79.4,
            rainfall=0.0,
            sunlight_hours=None,
            solar_radiation=18.82,
        )
        return WeatherObservation(**{**base, **overrides})

    def test_negative_rainfall_becomes_none(self):
        """-999는 공공데이터 결측 관례값이다. 강수 0mm로 오해하면 안 된다."""
        self.assertIsNone(self._obs(rainfall=-999).rainfall)

    def test_valid_rainfall_kept(self):
        """0mm는 결측이 아니라 '비가 안 왔다'는 정보다."""
        self.assertEqual(self._obs(rainfall=0).rainfall, 0)

    def test_impossible_temperature_becomes_none(self):
        self.assertIsNone(self._obs(temp_max=-999).temp_max)
        self.assertIsNone(self._obs(temp_min=999).temp_min)
        self.assertEqual(self._obs(temp_min=-30.0).temp_min, -30.0)  # 국내 최저기온 범위 내

    def test_impossible_humidity_becomes_none(self):
        self.assertIsNone(self._obs(humidity=-1).humidity)
        self.assertIsNone(self._obs(humidity=101).humidity)
        self.assertEqual(self._obs(humidity=100).humidity, 100)

    def test_negative_radiation_becomes_none(self):
        self.assertIsNone(self._obs(solar_radiation=-1).solar_radiation)


class TestWeatherClientRequestShape(unittest.TestCase):
    """요청 형식은 실호출로 확정한 것이라 회귀하면 조용히 201/204가 난다.

    인증키를 주입하는 이유: `_fetch_page`는 키가 없으면 호출 전에 예외를 던진다. 그러면
    이 테스트들이 `.env` 존재 여부에 따라 통과/실패해 CI에서 깨진다 — 테스트는 환경이
    아니라 코드를 검증해야 한다(실제로 깨끗한 체크아웃에서 3건이 실패했다).
    """

    def setUp(self):
        self._keys = patch.object(
            weather_client, "_service_keys", lambda: ["dummy-key"]
        )
        self._keys.start()
        self.addCleanup(self._keys.stop)

    def test_period_dates_are_hyphenated(self):
        """명세서는 YYYYMMDD로 적었지만 실제로는 하이픈이 필요하다(없으면 201)."""
        _hyphenate = weather_client._hyphenate

        self.assertEqual(_hyphenate("20240701"), "2024-07-01")
        self.assertEqual(_hyphenate("2024-07-01"), "2024-07-01")

    def test_bad_date_is_rejected_early(self):
        """형식이 틀리면 API를 부르기 전에 잡는다 — 쿼터를 낭비하지 않는다."""
        _hyphenate = weather_client._hyphenate

        for bad in ("2024-7-1", "240701", ""):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                _hyphenate(bad)

    def test_pagination_walks_until_short_page(self):
        """Page_Size를 넘는 결과가 잘리지 않아야 한다(실측: rcdcnt=100 vs total=6551)."""
        pages = [
            [{"stn_Cd": f"S{i}", "date": "2024-07-01"} for i in range(3)],
            [{"stn_Cd": "S9", "date": "2024-07-02"}],  # 짧은 페이지 = 끝
        ]
        calls: list[str] = []

        def fake_fetch_items(url, params, **kwargs):
            calls.append(params["Page_No"])
            idx = int(params["Page_No"]) - 1
            return pages[idx] if idx < len(pages) else []

        with patch.object(weather_client, "fetch_items", fake_fetch_items):
            rows = weather_client.get_monthly_daily_weather("2024", "07", page_size=3)

        self.assertEqual(len(rows), 4)
        self.assertEqual(calls, ["1", "2"])

    def test_pagination_stops_at_max_pages(self):
        """응답이 계속 가득 차 와도 무한 루프로 쿼터를 소진하지 않는다."""
        def always_full(url, params, **kwargs):
            return [{"stn_Cd": "S", "date": "2024-07-01"}] * 2

        with patch.object(weather_client, "fetch_items", always_full):
            rows = weather_client.get_monthly_daily_weather("2024", "07", page_size=2)
        self.assertEqual(len(rows), 2 * weather_client.MAX_PAGES)

    def test_month_is_zero_padded(self):
        """search_Month는 2자리다 — "7"을 그대로 보내면 응답이 비거나 201이 난다."""
        seen: dict[str, str] = {}

        def capture(url, params, **kwargs):
            seen.update(params)
            return []

        with patch.object(weather_client, "fetch_items", capture):
            weather_client.get_monthly_daily_weather("2024", "7")
        self.assertEqual(seen["search_Month"], "07")


class TestSoilProfileClient(unittest.TestCase):
    def test_parses_official_example_and_maps_codes(self):
        with patch("httpx.get", return_value=FakeResponse(SOIL_PROFILE_XML)):
            profile = get_soil_profile("4215034022100050000")
        self.assertIsNotNone(profile)
        self.assertEqual(profile.pnu_code, "4215034022100050000")
        self.assertEqual(profile.deepsoil_texture, "식양질")  # 04
        self.assertEqual(profile.deepsoil_gravel, "있음_15-35%")  # 02
        self.assertEqual(profile.soil_slope, "경사_7-15%")  # 03

    def test_url_carries_the_v2_segment(self):
        """`/V2` 없는 경로는 NO_OPENAPI_SERVICE_ERROR다 — 실호출로 확인(2026-08-05).

        명세서(`soilV3_API-Guide.md`)는 `/V3`로 적지만 `/V3`도 응답하지 않는다. 명세서를 근거로
        되돌리는 것을 막기 위해 경로를 테스트로 못박는다.
        """
        self.assertIn("/SoilCharacSctnn/V2/", soil_profile_client.BASE_URL)


class TestSoilExamClient(unittest.TestCase):
    def test_get_soil_exam_parses_official_example(self):
        with patch("httpx.get", return_value=FakeResponse(SOIL_EXAM_XML)):
            exam = get_soil_exam("4215034022100050000")
        self.assertIsNotNone(exam)
        self.assertEqual(exam.ph, 6.9)
        self.assertEqual(exam.organic_matter, 13.2)
        self.assertEqual(exam.field_type, "논")  # Exam_Type=1

    def test_get_soil_exam_list_rejects_out_of_range_ph(self):
        with patch("httpx.get", return_value=FakeResponse(SOIL_EXAM_LIST_XML)):
            exams = get_soil_exam_list("4215034022")
        self.assertEqual(len(exams), 2)
        self.assertEqual(exams[0].ph, 6.9)
        self.assertIsNone(exams[1].ph)  # pH 20은 범위 밖 → 결측 처리(CLAUDE.md §12)


if __name__ == "__main__":
    unittest.main()
