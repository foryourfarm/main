from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.rate_limit import rate_limit_chat
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


@router.post("/chat", dependencies=[Depends(rate_limit_chat)])
def chat(
    req: ChatRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """상담 챗봇(SSE 스트리밍).

    **로그인이 필요하다.** 종전에는 토큰이 없으면 게스트로 흘려보냈는데, 그건 `PRD.md` §4.1이
    정한 "로그인 필수 / 비로그인 접근 시 로그인으로 리다이렉트"와 어긋난 상태였다(§4.6 챗봇
    항목에도 게스트 얘기는 없다). 게스트 경로는 명세에 없이 구현 쪽에서 자란 것이다(§18-7).

    보안상으로도 이 경로만 예외였다 — **비인증으로 GPU를 태울 수 있는 유일한 엔드포인트**라
    인증 없이 LLM 비용을 소진시킬 수 있었다. 로그인을 요구하면 레이트리밋을 `user.id`로 걸 수
    있어(위조 불가) 프록시 뒤 IP 추정에 기대지 않아도 된다.

    SSE라 `ApiResponse` 래퍼를 쓰지 않는다(§6 스트리밍 예외). 스트림 내부 오류·근거 없음은
    `chat_service`가 폴백 문구로 흡수한다.
    """
    # 세션이 지정되면 서버 저장 히스토리를 쓰므로 요청 본문의 history는 무시된다(chat_service).
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
