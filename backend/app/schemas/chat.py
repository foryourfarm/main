from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """상담 챗봇 요청. crop_id를 주면 그 작물 문서로만 검색 근거를 한정한다(없으면 전체)."""

    question: str = Field(min_length=1, max_length=1000)
    crop_id: int | None = Field(default=None, ge=1)
