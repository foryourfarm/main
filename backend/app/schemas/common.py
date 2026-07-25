from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiError(BaseModel):
    code: str
    message: str


class ApiResponse(BaseModel, Generic[T]):
    """성공/실패 공통 응답 래퍼(CLAUDE.md §6)."""

    success: bool
    data: T | None = None
    error: ApiError | None = None

    @classmethod
    def ok(cls, data: T) -> "ApiResponse[T]":
        return cls(success=True, data=data, error=None)

    @classmethod
    def fail(cls, code: str, message: str) -> "ApiResponse[T]":
        return cls(success=False, data=None, error=ApiError(code=code, message=message))
