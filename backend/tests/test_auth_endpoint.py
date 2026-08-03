"""인증 라우터의 HTTP 경계 동작 (app/api/auth.py, docs/auth-security.md).

**서비스 계층 테스트가 원리적으로 못 잡는 것만 여기서 본다.** `auth_service`는 이메일과
비밀번호를 받아 유저를 돌려줄 뿐, **토큰이 어디에 실려 나가는지**를 모른다. 분리 토큰
방식(access는 응답 본문, refresh는 httpOnly 쿠키)의 안전성은 전부 이 배선에 달려 있다:

- refresh가 본문에 섞여 나가면 httpOnly의 의미가 사라진다(XSS로 탈취 가능).
- 쿠키 `path`가 넓어지면 모든 요청에 refresh가 실려 공격면이 커진다.
- access/refresh를 서로 바꿔 쓸 수 있으면 30분짜리 토큰이 14일짜리가 된다.

토큰은 실물을 쓴다(`create_*_token`은 DB가 필요 없다) — 타입 혼용 검증을 진짜 서명으로
해야 의미가 있다. DB가 필요한 지점만 `auth_service`를 대역으로 바꾼다.
"""

import unittest
from unittest import mock

from fastapi.testclient import TestClient

from app.api import auth as auth_api
from app.api import deps
from app.core.security import create_access_token, create_refresh_token
from app.db.session import get_db
from app.main import app
from app.models.user import User

USER = User(id=7, email="farmer@example.com", nickname="귀농인", password_hash="$2b$dummy")

LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
ME_URL = "/api/v1/auth/me"


class AuthEndpointTestCase(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_db] = lambda: None
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def _post_refresh_with_cookie(self, token: str):
        """refresh 쿠키를 실어 POST. 요청별 `cookies=`는 starlette이 지원 중단 예고를 해서
        클라이언트 인스턴스에 심는다(동작은 같고 경고만 사라진다)."""
        self.client.cookies.set(auth_api.REFRESH_COOKIE, token, path=auth_api.REFRESH_PATH)
        try:
            return self.client.post(REFRESH_URL)
        finally:
            self.client.cookies.clear()


class TestLoginTokenPlacement(AuthEndpointTestCase):
    def _login(self):
        with mock.patch.object(auth_api.auth_service, "authenticate", return_value=USER):
            return self.client.post(
                LOGIN_URL, json={"email": USER.email, "password": "pw12345678"}
            )

    def test_refresh_token_never_appears_in_response_body(self):
        """본문에 새어 나가면 httpOnly 쿠키로 둔 이유가 통째로 사라진다."""
        resp = self._login()
        self.assertEqual(resp.status_code, 200)
        cookie_token = resp.cookies.get(auth_api.REFRESH_COOKIE)
        self.assertIsNotNone(cookie_token, "refresh 쿠키가 설정되지 않았다")
        self.assertNotIn(cookie_token, resp.text, "refresh 토큰이 응답 본문에 실렸다")

    def test_refresh_cookie_is_httponly_and_path_scoped(self):
        """`path`가 넓어지면 refresh가 모든 요청에 실려 공격면이 커진다."""
        resp = self._login()
        raw = resp.headers.get("set-cookie", "")
        self.assertIn("httponly", raw.lower(), f"HttpOnly가 없다: {raw}")
        self.assertIn(f"Path={auth_api.REFRESH_PATH}", raw, f"path 스코프가 좁혀지지 않았다: {raw}")

    def test_password_is_not_echoed_back(self):
        resp = self._login()
        self.assertNotIn("pw12345678", resp.text)
        self.assertNotIn("password_hash", resp.text)

    def test_success_envelope_shape(self):
        # §6 공통 래퍼 — FE가 이 모양에 의존한다.
        body = self._login().json()
        self.assertTrue(body["success"])
        self.assertIsNone(body["error"])
        self.assertEqual(body["data"]["user"]["email"], USER.email)
        self.assertTrue(body["data"]["access_token"])


