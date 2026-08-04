import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import admin, auth, chat, dashboard, farms, health, quests
from app.core.config import settings
from app.core.log_config import setup_logging
from app.schemas.common import ApiResponse

setup_logging()
logger = logging.getLogger("app.request")

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
app.include_router(dashboard.router)
app.include_router(quests.router)
app.include_router(admin.router)


def _ctx(request: Request, status: int) -> dict[str, object]:
    """로그에 실을 요청 컨텍스트. **쿼리스트링·본문은 넣지 않는다** — 로그인 본문에
    비밀번호가, 쿼리에 토큰이 실릴 수 있다(§17)."""
    return {
        "http_method": request.method,
        "http_path": request.url.path,
        "http_status": status,
    }


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # AppError는 도메인 code를, 그 외 HTTPException은 HTTP_상태 코드를 실어 공통 실패 포맷으로(§6).
    code = getattr(exc, "code", None) or f"HTTP_{exc.status_code}"
    # 5xx는 우리 잘못이라 ERROR, 4xx는 클라이언트 입력이라 WARNING이 아니라 INFO다 —
    # 401/404가 정상 흐름(비로그인·없는 밭)이라 WARNING으로 두면 경보가 무의미해진다.
    if exc.status_code >= 500:
        logger.error("%s %s -> %s", request.method, request.url.path, code,
                     extra=_ctx(request, exc.status_code))
    else:
        logger.info("%s %s -> %s", request.method, request.url.path, code,
                    extra=_ctx(request, exc.status_code))
    body = ApiResponse[str].fail(code, str(exc.detail))
    return JSONResponse(status_code=exc.status_code, content=body.model_dump())


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # 어느 필드가 왜 틀렸는지 남긴다 — 값은 빼고 위치·사유만(본문에 비밀번호가 있을 수 있다).
    fields = [
        {"loc": ".".join(str(p) for p in e.get("loc", ())), "type": e.get("type")}
        for e in exc.errors()
    ]
    logger.warning("%s %s -> VALIDATION_ERROR %s", request.method, request.url.path, fields,
                   extra=_ctx(request, 422))
    body = ApiResponse[str].fail("VALIDATION_ERROR", "입력값이 올바르지 않습니다.")
    return JSONResponse(status_code=422, content=body.model_dump())


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # 어떤 예외도 공통 실패 포맷으로(CLAUDE.md §6). 상세 코드는 도메인 예외 생기면 확장.
    #
    # **트레이스백을 반드시 남긴다.** 종전엔 여기서 예외를 삼키고 로그를 한 줄도 남기지
    # 않아, 500이 나도 `severity>=ERROR` 조회에 아무것도 안 걸렸다(2026-08-03 실측).
    # 유저에게는 상세를 숨기되(공격자에게 내부 구조를 주지 않는다) 서버 로그에는 전부 남긴다.
    logger.exception("%s %s -> INTERNAL_ERROR", request.method, request.url.path,
                     extra=_ctx(request, 500))
    body = ApiResponse[str].fail("INTERNAL_ERROR", "예상치 못한 오류가 발생했습니다.")
    return JSONResponse(status_code=500, content=body.model_dump())
