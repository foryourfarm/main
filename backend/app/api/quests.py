"""리텐션 장치 엔드포인트(펫·레벨·데일리 퀘스트) — PRD.md §14.5, 계약은 docs/quest-pet-api.md.

세 엔드포인트가 **같은 응답(QuestProgress)**을 돌려준다. FE는 무엇을 호출하든 받은 상태로
화면을 통째로 갈아끼우면 되고, 별도 재조회가 없다.
"""

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.common import ApiResponse
from app.schemas.quest import PetChangeRequest, QuestProgress
from app.services import quest_service

router = APIRouter(prefix="/api/v1", tags=["quests"])


@router.get("/quests/today")
def today(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[QuestProgress]:
    # 날짜는 서버 로컬 기준. 유저 타임존을 받지 않으므로 자정 경계는 서버 시간으로 갈린다.
    return ApiResponse.ok(quest_service.progress(db, current, date.today()))


@router.post("/quests/{quest_code}")
def complete(
    quest_code: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[QuestProgress]:
    """퀘스트 완료(멱등 — 같은 날 두 번 눌러도 경험치는 한 번만).

    # ponytail: 완료 판정은 클라이언트 신뢰다. 유저가 직접 이 API를 호출하면 탭을 안 보고도
    # 채울 수 있지만 속여봐야 자기 손해인 넛지 장치라 서버 열람 검증을 붙이지 않는다
    # (PRD §14.5 한계 표기). 보상이 생기면 그때 서버 이벤트 기반으로 승격할 것.
    """
    today_ = date.today()
    quest_service.complete(db, current.id, quest_code, today_)
    return ApiResponse.ok(quest_service.progress(db, current, today_))


@router.put("/pet")
def change_pet(
    req: PetChangeRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[QuestProgress]:
    quest_service.set_pet(db, current, req.code)
    return ApiResponse.ok(quest_service.progress(db, current, date.today()))
