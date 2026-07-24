from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ChatMessage(Base):
    """상담 챗봇 대화 로그(DB.md §3.16). 런타임 기록 — 시드/마스터 아님.
    멀티턴 히스토리를 (user_id, session_id)로 스코프해 로드/저장한다(소유권, CLAUDE.md §11).
    게스트(비로그인)는 저장하지 않고 클라이언트 history 재전송 경로를 그대로 쓴다."""

    __tablename__ = "chat_message"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    session_id: Mapped[str] = mapped_column()  # 클라가 만든 uuid4(대화 스레드 키)
    role: Mapped[str] = mapped_column()  # 'user' | 'assistant'
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 히스토리 로드가 (user_id, session_id)로 필터 + id(=삽입순) 정렬이라 이 순서로 인덱스.
    __table_args__ = (Index("ix_chat_message_user_session", "user_id", "session_id", "id"),)
