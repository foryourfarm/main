from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import auth, chat, farms, health
from app.core.config import settings
from app.schemas.common import ApiResponse

app = FastAPI(title="For Your Farm API", version="0.1.0")

# CORS — refresh 쿠키가 크로스오리진으로 오가려면 명시 오리진 + credentials 필요(docs/auth-security.md).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(farms.router)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # AppError는 도메인 code를, 그 외 HTTPException은 HTTP_상태 코드를 실어 공통 실패 포맷으로(§6).
    code = getattr(exc, "code", None) or f"HTTP_{exc.status_code}"
    body = ApiResponse[str].fail(code, str(exc.detail))
    return JSONResponse(status_code=exc.status_code, content=body.model_dump())


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    body = ApiResponse[str].fail("VALIDATION_ERROR", "입력값이 올바르지 않습니다.")
    return JSONResponse(status_code=422, content=body.model_dump())


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # 어떤 예외도 공통 실패 포맷으로(CLAUDE.md §6). 상세 코드는 도메인 예외 생기면 확장.
    body = ApiResponse[str].fail("INTERNAL_ERROR", "예상치 못한 오류가 발생했습니다.")
    return JSONResponse(status_code=500, content=body.model_dump())
