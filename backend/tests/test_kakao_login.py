"""카카오 로그인의 계정 처리 + HTTP 배선 (auth_service.upsert_kakao_user, POST /auth/kakao).

`test_kakao_client.py`가 외부 응답 파싱을 보고, 여기서는 그 결과가 **우리 계정 체계에 어떻게
앉는지**를 본다. 특히 다음 세 가지는 잘못되면 조용히 보안 문제가 된다:

  - 카카오 계정이 기존 이메일 계정에 **이어붙지 않아야** 한다(카카오 이메일 미인증 시 탈취 경로).
  - 같은 카카오 계정으로 두 번 로그인해도 계정이 하나여야 한다.
  - refresh 토큰은 본문이 아니라 **httpOnly 쿠키**로만 나가야 한다(분리 토큰 방식의 전제).

sqlite 인메모리에 users 테이블만 만들어 돌린다(로직은 kakao_id 조회라 DB 종류와 무관).

실행: backend/.venv/Scripts/python.exe -m unittest tests.test_kakao_login
"""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.services.auth_service import authenticate, upsert_kakao_user

KAKAO_URL = "/api/v1/auth/kakao"


# BIGINT PK는 sqlite에서 rowid로 autoincrement되지 않는다(Postgres는 BIGSERIAL로 정상).
@compiles(BigInteger, "sqlite")
def _bigint_as_integer_on_sqlite(element, compiler, **kw):
    return "INTEGER"


class KakaoAccountTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        User.__table__.create(self.engine)
        self.db = Session(self.engine)

    def tearDown(self):
        self.db.close()


class TestUpsertKakaoUser(KakaoAccountTestCase):
    def test_creates_account_without_email_or_password(self):
        """카카오 계정은 이메일·비밀번호가 없다 — 가짜 값을 지어 채우지 않는다."""
        user = upsert_kakao_user(self.db, kakao_id=999, nickname="귀농이")
        self.assertIsNotNone(user.id)
        self.assertEqual(user.kakao_id, 999)
        self.assertEqual(user.nickname, "귀농이")
        self.assertIsNone(user.email)
        self.assertIsNone(user.password_hash)

    def test_second_login_reuses_the_same_account(self):
        first = upsert_kakao_user(self.db, kakao_id=999, nickname="귀농이")
        second = upsert_kakao_user(self.db, kakao_id=999, nickname="귀농이")
        self.assertEqual(first.id, second.id)
        self.assertEqual(self.db.query(User).count(), 1)

    def test_does_not_overwrite_nickname_on_later_logins(self):
        """매번 덮으면 유저가 우리 쪽에서 바꾼 이름이 카카오 닉네임으로 조용히 되돌아간다."""
        user = upsert_kakao_user(self.db, kakao_id=999, nickname="처음이름")
        user.nickname = "내가 바꾼 이름"
        self.db.commit()
        again = upsert_kakao_user(self.db, kakao_id=999, nickname="처음이름")
        self.assertEqual(again.nickname, "내가 바꾼 이름")

    def test_does_not_attach_to_an_existing_email_account(self):
        """**계정 탈취 방어**: 이메일이 같아도 잇지 않는다. 카카오 이메일은 미인증일 수 있다."""
        existing = User(email="farmer@example.com", password_hash="$2b$hash", nickname="기존")
        self.db.add(existing)
        self.db.commit()

        kakao_user = upsert_kakao_user(self.db, kakao_id=999, nickname="카카오")
        self.assertNotEqual(kakao_user.id, existing.id)
        self.db.refresh(existing)
        self.assertIsNone(existing.kakao_id)  # 기존 계정은 손대지 않는다

    def test_different_kakao_ids_get_different_accounts(self):
        a = upsert_kakao_user(self.db, kakao_id=1, nickname="가")
        b = upsert_kakao_user(self.db, kakao_id=2, nickname="나")
        self.assertNotEqual(a.id, b.id)


