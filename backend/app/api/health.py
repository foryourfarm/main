from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> ApiResponse[str]:
    # DB 연결까지 확인 — 실패하면 예외 핸들러가 공통 포맷으로 응답(main.py).
    db.execute(text("SELECT 1"))
    return ApiResponse.ok("ok")
