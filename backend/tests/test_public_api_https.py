"""공공 API 클라이언트가 평문 HTTP를 쓰지 않는지 검증.

**왜 필요한가**: 2026-08-03 프로덕션에서 대시보드가 진입마다 30초씩 걸렸다. 원인은
`data.go.kr`이 평문 HTTP 응답을 중단한 것이었다 — `http://`로 부르면 연결이 걸린 채
타임아웃(15초)까지 매달린다(실측: http 25초 무응답 / https 0.08초 응답).

증상이 지연으로만 나타나 원인을 찾기 어려웠던 이유가 두 가지다:

1. `get_forecast_rows`는 조회 실패 시 캐시를 갱신하지 않고 그냥 반환한다(외부 장애가
   화면을 죽이지 않게 하는 §12 방어). 그래서 **실패가 에러로 드러나지 않고**, 다음 요청이
   같은 지연을 처음부터 다시 먹는다 — 영구히 느린 상태가 된다.
2. 대시보드가 밭마다 예보를 부르는데(지역이 다르면 캐시 공유가 안 된다) 프로덕션 밭 16개가
   전부 다른 지역이라 15초 × 16이 순차로 쌓였다.

**부분 마이그레이션이 방치돼 있었다.** `weather_client`·`soil_chem_stat_client`는 이미
https였는데 `forecast_client`·`soil_exam_client`·`soil_profile_client`·`agri_station_client`는
http로 남아 있었다. 규칙이 코드 어디에도 강제되지 않아 고친 사람만 고치고 끝났다.
이 파일이 그 강제 장치다.

`www.kma.go.kr`(3개월전망 RSS)은 대상이 아니다 — 다른 호스트이고 http도 정상 응답한다.
"""

import re
import unittest
from pathlib import Path

CLIENT_DIR = Path(__file__).resolve().parents[1] / "app" / "infra" / "public_api"

# 평문 HTTP로 부르면 안 되는 호스트. 실측으로 확인된 것만 넣는다 — 추측으로 넓히지 않는다.
HTTPS_REQUIRED_HOSTS = ("apis.data.go.kr", "apihub.kma.go.kr")

_PLAIN_HTTP = re.compile(r"http://([A-Za-z0-9.\-]+)")


def _offending_lines() -> list[str]:
    out: list[str] = []
    for path in sorted(CLIENT_DIR.glob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for host in _PLAIN_HTTP.findall(line):
                if host in HTTPS_REQUIRED_HOSTS:
                    out.append(f"{path.name}:{lineno} → http://{host}")
    return out


class TestPublicApiUsesHttps(unittest.TestCase):
    def test_no_plain_http_for_https_required_hosts(self):
        offending = _offending_lines()
        self.assertEqual(
            offending,
            [],
            "평문 HTTP로 공공 API를 부르면 응답 없이 타임아웃까지 매달린다"
            f"(2026-08-03 프로덕션 30초 지연의 원인). https로 바꿀 것: {offending}",
        )

    def test_scans_actual_client_files(self):
        # 경로가 어긋나면 0개를 훑고 위 검증이 공허하게 통과한다.
        files = list(CLIENT_DIR.glob("*.py"))
        self.assertGreater(len(files), 5, f"클라이언트 파일을 {len(files)}개만 찾았다")

    def test_detects_plain_http_when_present(self):
        # 이 검사가 헛돌지 않는지 — 패턴이 실제로 대상 호스트를 잡아내야 한다.
        found = _PLAIN_HTTP.findall("BASE_URL = 'http://apis.data.go.kr/foo'")
        self.assertIn("apis.data.go.kr", found)


if __name__ == "__main__":
    unittest.main()
