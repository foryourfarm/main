"""설정이 위험한 상태로 기동하는 것을 막는 가드 검증 (CLAUDE.md §17).

**왜 필요한가**: 여기서 막는 두 사고는 **증상이 없다는 점**이 공통이다.

1. `JWT_SECRET` 미설정 — 앱은 정상으로 뜨고 로그인도 되지만, 리포에 공개된 기본 시크릿으로
   서명하므로 누구나 임의 계정의 토큰을 위조할 수 있다. 화면상 아무 차이가 없어 배포 후에도
   모른다. README §⑤의 `--set-env-vars` 사고가 정확히 이 상태를 만든다.
2. `COOKIE_SAMESITE=none` + `COOKIE_SECURE=false` — 브라우저가 refresh 쿠키를 버린다.
   로그인 직후엔 메모리 access로 멀쩡히 동작하다가 새로고침에서만 깨져서, 배포 한참 뒤에
   "가끔 로그아웃된다"로 발견된다(2026-07-26 실제 사고).

둘 다 사람이 조심해서 막는 부류가 아니라 기동을 막아야 하는 부류다.
"""

import os
import unittest
from unittest import mock

import pydantic

from app.core.config import _DEV_JWT_SECRET, Settings


def _settings(**overrides: object) -> Settings:
    """`.env`와 실제 환경변수를 타지 않는 Settings. 로컬 개발자의 .env 유무에 결과가
    좌우되면 이 테스트는 CI와 로컬에서 다른 말을 하게 된다."""
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


class TestJwtSecretGuard(unittest.TestCase):
    def test_cloud_run_rejects_default_secret(self) -> None:
        """Cloud Run(K_SERVICE 존재)에서 공개 기본 시크릿이면 기동을 막는다."""
        with mock.patch.dict(os.environ, {"K_SERVICE": "foryourfarm-backend"}):
            with self.assertRaises(pydantic.ValidationError) as ctx:
                _settings(jwt_secret=_DEV_JWT_SECRET)
        self.assertIn("JWT_SECRET", str(ctx.exception))

    def test_cloud_run_accepts_real_secret(self) -> None:
        """제대로 넣었으면 Cloud Run에서도 그냥 뜬다 — 가드가 정상 배포를 막지 않는다."""
        with mock.patch.dict(os.environ, {"K_SERVICE": "foryourfarm-backend"}):
            s = _settings(jwt_secret="a" * 64)
        self.assertEqual(s.jwt_secret, "a" * 64)

    def test_local_still_boots_with_default(self) -> None:
        """로컬(K_SERVICE 없음)은 종전 그대로 — .env 없이도 백엔드가 떠야 한다."""
        env = {k: v for k, v in os.environ.items() if k != "K_SERVICE"}
        with mock.patch.dict(os.environ, env, clear=True):
            s = _settings(jwt_secret=_DEV_JWT_SECRET)
        self.assertEqual(s.jwt_secret, _DEV_JWT_SECRET)


class TestCookiePolicyGuard(unittest.TestCase):
    def test_samesite_none_requires_secure(self) -> None:
        """Secure 없는 SameSite=None은 브라우저가 버린다 — 기동 시점에 잡는다."""
        with self.assertRaises(pydantic.ValidationError) as ctx:
            _settings(cookie_samesite="none", cookie_secure=False)
        self.assertIn("COOKIE_SECURE", str(ctx.exception))

    def test_samesite_none_with_secure_is_ok(self) -> None:
        """크로스사이트 배포의 정상 조합은 통과해야 한다."""
        s = _settings(cookie_samesite="none", cookie_secure=True)
        self.assertEqual(s.cookie_samesite, "none")

    def test_unknown_samesite_rejected(self) -> None:
        """오타는 쿠키가 조용히 안 붙는 원인이라 값 자체를 화이트리스트로 검증한다."""
        with self.assertRaises(pydantic.ValidationError):
            _settings(cookie_samesite="Lax;")

    def test_default_local_combination_is_ok(self) -> None:
        """기본값(lax + secure=False)은 http localhost용 정상 조합이다."""
        s = _settings()
        self.assertEqual((s.cookie_samesite, s.cookie_secure), ("lax", False))


if __name__ == "__main__":
    unittest.main()
