from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 의존성. 요청 단위 세션 — 트랜잭션 경계는 서비스 계층에서(CLAUDE.md §10)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
