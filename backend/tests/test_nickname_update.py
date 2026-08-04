"""닉네임 변경 (PATCH /api/v1/auth/me) + 카카오 신규 판정(is_new_user).

**왜 이 기능이 생겼나**: 카카오는 닉네임을 주지 않아 계정이 기본값(`카카오 사용자`)으로 시작하는데
그 값을 **바꿀 방법이 아예 없었다**(수정 엔드포인트도 화면도 없었다). 이메일 가입자도 가입 후에는
못 바꿨다. 그래서 두 경로 모두를 이 엔드포인트로 해결한다.

여기서 고정하는 것:
  - 남의 닉네임을 바꿀 수 없다(대상 id를 받지 않는다 — 인증된 유저 자신만).
  - 인증 없이는 못 바꾼다.
  - 가입 때와 **같은 길이 제약**(1~50) — 한쪽만 느슨하면 그 경로로 이상한 값이 들어온다.
  - `is_new_user`는 **처음 만든 로그인에만** 참이다(매번 참이면 닉네임 화면이 계속 뜬다).

실행: backend/.venv/Scripts/python.exe -m unittest tests.test_nickname_update
"""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models.user import User

ME_URL = "/api/v1/auth/me"
KAKAO_URL = "/api/v1/auth/kakao"


@compiles(BigInteger, "sqlite")
def _bigint_as_integer_on_sqlite(element, compiler, **kw):
    return "INTEGER"


class NicknameTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        User.__table__.create(self.engine)
        self.db = Session(self.engine)
        self.user = User(email="farmer@example.com", password_hash="$2b$hash", nickname="처음이름")
        self.other = User(email="other@example.com", password_hash="$2b$hash", nickname="남의이름")
        self.db.add_all([self.user, self.other])
        self.db.commit()
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()

    def _as_me(self):
        app.dependency_overrides[get_current_user] = lambda: self.user


class TestNicknameUpdate(NicknameTestCase):
    def test_updates_own_nickname(self):
        self._as_me()
        resp = self.client.patch(ME_URL, json={"nickname": "바꾼이름"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["nickname"], "바꾼이름")
        self.db.refresh(self.user)
        self.assertEqual(self.user.nickname, "바꾼이름")

    def test_does_not_touch_other_users(self):
        """대상 id를 받지 않으므로 남의 계정을 가리킬 방법이 없다 — 그 사실을 고정한다."""
        self._as_me()
        self.client.patch(ME_URL, json={"nickname": "바꾼이름"})
        self.db.refresh(self.other)
        self.assertEqual(self.other.nickname, "남의이름")

    def test_requires_authentication(self):
        resp = self.client.patch(ME_URL, json={"nickname": "바꾼이름"})
        self.assertEqual(resp.status_code, 401)

    def test_rejects_blank_nickname(self):
        """빈 닉네임을 허용하면 화면에 "님"만 남는다."""
        self._as_me()
        self.assertEqual(self.client.patch(ME_URL, json={"nickname": ""}).status_code, 422)

    def test_rejects_too_long_nickname(self):
        """가입(1~50)과 같은 제약이어야 한다 — 한쪽만 느슨하면 그 경로로 들어온다."""
        self._as_me()
        resp = self.client.patch(ME_URL, json={"nickname": "가" * 51})
        self.assertEqual(resp.status_code, 422)

    def test_email_and_password_are_not_changeable_here(self):
        """이메일·비밀번호는 이 엔드포인트가 다루지 않는다(별개 흐름) — 슬쩍 바뀌지 않아야 한다."""
        self._as_me()
        self.client.patch(
            ME_URL,
            json={"nickname": "바꾼이름", "email": "hacked@example.com", "password": "x" * 12},
        )
        self.db.refresh(self.user)
        self.assertEqual(self.user.email, "farmer@example.com")
        self.assertEqual(self.user.password_hash, "$2b$hash")


class TestKakaoIsNewUser(NicknameTestCase):
    """FE가 "처음 온 사람"을 닉네임 화면으로 보내는 근거. 문자열 비교로 추측하지 않게 서버가 준다."""

    def setUp(self):
        super().setUp()
        self._saved_key = settings.kakao_rest_api_key
        settings.kakao_rest_api_key = "test-app-key"

    def tearDown(self):
        settings.kakao_rest_api_key = self._saved_key
        super().tearDown()

    def test_true_on_first_login_false_afterwards(self):
        with (
            patch("app.api.auth.exchange_code_for_token", return_value="kakao-token"),
            patch("app.api.auth.fetch_kakao_account", return_value=(999, "카카오 사용자")),
        ):
            first = self.client.post(KAKAO_URL, json={"code": "c1"}).json()["data"]
            second = self.client.post(KAKAO_URL, json={"code": "c2"}).json()["data"]
        self.assertTrue(first["is_new_user"])
        self.assertFalse(second["is_new_user"])

    def test_email_login_is_never_new(self):
        """가입이 별도 단계라 로그인은 언제나 기존 계정이다 — FE가 이메일 로그인에서 닉네임
        화면으로 튀지 않아야 한다."""
        with patch("app.api.auth.auth_service.authenticate", return_value=self.user):
            resp = self.client.post(
                "/api/v1/auth/login", json={"email": "farmer@example.com", "password": "pw"}
            )
        self.assertFalse(resp.json()["data"]["is_new_user"])


if __name__ == "__main__":
    unittest.main()
