"""카카오 로그인 클라이언트의 경계 방어 (app/infra/oauth/kakao_client.py).

외부 응답은 항상 결측·이상치가 있다고 가정한다(CLAUDE.md §12). 여기서 고정하는 규칙:
  - 인가코드 문제(유저 재시도로 풀림)와 카카오 장애(우리가 할 게 없음)를 **다른 예외로** 구분
    → 라우터가 401 / 502로 갈라 매핑한다. 한 예외로 묶으면 유저에게 잘못된 안내가 간다.
  - 200 응답이라도 필요한 필드가 없으면 실패다(카카오는 실패를 200 + error로 싣기도 한다).
  - 닉네임은 동의 항목이라 없을 수 있다 — 그것 때문에 로그인이 막히면 안 된다.

실행: backend/.venv/Scripts/python.exe -m unittest tests.test_kakao_client
"""

import unittest
from unittest.mock import patch

from app.infra.oauth.kakao_client import (
    DEFAULT_NICKNAME,
    KakaoAuthError,
    KakaoError,
    exchange_code_for_token,
    fetch_kakao_account,
)


class FakeResponse:
    def __init__(self, payload: object, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self) -> object:
        if isinstance(self._payload, str):
            raise ValueError("not json")  # httpx도 JSON 파싱 실패를 ValueError로 던진다
        return self._payload


def _exchange() -> str:
    return exchange_code_for_token(
        "code-1", client_id="app-key", redirect_uri="http://localhost:3000/login/kakao"
    )


class TestExchangeCode(unittest.TestCase):
    def test_returns_access_token(self):
        with patch("httpx.post", return_value=FakeResponse({"access_token": "kakao-token"})):
            self.assertEqual(_exchange(), "kakao-token")

    def test_client_secret_is_omitted_when_empty(self):
        """빈 client_secret을 보내면 카카오가 invalid_client로 거절한다 — 아예 넣지 않는다."""
        captured: dict[str, object] = {}

        def fake_post(url, data=None, timeout=None):  # noqa: ANN001, ARG001
            captured.update(data or {})
            return FakeResponse({"access_token": "t"})

        with patch("httpx.post", side_effect=fake_post):
            _exchange()
        self.assertNotIn("client_secret", captured)

    def test_client_secret_is_sent_when_configured(self):
        captured: dict[str, object] = {}

        def fake_post(url, data=None, timeout=None):  # noqa: ANN001, ARG001
            captured.update(data or {})
            return FakeResponse({"access_token": "t"})

        with patch("httpx.post", side_effect=fake_post):
            exchange_code_for_token(
                "code-1",
                client_id="app-key",
                redirect_uri="http://localhost:3000/login/kakao",
                client_secret="s3cret",
            )
        self.assertEqual(captured["client_secret"], "s3cret")

    def test_redirect_uri_and_code_are_sent_verbatim(self):
        """카카오가 인가 요청 때의 redirect_uri와 글자 단위로 대조한다."""
        captured: dict[str, object] = {}

        def fake_post(url, data=None, timeout=None):  # noqa: ANN001, ARG001
            captured.update(data or {})
            return FakeResponse({"access_token": "t"})

        with patch("httpx.post", side_effect=fake_post):
            _exchange()
        self.assertEqual(captured["redirect_uri"], "http://localhost:3000/login/kakao")
        self.assertEqual(captured["code"], "code-1")
        self.assertEqual(captured["grant_type"], "authorization_code")

    def test_invalid_code_is_auth_error(self):
        """만료·재사용된 인가코드 — 유저가 다시 시도하면 풀리므로 401로 갈라야 한다."""
        payload = {"error": "invalid_grant", "error_description": "authorization code not found"}
        with patch("httpx.post", return_value=FakeResponse(payload, status_code=400)):
            with self.assertRaises(KakaoAuthError):
                _exchange()

    def test_error_field_on_200_is_still_a_failure(self):
        """카카오는 실패를 200 + error로 싣기도 한다 — 상태코드만 보면 놓친다."""
        with patch("httpx.post", return_value=FakeResponse({"error": "invalid_client"})):
            with self.assertRaises(KakaoError):
                _exchange()

    def test_server_error_is_not_auth_error(self):
        """카카오 장애는 유저가 할 게 없다 — 502로 매핑되도록 일반 KakaoError여야 한다."""
        with patch("httpx.post", return_value=FakeResponse({"error": "boom"}, status_code=502)):
            with self.assertRaises(KakaoError) as ctx:
                _exchange()
        self.assertNotIsInstance(ctx.exception, KakaoAuthError)

    def test_missing_access_token_is_failure(self):
        with patch("httpx.post", return_value=FakeResponse({"token_type": "bearer"})):
            with self.assertRaises(KakaoError):
                _exchange()

    def test_non_json_response_is_failure(self):
        """장애 페이지(HTML)가 오는 경우 — 파싱 예외가 그대로 500으로 새지 않게 한다."""
        with patch("httpx.post", return_value=FakeResponse("<html>error</html>")):
            with self.assertRaises(KakaoError):
                _exchange()

    def test_network_failure_is_kakao_error(self):
        import httpx

        with patch("httpx.post", side_effect=httpx.ConnectTimeout("timeout")):
            with self.assertRaises(KakaoError):
                _exchange()


