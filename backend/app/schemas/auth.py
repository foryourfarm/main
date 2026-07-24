from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    nickname: str = Field(min_length=1, max_length=50)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    """유저 공개 정보. SQLAlchemy 모델을 그대로 노출하지 않는다(CLAUDE.md §6). password_hash 미포함."""

    id: int
    email: str
    nickname: str


class LoginResponse(BaseModel):
    access_token: str
    user: UserResponse


class AccessTokenResponse(BaseModel):
    access_token: str
