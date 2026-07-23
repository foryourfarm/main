from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import chat, health
from app.schemas.common import ApiResponse

app = FastAPI(title="For Your Farm API", version="0.1.0")

app.include_router(health.router)
app.include_router(chat.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # 어떤 예외도 공통 실패 포맷으로(CLAUDE.md §6). 상세 코드는 도메인 예외 생기면 확장.
    body = ApiResponse[str].fail("INTERNAL_ERROR", "예상치 못한 오류가 발생했습니다.")
    return JSONResponse(status_code=500, content=body.model_dump())
