from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_current_user_optional
from app.core.config import settings
from app.db.session import get_db
from app.models import User
from app.schemas.chat import (
    SESSION_ID_PATTERN,
    ChatHistoryMessage,
    ChatRequest,
    ChatSessionSummary,
)
from app.schemas.common import ApiResponse
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


@router.get("/chat/history")
def chat_history(
    session_id: str = Query(pattern=SESSION_ID_PATTERN),
    current: User = Depends(get_current_user),  # 내 대화만 — 게스트는 저장 자체가 없다
    db: Session = Depends(get_db),
) -> ApiResponse[list[ChatHistoryMessage]]:
    """저장된 대화를 돌려줘 화면을 복원한다. 리로드해도 대화가 이어져 보이게 하는 것이 목적.

    소유권은 (user_id, session_id) 스코프로 강제된다 — 남의 session_id를 넣어도 빈 목록이다(§11).
    """
    rows = chat_service.load_history(db, current.id, session_id, settings.chat_history_display_limit)
    return ApiResponse.ok([ChatHistoryMessage(role=role, content=content) for role, content in rows])


@router.get("/chat/sessions")
def chat_sessions(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[list[ChatSessionSummary]]:
    """내 대화 스레드 목록(최근 활동 순). **새 대화는 이 API를 부르지 않는다** —
    FE가 uuid를 새로 만들면 그게 곧 새 스레드고, 첫 답변이 저장되는 순간 목록에 나타난다."""
    return ApiResponse.ok(
        chat_service.list_sessions(db, current.id, settings.chat_session_list_limit)
    )


@router.delete("/chat/sessions/{session_id}")
def delete_chat_session(
    session_id: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[int]:
    """스레드 삭제. 내 것이 아니거나 없으면 0을 돌려준다 — 404로 남의 스레드 존재 여부를
    알려주지 않는다(§11)."""
    return ApiResponse.ok(chat_service.delete_session(db, current.id, session_id))
