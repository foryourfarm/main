from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    """계정(DB.md §3.1). 비밀번호는 해시만 저장(평문 금지, CLAUDE.md §11)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str] = mapped_column()
    nickname: Mapped[str] = mapped_column()
    # 챗봇 펫 종류(PRD.md §14.5). NULL이면 기본 펫 — 기존 계정을 마이그레이션으로 백필하지 않는다.
    # 값이 없어도 화면이 돌아가야 하고, 유저가 직접 고른 것과 기본값은 구분돼야 한다.
    pet_code: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
