"""500이 로그에 트레이스백과 함께 남는지 검증.

**왜 필요한가**: 2026-08-03 프로덕션에서 단기 탭 행동추천이 화면에서 통째로 사라졌는데
`severity>=ERROR`로 조회해도 **로그가 한 줄도 없었다.** `unhandled_exception_handler`가
모든 예외를 잡아 공통 실패 포맷으로 바꾸면서 **트레이스백을 버리고 있었기 때문이다.**
서비스가 죽지 않는 건 좋지만(§18-5) 원인을 못 찾으면 고칠 수도 없다.

여기서 굳히는 계약은 셋이다:
1. 500은 ERROR로, **예외 정보를 포함해** 기록된다.
2. 4xx는 ERROR가 아니다 — 401/404는 비로그인·없는 밭이라 정상 흐름이고, 그걸 ERROR로
   두면 경보가 잡음에 묻혀 무의미해진다.
3. 응답 본문에 내부 상세(예외 메시지·트레이스백)가 새지 않는다 — 공격자에게 내부 구조를
   주지 않는다. 로그에만 남긴다.
"""

import logging
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app as real_app
from app.main import unhandled_exception_handler

_BOOM = "의도적 테스트 예외 — 실제 장애가 아니다"


def _make_boom_app() -> FastAPI:
    """500을 내는 경로를 가진 **별도** 앱. 실제 `app`에 라우트를 붙이지 않는다 —
    붙였더니 `test_route_auth_guard`가 "인증 없이 500을 내는 라우트"로 잡아냈다(가드가
    제대로 동작한 것이다). 여기서 검증하려는 건 핸들러이지 라우팅이 아니므로 떼어 쓴다."""
    boom_app = FastAPI()
    boom_app.add_exception_handler(Exception, unhandled_exception_handler)

    @boom_app.get("/boom")
    def _boom() -> None:
        raise RuntimeError(_BOOM)

    return boom_app


class TestErrorLogging(unittest.TestCase):
    def setUp(self) -> None:
        # raise_server_exceptions=False — 예외를 클라이언트로 재던지지 않고 실제 운영처럼
        # 핸들러를 태워야 로그 동작을 볼 수 있다.
        self.client = TestClient(_make_boom_app(), raise_server_exceptions=False)

    def test_unhandled_exception_is_logged_with_traceback(self):
        with self.assertLogs("app.request", level="ERROR") as captured:
            resp = self.client.get("/boom")
        self.assertEqual(resp.status_code, 500)
        joined = "\n".join(captured.output)
        self.assertIn("INTERNAL_ERROR", joined)
        self.assertIn("/boom", joined)
        # 트레이스백이 실려야 원인을 알 수 있다 — 이게 없으면 종전 상태와 같다.
        self.assertIn("RuntimeError", joined)
        self.assertIn(_BOOM, joined)

    def test_response_body_does_not_leak_internals(self):
        resp = self.client.get("/boom")
        self.assertNotIn(_BOOM, resp.text)
        self.assertNotIn("Traceback", resp.text)
        self.assertEqual(resp.json()["error"]["code"], "INTERNAL_ERROR")

    def test_client_errors_are_not_logged_as_error(self):
        """401은 정상 흐름이다 — ERROR로 남기면 경보가 잡음에 묻힌다."""
        client = TestClient(real_app, raise_server_exceptions=False)
        with self.assertLogs("app.request", level="INFO") as captured:
            resp = client.get("/api/v1/farms")  # 자격증명 없음 → 401
        self.assertEqual(resp.status_code, 401)
        self.assertFalse(
            [r for r in captured.records if r.levelno >= logging.ERROR],
            f"4xx가 ERROR로 기록됐다: {captured.output}",
        )


