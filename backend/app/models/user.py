from datetime import datetime

from sqlalchemy import BigInteger, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    """계정(DB.md §3.1). 비밀번호는 해시만 저장(평문 금지, CLAUDE.md §11).

    **계정은 두 종류다**(0037). 이메일 계정은 `email`+`password_hash`로, 카카오 계정은
    `kakao_id`로 식별한다. 카카오 계정은 앞의 둘이 NULL이므로 읽는 쪽이 방어해야 한다
    (`auth_service.authenticate`가 그 경계다).
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str | None] = mapped_column(unique=True, nullable=True)
    """이메일 계정의 식별자. **카카오 계정은 NULL** — 카카오에서 이메일을 받지 않는다(0037)."""
    password_hash: Mapped[str | None] = mapped_column(nullable=True)
    """카카오 계정은 NULL — 비밀번호가 없다(카카오가 본인 확인을 대신한다)."""
    nickname: Mapped[str] = mapped_column()
    kakao_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    """카카오 회원번호. 이메일 계정은 NULL. 이 값이 카카오 계정의 유일한 식별자다."""
    # 챗봇 펫 종류(PRD.md §14.5). NULL이면 기본 펫 — 기존 계정을 마이그레이션으로 백필하지 않는다.
    # 값이 없어도 화면이 돌아가야 하고, 유저가 직접 고른 것과 기본값은 구분돼야 한다.
    pet_code: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
