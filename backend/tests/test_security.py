"""인증 보안 경계 검증 — 해싱 왕복, 토큰 발급/검증, 토큰 타입 혼용 차단. 네트워크/DB 불필요.

실행: backend/.venv/Scripts/python.exe -m unittest tests.test_security   (backend/ 에서)
"""

import unittest

import jwt

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPasswordHash(unittest.TestCase):
    def test_hash_verify_roundtrip(self) -> None:
        h = hash_password("correct horse battery")
        self.assertTrue(verify_password("correct horse battery", h))

    def test_wrong_password_fails(self) -> None:
        h = hash_password("correct horse battery")
        self.assertFalse(verify_password("wrong password", h))

    def test_hash_is_not_plaintext(self) -> None:
        # 평문이 해시에 그대로 남지 않아야 한다(§11).
        self.assertNotIn("secret123", hash_password("secret123"))

    def test_long_multibyte_password_does_not_crash(self) -> None:
        # 한글(3바이트) 긴 비밀번호도 bcrypt 72바이트 상한에서 안전하게 처리.
        pw = "가" * 100
        self.assertTrue(verify_password(pw, hash_password(pw)))


class TestJwt(unittest.TestCase):
    def test_access_token_roundtrip(self) -> None:
        self.assertEqual(decode_token(create_access_token(42), "access"), 42)

    def test_refresh_token_roundtrip(self) -> None:
        self.assertEqual(decode_token(create_refresh_token(7), "refresh"), 7)

    def test_refresh_cannot_be_used_as_access(self) -> None:
        # 토큰 타입 혼용 차단 — refresh를 access로 검증하면 거부.
        with self.assertRaises(ValueError):
            decode_token(create_refresh_token(1), "access")

    def test_tampered_token_rejected(self) -> None:
        token = create_access_token(1)
        with self.assertRaises(jwt.PyJWTError):
            decode_token(token + "x", "access")


if __name__ == "__main__":
    unittest.main()
