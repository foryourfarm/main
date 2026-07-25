"""app.infra.public_api 파싱/방어 로직 테스트. 네트워크·API키 불필요(캔드 XML만 사용).

soil_profile/soil_exam의 SUCCESS_XML은 각 API의 공식 OPEN API 기술명세서(ver1.0)에
실린 요청/응답 예제를 그대로 사용한다 — 실제 스펙과 어긋나지 않는지 검증하는 목적.
"""

import unittest
from unittest.mock import patch

from app.infra.public_api.base import PublicApiError, fetch_items
from app.infra.public_api.soil_exam_client import get_soil_exam, get_soil_exam_list
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
<PNU_Code>4215034022100050000</PNU_Code>
<Deepsoil_Qlt_Code>04</Deepsoil_Qlt_Code>
<Deepsoil_Ston_Code>02</Deepsoil_Ston_Code>
<Soilslope_Code>03</Soilslope_Code>
</item></items></body>
</response>"""

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
    def test_negative_rainfall_becomes_none(self):
        obs = WeatherObservation(point_code="bcde", obs_date="20260102", temp_avg=1.5, rainfall=-999)
        self.assertIsNone(obs.rainfall)

    def test_valid_rainfall_kept(self):
        obs = WeatherObservation(point_code="a", obs_date="20260101", temp_avg=-2.3, rainfall=0)
        self.assertEqual(obs.rainfall, 0)


class TestSoilProfileClient(unittest.TestCase):
    def test_parses_official_example_and_maps_codes(self):
        with patch("httpx.get", return_value=FakeResponse(SOIL_PROFILE_XML)):
            profile = get_soil_profile("4215034022100050000")
        self.assertIsNotNone(profile)
        self.assertEqual(profile.deepsoil_texture, "식양질")  # 04
        self.assertEqual(profile.deepsoil_gravel, "있음_15-35%")  # 02
        self.assertEqual(profile.soil_slope, "경사_7-15%")  # 03


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
