from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserDailyQuest(Base):
    """데일리 퀘스트 완료 로그(PRD.md §14.5). 런타임 기록 — 시드/마스터 아님.

    **경험치·레벨 컬럼이 없는 것은 의도다.** 이 로그의 합이 곧 경험치이고 레벨은 거기서
    파생 계산한다(quest_service). 카운터를 따로 들면 로그와 어긋날 수 있고(중복 적립·롤백),
    같은 입력이 같은 출력을 내야 한다는 결정론 원칙과 충돌한다(CLAUDE.md §2).

    하루 한 번은 UNIQUE 제약이 강제한다 — 애플리케이션 검사에만 맡기면 동시 요청 두 개가
    같은 날짜를 함께 통과한다.
    """

    __tablename__ = "user_daily_quest"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    quest_date: Mapped[date] = mapped_column(Date)  # 완료한 날(서버 로컬 날짜)
    quest_code: Mapped[str] = mapped_column()  # quest_service.QUESTS의 키
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "quest_date", "quest_code", name="uq_user_daily_quest"),
    )
