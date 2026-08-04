"""인증 라우터(docs/auth-security.md). 분리 토큰 JWT — access는 본문, refresh는 httpOnly 쿠키."""

import jwt
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.rate_limit import LOGIN_PER_EMAIL, SIGNUP_GLOBAL, check
from app.core.config import settings
from app.core.errors import AppError
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.db.session import get_db
from app.models.user import User
from app.infra.oauth.kakao_client import (
    KakaoAuthError,
    KakaoError,
    exchange_code_for_token,
    fetch_kakao_account,
)
from app.schemas.auth import (
    AccessTokenResponse,
    KakaoLoginRequest,
    LoginRequest,
    LoginResponse,
    NicknameUpdateRequest,
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
    #
    # 인증 이전 경로라 셀 수 있는 것이 전역뿐이다(IP는 프록시 뒤에서 믿을 수 없다 — rate_limit
    # 모듈 주석). 한 명이 한도를 채우면 그동안 정상 가입도 막히는 것이 이 선택의 대가인데,
    # 가입은 원래 드문 행위라 분당 30건이면 실사용과 부딪히지 않는다.
    check("signup", "global", SIGNUP_GLOBAL)
    try:
        user = auth_service.create_user(db, req.email, req.password, req.nickname)
    except auth_service.EmailAlreadyExists:
        raise AppError(status.HTTP_409_CONFLICT, "EMAIL_EXISTS", "이미 가입된 이메일입니다.")
    return ApiResponse.ok(_user_response(user))


@router.post("/login")
def login(
    req: LoginRequest, response: Response, db: Session = Depends(get_db)
) -> ApiResponse[LoginResponse]:
    # **이메일로 센다.** 무차별 대입은 한 계정을 겨냥하므로 공격 대상 자체가 자연스러운 키이고,
    # 프록시 뒤 IP와 달리 요청자가 위조할 수 없다. 소문자로 맞춰 대소문자만 바꿔 한도를
    # 우회하지 못하게 한다(이메일 로컬파트는 이론상 대소문자를 구분하지만 실무에선 같은 계정이다).
    check("login", req.email.lower(), LOGIN_PER_EMAIL)
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


@router.post("/kakao")
def kakao_login(
    req: KakaoLoginRequest, response: Response, db: Session = Depends(get_db)
) -> ApiResponse[LoginResponse]:
    """카카오 인가코드로 로그인(없으면 가입). **응답은 `/login`과 완전히 같다** —
    FE의 토큰 처리 코드가 그대로 재사용되고 새 스키마가 생기지 않는다.

    FE 흐름은 `docs/auth-security.md` §카카오: FE가 카카오 인가 화면으로 보내고, 카카오가 FE
    콜백(`/login/kakao`)으로 `code`를 돌려주면 FE가 그 코드를 이 엔드포인트로 POST한다.
    **리다이렉트를 백엔드로 받지 않는 이유**: access를 메모리에만 두는 정책이라(docs §토큰 저장)
    서버가 리다이렉트를 받으면 토큰을 FE 메모리로 넘길 길이 없다.

    CSRF 방어(state 대조)는 FE가 한다 — state는 이 브라우저 탭이 시작한 로그인인지를 증명하는
    값이라 sessionStorage에 두고 콜백에서 대조하는 것이 자연스럽다(서버 세션이 없다).
    """
    if not settings.kakao_rest_api_key:
        # 키가 없으면 카카오에 물어볼 수 없다. 조용히 500을 내지 않고 원인을 알린다(§12).
        raise AppError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "KAKAO_NOT_CONFIGURED",
            "카카오 로그인이 설정되지 않았습니다.",
        )
    try:
        token = exchange_code_for_token(
            req.code,
            client_id=settings.kakao_rest_api_key,
            redirect_uri=settings.kakao_redirect_uri,
            client_secret=settings.kakao_client_secret,
        )
        kakao_id, nickname = fetch_kakao_account(token)
    except KakaoAuthError:
        # 인가코드가 만료·재사용된 경우가 대부분이다(1회용). 다시 시도하면 풀린다.
        raise AppError(
            status.HTTP_401_UNAUTHORIZED,
            "KAKAO_AUTH_FAILED",
            "카카오 로그인에 실패했습니다. 다시 시도해 주세요.",
        )
    except KakaoError:
        # 카카오 장애·네트워크 문제 — 우리 잘못이 아니라는 것을 코드로 구분한다(§6).
        raise AppError(
            status.HTTP_502_BAD_GATEWAY,
            "UPSTREAM_UNAVAILABLE",
            "카카오와 통신할 수 없습니다. 잠시 후 다시 시도해 주세요.",
        )

    user, is_new = auth_service.upsert_kakao_user(db, kakao_id, nickname)
    _set_refresh_cookie(response, create_refresh_token(user.id))
    return ApiResponse.ok(
        LoginResponse(
            access_token=create_access_token(user.id),
            user=_user_response(user),
            # 카카오는 닉네임을 주지 않아 기본값으로 시작한다 — 처음 온 사람은 FE가 닉네임
            # 화면으로 보낸다. 그 판단 근거를 FE가 문자열 비교로 추측하지 않게 서버가 알려준다.
            is_new_user=is_new,
        )
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


@router.patch("/me")
def update_me(
    req: NicknameUpdateRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[UserResponse]:
    """닉네임 변경. 인증된 유저가 **자기 것만** 바꾼다 — 대상 id를 받지 않으므로 남의 계정을
    가리킬 방법이 없다(§11 소유권).

    이메일·비밀번호는 여기서 바꾸지 않는다. 이메일은 계정 식별자라 변경에 재검증이 필요하고,
    비밀번호는 현재 비밀번호 확인이 필요해 별개 흐름이다(§2 YAGNI — 요구가 생기면 그때).
    """
    user = auth_service.update_nickname(db, current, req.nickname)
    return ApiResponse.ok(_user_response(user))
