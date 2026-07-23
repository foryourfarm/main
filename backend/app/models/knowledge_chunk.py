from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class KnowledgeChunk(Base):
    """챗봇 RAG 문서 조각 + bge-m3 임베딩(1024차원), pgvector (DB.md §3.15). 핵심 예측 기능은 사용 안 함."""

    __tablename__ = "knowledge_chunk"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_ref: Mapped[str] = mapped_column()
    crop_id: Mapped[int | None] = mapped_column(ForeignKey("crop.id"))
    content: Mapped[str] = mapped_column()
    embedding: Mapped[list[float]] = mapped_column(Vector(1024))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
