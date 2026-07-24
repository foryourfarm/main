"""인증 라우터(docs/auth-security.md). 분리 토큰 JWT — access는 본문, refresh는 httpOnly 쿠키."""

import jwt
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.errors import AppError
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    LoginResponse,
    SignupRequest,
    UserResponse,
)
from app.schemas.common import ApiResponse
from app.services import auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
REFRESH_PATH = "/api/v1/auth/refresh"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        httponly=True,  # JS 접근 차단(XSS 방어)
        secure=settings.cookie_secure,  # 운영(HTTPS)에서만 True
        samesite=settings.cookie_samesite,  # CSRF 방어
        path=REFRESH_PATH,  # refresh 엔드포인트에만 전송 → 공격면 최소
        max_age=settings.refresh_token_expire_days * 86400,
    )


def _user_response(user: User) -> UserResponse:
    return UserResponse(id=user.id, email=user.email, nickname=user.nickname)


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(req: SignupRequest, db: Session = Depends(get_db)) -> ApiResponse[UserResponse]:
    # 가입만 하고 토큰은 발급하지 않는다 → FE가 로그인 화면으로 이동시킨다(docs/auth-security.md).
    try:
        user = auth_service.create_user(db, req.email, req.password, req.nickname)
    except auth_service.EmailAlreadyExists:
        raise AppError(status.HTTP_409_CONFLICT, "EMAIL_EXISTS", "이미 가입된 이메일입니다.")
    return ApiResponse.ok(_user_response(user))


@router.post("/login")
def login(
    req: LoginRequest, response: Response, db: Session = Depends(get_db)
) -> ApiResponse[LoginResponse]:
    user = auth_service.authenticate(db, req.email, req.password)
    if user is None:
        # 문구 일반화 — 어느 필드가 틀렸는지/계정 존재 여부를 노출하지 않는다(계정 열거 방지).
        raise AppError(
            status.HTTP_401_UNAUTHORIZED,
            "INVALID_CREDENTIALS",
            "이메일 또는 비밀번호가 올바르지 않습니다.",
        )
    _set_refresh_cookie(response, create_refresh_token(user.id))
    return ApiResponse.ok(
        LoginResponse(access_token=create_access_token(user.id), user=_user_response(user))
    )


@router.post("/refresh")
def refresh(request: Request, db: Session = Depends(get_db)) -> ApiResponse[AccessTokenResponse]:
    token = request.cookies.get(REFRESH_COOKIE)
    if token is None:
        raise AppError(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", "인증이 필요합니다.")
    try:
        user_id = decode_token(token, "refresh")
    except (jwt.PyJWTError, ValueError):
        raise AppError(
            status.HTTP_401_UNAUTHORIZED, "INVALID_TOKEN", "세션이 만료되었습니다. 다시 로그인해 주세요."
        )
    if auth_service.get_user(db, user_id) is None:  # 삭제된 계정의 refresh 무효화
        raise AppError(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", "인증이 필요합니다.")
    return ApiResponse.ok(AccessTokenResponse(access_token=create_access_token(user_id)))


@router.post("/logout")
def logout(response: Response) -> ApiResponse[str]:
    response.delete_cookie(key=REFRESH_COOKIE, path=REFRESH_PATH)
    return ApiResponse.ok("logged out")


@router.get("/me")
def me(current: User = Depends(get_current_user)) -> ApiResponse[UserResponse]:
    return ApiResponse.ok(_user_response(current))
