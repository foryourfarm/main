from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_optional
from app.db.session import get_db
from app.models import User
from app.schemas.chat import ChatRequest
from app.services import chat_service

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post("/chat")
def chat(
    req: ChatRequest,
    current: User | None = Depends(get_current_user_optional),  # 게스트 허용(토큰 없으면 None)
    db: Session = Depends(get_db),
) -> StreamingResponse:
    # SSE 스트리밍 — ApiResponse 래퍼를 쓰지 않는다(CLAUDE.md §6 스트리밍 예외).
    # 스트림 내부 오류/근거 없음은 chat_service가 폴백 문구로 흡수한다.
    # 로그인 유저면 밭 컨텍스트 주입("내 땅 맞춤"), 게스트는 기존 무상태 경로.
    history = [(m.role, m.content) for m in req.history]
    return StreamingResponse(
        chat_service.stream_answer(
            db,
            req.question,
            req.crop_id,
            history,
            user=current,
            farm_id=req.farm_id,
            session_id=req.session_id,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
