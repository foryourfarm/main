"""인증 의존성. get_current_user는 Bearer access 토큰을 검증해 현재 유저를 돌려준다(docs/auth-security.md).
인가(소유권 검증)는 여기가 아니라 서비스 계층에서(CLAUDE.md §11)."""

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.services import auth_service

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if cred is None:
        raise AppError(401, "UNAUTHORIZED", "인증이 필요합니다.")
    try:
        user_id = decode_token(cred.credentials, "access")
    except (jwt.PyJWTError, ValueError):
        raise AppError(401, "INVALID_TOKEN", "유효하지 않은 인증 토큰입니다.")
    user = auth_service.get_user(db, user_id)
    if user is None:
        raise AppError(401, "UNAUTHORIZED", "인증이 필요합니다.")
    return user
