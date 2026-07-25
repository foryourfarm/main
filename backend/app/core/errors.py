from fastapi import HTTPException


class AppError(HTTPException):
    """도메인 에러 코드를 실은 HTTP 예외. 핸들러가 ApiResponse.fail(code, message)로 변환한다(CLAUDE.md §6).
    code는 문자열 상수로 관리(EMAIL_EXISTS, INVALID_CREDENTIALS 등)."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(status_code=status_code, detail=message)
        self.code = code
