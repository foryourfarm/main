"""요청 빈도 제한 검증 (CLAUDE.md §17).

**왜 필요한가**: 2026-08-05 보안 점검 전까지 레이트리밋이 코드에 한 줄도 없었다. 특히
`POST /chat`은 **비인증 게스트가 GPU를 태울 수 있는 경로**였다 — 계정도 필요 없이 LLM 예산을
소진시킬 수 있었다. 로그인은 bcrypt(실측 ~440ms)를 요청마다 태우므로 무차별 대입이 비밀번호
추측이자 CPU 소진이었다.

여기서 굳히는 계약은 셋이다:
1. 한도를 넘으면 429다(500도, 조용한 통과도 아니다).
2. **키가 다르면 서로 영향을 주지 않는다** — 한 계정이 막혔다고 다른 계정이 막히면 그건
   제한이 아니라 장애다.
3. 윈도우가 지나면 다시 열린다 — 영구 차단이 아니다.
"""

import time
import unittest

from app.api import rate_limit
from app.core.errors import AppError


class TestSlidingWindow(unittest.TestCase):
    def setUp(self) -> None:
        rate_limit.reset()

    def test_allows_up_to_limit_then_429(self) -> None:
        limit = (3, 60.0)
        for _ in range(3):
            rate_limit.check("t", "k", limit)  # 한도까지는 통과해야 한다
        with self.assertRaises(AppError) as ctx:
            rate_limit.check("t", "k", limit)
        self.assertEqual(ctx.exception.status_code, 429)

    def test_keys_are_independent(self) -> None:
        """한 계정/이메일이 한도를 채워도 다른 쪽은 멀쩡해야 한다."""
        limit = (1, 60.0)
        rate_limit.check("t", "a", limit)
        with self.assertRaises(AppError):
            rate_limit.check("t", "a", limit)
        rate_limit.check("t", "b", limit)  # 다른 키 — 걸리면 안 된다

    def test_buckets_are_independent(self) -> None:
        """경로가 다르면 별도로 센다(로그인 한도가 챗봇을 막지 않는다)."""
        limit = (1, 60.0)
        rate_limit.check("login", "k", limit)
        rate_limit.check("chat", "k", limit)

    def test_window_expires(self) -> None:
        """윈도우가 지나면 다시 열린다 — 영구 차단이 아니다."""
        limit = (1, 0.05)
        rate_limit.check("t", "k", limit)
        with self.assertRaises(AppError):
            rate_limit.check("t", "k", limit)
        time.sleep(0.06)
        rate_limit.check("t", "k", limit)

    def test_blocked_request_does_not_extend_window(self) -> None:
        """막힌 요청을 기록하면 계속 두드리는 클라이언트가 스스로 윈도우를 갱신해 영구히
        잠긴다. 그건 제한이 아니라 차단이라 기록하지 않는다.

        윈도우 **안에서만** 두드린 뒤(그동안은 계속 429여야 한다) 윈도우가 지나면 열리는지 본다."""
        window = 0.2
        limit = (1, window)
        start = time.monotonic()
        rate_limit.check("t", "k", limit)
        while time.monotonic() - start < window * 0.5:  # 윈도우 안에서 계속 두드린다
            with self.assertRaises(AppError):
                rate_limit.check("t", "k", limit)
        time.sleep(window)  # 첫 요청이 윈도우 밖으로 나갈 때까지 기다린다
        rate_limit.check("t", "k", limit)  # 두드린 것들이 윈도우를 밀지 않았으므로 열려야 한다


class TestConfiguredLimits(unittest.TestCase):
    """실제 설정값이 사람의 정상 사용을 막지 않는지 — 숫자가 실수로 1 같은 값이 되는 것을 잡는다."""

    def test_limits_are_above_human_usage(self) -> None:
        self.assertGreaterEqual(rate_limit.CHAT_PER_USER[0], 5)
        self.assertGreaterEqual(rate_limit.LOGIN_PER_EMAIL[0], 5)
        self.assertGreaterEqual(rate_limit.SIGNUP_GLOBAL[0], 10)

    def test_windows_are_bounded(self) -> None:
        """윈도우가 과하게 길면 정상 유저가 오래 잠긴다."""
        for limit in (rate_limit.CHAT_PER_USER, rate_limit.LOGIN_PER_EMAIL, rate_limit.SIGNUP_GLOBAL):
            self.assertLessEqual(limit[1], 600.0)


if __name__ == "__main__":
    unittest.main()
