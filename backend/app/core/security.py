"""비밀번호 해싱 + JWT 발급/검증(docs/auth-security.md).

- 비밀번호: bcrypt 해시만 저장(평문 금지, CLAUDE.md §11/§18-6).
- JWT: PyJWT HS256. payload는 서명일 뿐 암호화 아님 → 민감정보 없이 sub/type/exp만.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings

# bcrypt는 비밀번호 72바이트까지만 처리(초과 시 예외). 다국어(한글=3바이트)도 안전하게 바이트 기준 절단.
_BCRYPT_MAX_BYTES = 72


def _to_bcrypt_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_to_bcrypt_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(_to_bcrypt_bytes(password), password_hash.encode("utf-8"))


def _create_token(user_id: int, expires: timedelta, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "type": token_type, "iat": now, "exp": now + expires}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: int) -> str:
    return _create_token(user_id, timedelta(minutes=settings.access_token_expire_min), "access")


def create_refresh_token(user_id: int) -> str:
    return _create_token(user_id, timedelta(days=settings.refresh_token_expire_days), "refresh")


def decode_token(token: str, expected_type: str) -> int:
    """토큰 검증 후 user_id 반환. 서명/만료 문제는 jwt.PyJWTError,
    타입 불일치(access↔refresh 혼용)는 ValueError로 던진다."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != expected_type:
        raise ValueError("token type mismatch")
    return int(payload["sub"])