class TestPasswordLoginAgainstKakaoAccount(KakaoAccountTestCase):
    def test_password_login_is_impossible_for_kakao_accounts(self):
        """`password_hash`가 None인 계정에 verify_password를 태우면 500이 난다 — None을 먼저 막는다.

        카카오 계정은 email도 None이라 조회 자체가 비지만, 나중에 이메일을 채우는 변경이 오면
        이 방어가 유일한 벽이 된다.
        """
        user = upsert_kakao_user(self.db, kakao_id=999, nickname="카카오")
        user.email = "kakao@example.com"  # 이메일이 채워진 최악의 경우를 가정
        self.db.commit()
        self.assertIsNone(authenticate(self.db, "kakao@example.com", "아무비밀번호"))


class TestKakaoEndpoint(unittest.TestCase):
    """HTTP 경계 — 토큰이 어디에 실려 나가는지, 실패가 어떤 상태코드로 갈라지는지."""

    def setUp(self):
        # TestClient는 앱을 다른 스레드에서 돌린다 — 기본 풀이면 스레드마다 새 인메모리 DB가
        # 열려 "no such table"이 난다. StaticPool로 커넥션 하나를 공유한다.
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        User.__table__.create(self.engine)
        self.db = Session(self.engine)
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app, raise_server_exceptions=False)
        # 키가 없으면 503으로 꺼지는 것이 정상 동작이라, 켜진 상태를 만들어 나머지를 검증한다.
        self._saved_key = settings.kakao_rest_api_key
        settings.kakao_rest_api_key = "test-app-key"

    def tearDown(self):
        settings.kakao_rest_api_key = self._saved_key
        app.dependency_overrides.clear()
        self.db.close()

    def _post(self, code: str = "code-1"):
        return self.client.post(KAKAO_URL, json={"code": code})

    def test_success_returns_access_in_body_and_refresh_in_httponly_cookie(self):
        with (
            patch("app.api.auth.exchange_code_for_token", return_value="kakao-token"),
            patch("app.api.auth.fetch_kakao_account", return_value=(999, "귀농이")),
        ):
            resp = self._post()

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertIn("access_token", body["data"])
        self.assertEqual(body["data"]["user"]["nickname"], "귀농이")
        self.assertIsNone(body["data"]["user"]["email"])  # 카카오 계정은 이메일이 없다

        # refresh는 본문에 절대 실리지 않는다(XSS로 탈취 가능해진다).
        self.assertNotIn("refresh_token", resp.text)
        cookie = resp.headers["set-cookie"]
        self.assertIn("refresh_token=", cookie)
        self.assertIn("HttpOnly", cookie)
        # path가 넓어지면 모든 요청에 refresh가 실려 공격면이 커진다.
        self.assertIn("Path=/api/v1/auth/refresh", cookie)

    def test_missing_config_is_503_not_500(self):
        """키를 빠뜨린 배포가 조용한 500이 되지 않게 — fail closed를 코드로 알린다."""
        settings.kakao_rest_api_key = ""
        resp = self._post()
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.json()["error"]["code"], "KAKAO_NOT_CONFIGURED")

    def test_invalid_code_is_401(self):
        from app.infra.oauth.kakao_client import KakaoAuthError

        with patch("app.api.auth.exchange_code_for_token", side_effect=KakaoAuthError("bad")):
            resp = self._post()
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["error"]["code"], "KAKAO_AUTH_FAILED")

    def test_kakao_outage_is_502(self):
        """카카오 장애를 401로 내면 유저에게 "다시 로그인하라"는 잘못된 안내가 간다."""
        from app.infra.oauth.kakao_client import KakaoError

        with patch("app.api.auth.exchange_code_for_token", side_effect=KakaoError("down")):
            resp = self._post()
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(resp.json()["error"]["code"], "UPSTREAM_UNAVAILABLE")

    def test_empty_code_is_rejected_before_calling_kakao(self):
        with patch("app.api.auth.exchange_code_for_token") as exchange:
            resp = self.client.post(KAKAO_URL, json={"code": ""})
        self.assertEqual(resp.status_code, 422)
        exchange.assert_not_called()

    def test_repeated_login_does_not_create_two_accounts(self):
        with (
            patch("app.api.auth.exchange_code_for_token", return_value="kakao-token"),
            patch("app.api.auth.fetch_kakao_account", return_value=(999, "귀농이")),
        ):
            first = self._post().json()["data"]["user"]["id"]
            second = self._post().json()["data"]["user"]["id"]
        self.assertEqual(first, second)
        self.assertEqual(self.db.query(User).count(), 1)


if __name__ == "__main__":
    unittest.main()
