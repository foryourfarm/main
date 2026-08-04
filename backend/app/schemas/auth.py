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


class LoginResponse(BaseModel):
    access_token: str
    user: UserResponse


class AccessTokenResponse(BaseModel):
    access_token: str
