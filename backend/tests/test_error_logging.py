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
