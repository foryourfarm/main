from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    nickname: str = Field(min_length=1, max_length=50)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class KakaoLoginRequest(BaseModel):
    """카카오 인가코드. `redirect_uri`는 받지 않는다 — 서버 설정값을 쓴다(kakao_client 참고)."""

    code: str = Field(min_length=1, max_length=512)


class UserResponse(BaseModel):
    """유저 공개 정보. SQLAlchemy 모델을 그대로 노출하지 않는다(CLAUDE.md §6). password_hash 미포함."""

    id: int
    email: str | None
    """카카오 계정은 null — 카카오에서 이메일을 받지 않는다(0037)."""
    nickname: str


class NicknameUpdateRequest(BaseModel):
    """닉네임 변경. 가입 때와 같은 제약을 쓴다 — 두 경로가 다르면 한쪽으로만 이상한 값이 들어온다."""

    nickname: str = Field(min_length=1, max_length=50)


class LoginResponse(BaseModel):
    access_token: str
    user: UserResponse
    is_new_user: bool = False
    """이 로그인에서 계정이 **새로 만들어졌나**. 카카오는 로그인이 곧 가입이라 FE가 이걸로
    "닉네임부터 받는 화면"으로 보낸다. 이메일 로그인은 항상 False(가입이 별도 단계다)."""


class AccessTokenResponse(BaseModel):
    access_token: str