class TestSecretRedaction(unittest.TestCase):
    """로그에 인증키가 실리지 않는지 (§17).

    **실제로 샜다.** 2026-08-03 로깅을 켜자 Cloud Logging에 흙토람 호출 URL이 통째로
    적재됐고 거기 64자 `serviceKey`가 평문으로 들어 있었다. 원인은 루트 로거를 INFO로
    열면서 httpx의 요청 로그(URL 전문)가 같이 켜진 것이다.

    공공데이터포털은 인증키를 **쿼리스트링으로** 받는다 — 즉 이 프로젝트에서는 URL 자체가
    비밀이다. 레벨을 낮추는 것만으로는 부족하다: 예외 메시지에도 URL이 들어가고
    (`Client error '401' for url '…?serviceKey=…'`) 그게 트레이스백을 타고 나간다.
    그래서 **출력 직전에** 지운다.
    """

    # 실제 유출된 형태 그대로(키 값만 가짜로 바꿈).
    LEAKED = (
        "HTTP Request: GET https://apis.data.go.kr/1390802/SoilEnviron/SoilExam/V2/"
        "getSoilExamList?serviceKey=deadbeef0123456789abcdef&STDG_CD=5279025037 \"HTTP/1.1 200 OK\""
    )

    def test_service_key_is_masked(self):
        from app.core.log_config import redact

        out = redact(self.LEAKED)
        self.assertNotIn("deadbeef0123456789abcdef", out)
        self.assertIn("serviceKey=***", out)
        # 어느 API였는지는 진단에 필요하므로 남는다.
        self.assertIn("SoilExam", out)
        self.assertIn("STDG_CD=5279025037", out)

    def test_auth_key_is_masked(self):
        """기상청 apihub는 `authKey`를 쓴다 — 이름이 다르다고 새면 안 된다."""
        from app.core.log_config import redact

        out = redact("GET https://apihub.kma.go.kr/api/typ01/url/x.php?obs=ta_max&authKey=SEKRET123")
        self.assertNotIn("SEKRET123", out)
        self.assertIn("authKey=***", out)

    def test_bare_key_is_masked(self):
        """VWorld는 파라미터명이 그냥 `key`다. 지금은 스크립트에서만 쓰여 이 경로를 안 타지만,
        런타임으로 옮기는 순간 조용히 새는 자리라 미리 막아둔다."""
        from app.core.log_config import redact

        out = redact("GET https://api.vworld.kr/req/address?key=SEKRET123&format=json")
        self.assertNotIn("SEKRET123", out)
        self.assertIn("key=***", out)

    def test_key_inside_other_words_is_not_masked(self):
        """`\\b` 없이 넓히면 `sortkey=`·`monkey=` 같은 평범한 파라미터까지 지워 로그가
        진단에 쓸모없어진다. 마스킹 범위가 넓어지는 방향의 회귀도 잡는다."""
        from app.core.log_config import redact

        self.assertEqual(redact("?sortkey=name"), "?sortkey=name")

    def test_masking_survives_traceback_path(self):
        """예외 메시지에 실린 URL이 트레이스백을 타고 나가는 경로 — 레벨 조정으로는 못 막는다."""
        import json
        import sys

        from app.core.log_config import CloudLoggingFormatter

        try:
            raise RuntimeError(f"Client error '401' for url '{self.LEAKED}'")
        except RuntimeError:
            record = logging.LogRecord(
                "app.test", logging.ERROR, __file__, 1, "호출 실패", None, sys.exc_info()
            )
        out = json.loads(CloudLoggingFormatter().format(record))
        self.assertNotIn("deadbeef0123456789abcdef", out["message"])

    def test_httpx_request_logging_is_disabled(self):
        """애초에 URL을 찍지 않게 한다 — 마스킹은 2차 방어다."""
        from app.core.log_config import setup_logging

        setup_logging()
        self.assertGreaterEqual(logging.getLogger("httpx").level, logging.WARNING)
        self.assertGreaterEqual(logging.getLogger("httpcore").level, logging.WARNING)


class TestLogFormatter(unittest.TestCase):
    def test_cloud_formatter_emits_severity_and_traceback(self):
        """Cloud Logging은 `severity` 필드를 심각도로 읽는다 — 없으면 필터가 안 걸린다."""
        import json

        from app.core.log_config import CloudLoggingFormatter

        try:
            raise ValueError("정형화 확인용")
        except ValueError:
            import sys

            record = logging.LogRecord(
                "app.request", logging.ERROR, __file__, 1, "터졌다", None, sys.exc_info()
            )
        out = json.loads(CloudLoggingFormatter().format(record))
        self.assertEqual(out["severity"], "ERROR")
        self.assertIn("터졌다", out["message"])
        self.assertIn("ValueError", out["message"])  # 트레이스백이 붙는다


if __name__ == "__main__":
    unittest.main()
