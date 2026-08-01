"""AWS 일통계(typ01 텍스트) 파싱 검증. 네트워크 불필요.

샘플은 2026-08-01 실호출 응답 형태를 그대로 따른다 — `#START7777` 헤더,
공백 구분 6칼럼 + 지점명, `#7777END` 종료.
"""
import unittest

from app.infra.public_api.aws_daily_client import (
    OBS_TEMP_MAX,
    AwsDailyValue,
    parse_response,
)

REAL_SAMPLE = """#START7777
#--------------------------------------------------------------------------
#  지상 관측지점 시간자료
#--------------------------------------------------------------------------
# YYMMDD   STN         LON          LAT       HT      VAL
#    KST    ID        (deg)        (deg)     (m)
20250701   108 126.96580000  37.57142000   85.67     31.7 서울
20250701   212 127.88043000  37.68360000  140.20     30.1 홍천
20250702   108 126.96580000  37.57142000   85.67     29.4 서울
#7777END
"""


class ParseResponseTest(unittest.TestCase):
    def test_실제_응답_형태를_행으로_바꾼다(self) -> None:
        rows = parse_response(REAL_SAMPLE)

        self.assertEqual(len(rows), 3)
        self.assertEqual(
            rows[0],
            AwsDailyValue(
                point_code="108",
                obs_date="2025-07-01",  # YYMMDD → 하이픈 형식
                value=31.7,
                lat=37.57142,
                lon=126.9658,
                altitude=85.67,
                point_name="서울",
            ),
        )

    def test_주석과_종료표시는_데이터로_읽지_않는다(self) -> None:
        """`#`로 시작하는 줄이 6개 이상 토큰을 가져도 데이터가 되면 안 된다."""
        rows = parse_response(REAL_SAMPLE)

        self.assertTrue(all(not r.point_code.startswith("#") for r in rows))
        self.assertEqual({r.obs_date for r in rows}, {"2025-07-01", "2025-07-02"})

    def test_지점명에_공백이_있어도_칼럼이_밀리지_않는다(self) -> None:
        """실측 22,611행 중 495행이 필드 8개였다 — 이름을 위치로 읽으면 값이 깨진다."""
        text = (
            "#START7777\n"
            "20250701   295 128.10000000  36.50000000   50.00     28.3 문경 새재\n"
            "#7777END\n"
        )

        (row,) = parse_response(text)

        self.assertEqual(row.value, 28.3)
        self.assertEqual(row.altitude, 50.0)
        self.assertEqual(row.point_name, "문경 새재")

    def test_결측과_이상치는_행을_만들지_않는다(self) -> None:
        """관측불가(-9xx)나 비수치는 0으로 채우지 않고 아예 제외한다(§12)."""
        text = (
            "#START7777\n"
            "20250701   108 126.96580000  37.57142000   85.67   -999.0 서울\n"  # 결측값
            "20250701   109 126.96580000  37.57142000   85.67        - 미상\n"  # 비수치
            "20250701   110 126.96580000  37.57142000   85.67     25.0 정상\n"
            "#7777END\n"
        )

        rows = parse_response(text)

        self.assertEqual([r.point_code for r in rows], ["110"])

    def test_좌표가_없으면_버린다(self) -> None:
        """구역 배정이 좌표로 이뤄지므로 좌표 없는 관측은 쓸 수 없다."""
        text = (
            "#START7777\n"
            "20250701   108        -999.0       -999.0   85.67     25.0 좌표없음\n"
            "#7777END\n"
        )

        self.assertEqual(parse_response(text), [])

    def test_빈_응답도_예외를_내지_않는다(self) -> None:
        self.assertEqual(parse_response(""), [])
        self.assertEqual(parse_response("#START7777\n#7777END\n"), [])

    def test_요소_상수는_명세의_obs_값이다(self) -> None:
        """오타로 빈 응답을 받는 사고를 막는다 — 실호출로 확인한 값이다."""
        self.assertEqual(OBS_TEMP_MAX, "ta_max")


if __name__ == "__main__":
    unittest.main()
