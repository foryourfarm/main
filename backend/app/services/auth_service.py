"""인증 유스케이스 + 트랜잭션 경계(CLAUDE.md §10). 라우터는 HTTP 관심사만, 커밋/도메인 판정은 여기서."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User


class EmailAlreadyExists(Exception):
    """이메일 UNIQUE 위반. 라우터가 409로 매핑한다."""


def create_user(db: Session, email: str, password: str, nickname: str) -> User:
    user = User(email=email, password_hash=hash_password(password), nickname=nickname)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise EmailAlreadyExists from None
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    """이메일+비밀번호 검증. 실패 시 None(사유는 구분하지 않음 — 계정 열거 방지는 라우터 문구에서)."""
    user = db.query(User).filter(User.email == email).first()
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


def get_user(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)
