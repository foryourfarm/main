from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """이전 대화 한 턴. 멀티턴은 서버가 저장하지 않고 클라이언트가 매 요청에 실어보낸다
    (챗봇은 온디맨드·비영속 — docs/llm-integration.md §2). role은 user/assistant만."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    """상담 챗봇 요청. crop_id를 주면 그 작물 문서로만 검색 근거를 한정한다(없으면 전체 + 모델이 되물음)."""

    question: str = Field(min_length=1, max_length=1000)
    crop_id: int | None = Field(default=None, ge=1)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)
    # 로그인 유저가 특정 밭 기준 답변을 원할 때. 소유권 검증 후 밭 작물/토양을 프롬프트에 주입("내 땅 맞춤").
    # 게스트는 무시된다(밭 컨텍스트는 인증 유저만).
    farm_id: int | None = Field(default=None, ge=1)
