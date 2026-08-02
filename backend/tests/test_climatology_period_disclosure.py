"""화면에 적은 기상 데이터 기간이 실제 ETL 기간과 같은지 강제한다.

**왜 테스트로 묶나**: `CLIMATOLOGY_PERIOD_LIMITATION`은 "최근 5년(2021~2025) 관측 평균"이라고
유저에게 못박는다. ETL의 대상 연도가 바뀌면 이 문구는 **에러 없이 거짓말이 된다** — 화면에는
여전히 2021~2025라고 뜨는데 데이터는 다른 기간이다. §18-4가 금지하는 바로 그 상태다.

같은 부류(규칙은 주석에만 있고 강제 장치가 없어 반복해서 어긋남)가 이 리포에서 세 번
있었고 `test_env_example_matches_settings.py`가 그 장치였다. 여기도 같은 이유로 만든다.
"""
import re
import unittest
from pathlib import Path

from app.services.suitability_service import CLIMATOLOGY_PERIOD_LIMITATION

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
# 평년치를 적재하는 두 ETL. 둘 다 source 문자열에 대상 기간을 박아 넣는다.
ETL_SOURCES = {
    "load_weather_climatology.py": "obs_mean",
    "load_aws_climatology.py": "aws_mean",
}


def _etl_period(filename: str, prefix: str) -> tuple[int, int]:
    """ETL이 쓰는 `<prefix>_<시작>_<끝>` source 상수에서 기간을 뽑는다."""
    text = (SCRIPTS / filename).read_text(encoding="utf-8")
    match = re.search(rf'SOURCE\s*=\s*"{prefix}_(\d{{4}})_(\d{{4}})"', text)
    assert match is not None, f"{filename}에서 SOURCE = \"{prefix}_YYYY_YYYY\"를 찾지 못했다"
    return int(match.group(1)), int(match.group(2))


class TestClimatologyPeriodDisclosure(unittest.TestCase):
    def test_limitation_states_the_actual_etl_period(self):
        stated = re.search(r"최근 (\d+)년\((\d{4})~(\d{4})\)", CLIMATOLOGY_PERIOD_LIMITATION)
        self.assertIsNotNone(stated, "한계 문구에서 '최근 N년(YYYY~YYYY)'을 찾지 못했다")
        years, start, end = (int(g) for g in stated.groups())

        for filename, prefix in ETL_SOURCES.items():
            with self.subTest(etl=filename):
                self.assertEqual(
                    (start, end), _etl_period(filename, prefix),
                    f"{filename}의 적재 기간이 화면 문구와 다르다 — 문구를 고치거나 ETL을 되돌려라",
                )
        self.assertEqual(years, end - start + 1, "'최근 N년'의 N이 실제 연수와 다르다")

    def test_limitation_does_not_claim_to_be_kma_normal(self):
        """5년 평균을 기상청 평년값이라 부르지 않는지. 부르면 §18-4 위반이다."""
        self.assertRegex(CLIMATOLOGY_PERIOD_LIMITATION, r"30년 평년값.{0,20}아니")


if __name__ == "__main__":
    unittest.main()