class TestAccountEnumeration(AuthEndpointTestCase):
    def test_wrong_password_and_unknown_email_are_indistinguishable(self):
        """응답이 갈리면 이메일만 넣어보고 가입 여부를 캐낼 수 있다(계정 열거)."""
        with mock.patch.object(auth_api.auth_service, "authenticate", return_value=None):
            unknown = self.client.post(
                LOGIN_URL, json={"email": "nobody@example.com", "password": "pw12345678"}
            )
            wrong_pw = self.client.post(
                LOGIN_URL, json={"email": USER.email, "password": "wrongpassword"}
            )
        self.assertEqual(unknown.status_code, wrong_pw.status_code)
        self.assertEqual(unknown.json(), wrong_pw.json())
        self.assertEqual(unknown.status_code, 401)
        self.assertEqual(unknown.json()["error"]["code"], "INVALID_CREDENTIALS")


class TestTokenTypeConfusion(AuthEndpointTestCase):
    """access와 refresh를 바꿔 쓸 수 있으면 30분 토큰이 14일 토큰이 된다."""

    def test_refresh_token_is_rejected_as_bearer(self):
        with mock.patch.object(deps.auth_service, "get_user", return_value=USER) as get_user:
            resp = self.client.get(
                ME_URL, headers={"Authorization": f"Bearer {create_refresh_token(USER.id)}"}
            )
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["error"]["code"], "INVALID_TOKEN")
        get_user.assert_not_called()  # 타입 검증이 조회보다 먼저 끝나야 한다

    def test_access_token_is_rejected_in_refresh_cookie(self):
        with mock.patch.object(auth_api.auth_service, "get_user", return_value=USER):
            resp = self._post_refresh_with_cookie(create_access_token(USER.id))
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["error"]["code"], "INVALID_TOKEN")

    def test_valid_access_token_is_accepted(self):
        # 위 거절들이 "전부 401"인 헛 구현이 아님을 확인한다.
        with mock.patch.object(deps.auth_service, "get_user", return_value=USER):
            resp = self.client.get(
                ME_URL, headers={"Authorization": f"Bearer {create_access_token(USER.id)}"}
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["email"], USER.email)

    def test_garbage_token_is_401_not_500(self):
        resp = self.client.get(ME_URL, headers={"Authorization": "Bearer not-a-jwt"})
        self.assertEqual(resp.status_code, 401)


class TestDeletedAccountCannotRefresh(AuthEndpointTestCase):
    def test_refresh_of_deleted_user_is_rejected(self):
        """서명은 유효한데 계정이 사라진 경우 — 서명만 믿으면 최대 14일 살아남는다."""
        with mock.patch.object(auth_api.auth_service, "get_user", return_value=None):
            resp = self._post_refresh_with_cookie(create_refresh_token(USER.id))
        self.assertEqual(resp.status_code, 401)

    def test_refresh_without_cookie_is_rejected(self):
        self.assertEqual(self.client.post(REFRESH_URL).status_code, 401)


class TestSignup(AuthEndpointTestCase):
    def test_duplicate_email_is_409_not_500(self):
        with mock.patch.object(
            auth_api.auth_service,
            "create_user",
            side_effect=auth_api.auth_service.EmailAlreadyExists(),
        ):
            resp = self.client.post(
                "/api/v1/auth/signup",
                json={"email": USER.email, "password": "pw12345678", "nickname": "귀농인"},
            )
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["error"]["code"], "EMAIL_EXISTS")

    def test_signup_does_not_issue_tokens(self):
        """가입은 토큰을 주지 않는다(docs/auth-security.md) — FE가 로그인 화면으로 보낸다."""
        with mock.patch.object(auth_api.auth_service, "create_user", return_value=USER):
            resp = self.client.post(
                "/api/v1/auth/signup",
                json={"email": USER.email, "password": "pw12345678", "nickname": "귀농인"},
            )
        self.assertEqual(resp.status_code, 201)
        self.assertNotIn("access_token", resp.text)
        self.assertNotIn("set-cookie", {k.lower() for k in resp.headers})


if __name__ == "__main__":
    unittest.main()
