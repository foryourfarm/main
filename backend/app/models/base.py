from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 선언적 매핑 베이스. 스키마 자체는 Alembic이 관리하고,
    모델은 그 스키마에 매핑만 한다(런타임 create_all 사용 안 함, CLAUDE.md §10)."""

    pass
