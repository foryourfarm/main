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
    """이메일+비밀번호 검증. 실패 시 None(사유는 구분하지 않음 — 계정 열거 방지는 라우터 문구에서).

    **`password_hash`가 없는 계정은 비밀번호로 로그인할 수 없다**(0037 이후 카카오 계정).
    이 검사가 없으면 `verify_password`가 None을 받아 예외로 500이 난다.
    """
    user = db.query(User).filter(User.email == email).first()
    if user is None or user.password_hash is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def update_nickname(db: Session, user: User, nickname: str) -> User:
    """닉네임 변경. 유저가 자기 것만 바꾸므로 소유권 검증은 "인증된 유저 객체"로 이미 끝났다.

    카카오 계정은 닉네임을 못 받아 기본값(`카카오 사용자`)으로 시작하는데, 종전에는 그 값을
    **바꿀 방법이 아예 없었다**(수정 엔드포인트도, 화면도 없었다). 이메일 가입자도 가입 후에는
    못 바꿨으므로 두 경로 모두를 여기서 해결한다.
    """
    user.nickname = nickname
    db.commit()
    db.refresh(user)
    return user


def upsert_kakao_user(db: Session, kakao_id: int, nickname: str) -> tuple[User, bool]:
    """카카오 회원번호로 계정을 찾거나 만든다(로그인 = 가입, 별도 가입 화면 없음).

    반환값의 두 번째는 **이 호출에서 새로 만들었나**다 — 카카오는 로그인이 곧 가입이라
    "처음 온 사람"을 이 값으로만 구분할 수 있고, FE가 닉네임 화면으로 보낼 근거가 된다.

    **기존 이메일 계정과 자동으로 잇지 않는다.** 이메일이 같다는 사실만으로 이어붙이면 카카오
    쪽 이메일이 미인증일 때 남의 계정에 들어가는 경로가 된다. 그래서 카카오 계정은 `kakao_id`로만
    식별하고 이메일은 받지도 않는다(0037). 같은 사람이 두 방식으로 들어오면 계정이 둘이 되는데,
    그건 나중에 "명시적 계정 연결" 화면으로 풀 문제다(§2 YAGNI).

    **닉네임은 최초 생성 때만 쓴다.** 매번 덮으면 유저가 우리 쪽에서 바꾼 이름이 카카오 닉네임으로
    조용히 되돌아간다.
    """
    user = db.query(User).filter(User.kakao_id == kakao_id).first()
    if user is not None:
        return user, False

    user = User(kakao_id=kakao_id, nickname=nickname, email=None, password_hash=None)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # 같은 카카오 계정으로 동시에 두 번 들어온 경우 — UNIQUE가 막았다. 먼저 만들어진 행을 쓴다.
        # 이때는 "내가 만든 것"이 아니므로 신규로 보지 않는다(닉네임 화면이 두 번 뜨지 않게).
        db.rollback()
        existing = db.query(User).filter(User.kakao_id == kakao_id).first()
        if existing is None:
            raise
        return existing, False
    db.refresh(user)
    return user, True


def get_user(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)