class TestFetchAccount(unittest.TestCase):
    def test_returns_id_and_nickname(self):
        payload = {"id": 123456789, "properties": {"nickname": "귀농이"}}
        with patch("httpx.get", return_value=FakeResponse(payload)):
            self.assertEqual(fetch_kakao_account("t"), (123456789, "귀농이"))

    def test_id_as_string_is_accepted(self):
        """JSON 수치가 문자열로 오는 사례가 있다 — 그것 때문에 로그인이 죽지 않게 한다."""
        with patch("httpx.get", return_value=FakeResponse({"id": "123", "properties": {}})):
            kakao_id, _ = fetch_kakao_account("t")
        self.assertEqual(kakao_id, 123)

    def test_nickname_falls_back_to_kakao_account_profile(self):
        """동의 항목·앱 설정에 따라 두 경로 중 한쪽만 채워져 온다."""
        payload = {"id": 1, "kakao_account": {"profile": {"nickname": "농부"}}}
        with patch("httpx.get", return_value=FakeResponse(payload)):
            self.assertEqual(fetch_kakao_account("t")[1], "농부")

    def test_nickname_missing_uses_default(self):
        """닉네임은 표시용이다 — 없다고 로그인을 막지 않는다."""
        with patch("httpx.get", return_value=FakeResponse({"id": 1})):
            self.assertEqual(fetch_kakao_account("t")[1], DEFAULT_NICKNAME)

    def test_blank_nickname_uses_default(self):
        with patch("httpx.get", return_value=FakeResponse({"id": 1, "properties": {"nickname": "  "}})):
            self.assertEqual(fetch_kakao_account("t")[1], DEFAULT_NICKNAME)

    def test_long_nickname_is_truncated_to_column_limit(self):
        """users.nickname 상한(50)을 넘으면 DB 오류로 로그인이 죽는다."""
        with patch("httpx.get", return_value=FakeResponse({"id": 1, "properties": {"nickname": "가" * 80}})):
            self.assertEqual(len(fetch_kakao_account("t")[1]), 50)

    def test_missing_id_is_failure(self):
        """회원번호가 없으면 계정을 식별할 수 없다 — 조용히 넘어가면 안 된다."""
        with patch("httpx.get", return_value=FakeResponse({"properties": {"nickname": "농부"}})):
            with self.assertRaises(KakaoError):
                fetch_kakao_account("t")

    def test_401_is_auth_error(self):
        with patch("httpx.get", return_value=FakeResponse({"msg": "invalid token"}, status_code=401)):
            with self.assertRaises(KakaoAuthError):
                fetch_kakao_account("t")

    def test_sends_bearer_token(self):
        captured: dict[str, object] = {}

        def fake_get(url, headers=None, timeout=None):  # noqa: ANN001, ARG001
            captured.update(headers or {})
            return FakeResponse({"id": 1})

        with patch("httpx.get", side_effect=fake_get):
            fetch_kakao_account("kakao-token")
        self.assertEqual(captured["Authorization"], "Bearer kakao-token")


if __name__ == "__main__":
    unittest.main()
