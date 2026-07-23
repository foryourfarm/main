from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.chat import ChatRequest
from app.services import chat_service

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post("/chat")
def chat(req: ChatRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    # SSE 스트리밍 — ApiResponse 래퍼를 쓰지 않는다(CLAUDE.md §6 스트리밍 예외).
    # 스트림 내부 오류/근거 없음은 chat_service가 폴백 문구로 흡수한다.
    return StreamingResponse(
        chat_service.stream_answer(db, req.question, req.crop_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
