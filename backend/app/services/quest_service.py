"""리텐션 장치(펫·레벨·데일리 퀘스트) 유스케이스 — PRD.md §14.5.

**이 모듈은 농사 판단에 전혀 개입하지 않는다.** 적합도·행동추천·위험판정은 레벨을 모른다.
여기서 하는 일은 "제품을 실제로 쓴 행위"를 하루 단위로 기록하고, 그 로그에서 경험치/레벨/
펫 단계를 **파생 계산**하는 것뿐이다. 저장되는 상태는 완료 로그 한 종류 —
경험치 카운터가 없으므로 로그와 어긋날 방법도 없다(결정론, CLAUDE.md §2). RNG 없음.

퀘스트 목록·경험치·레벨 곡선은 여기 상수로 둔다. 농업 기준값이 아니라 UX 파라미터라
시드 데이터 분리(§18-2) 대상이 아니다 — 바꿔도 농사 계산 결과는 변하지 않는다.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import User, UserDailyQuest


@dataclass(frozen=True)
class Quest:
    code: str
    label: str
    exp: int


# 하루 3개 고정. **모두 "제품을 실제로 쓰는 행위"만 넣는다** — 출석 체크처럼 제품과 무관한
# 클릭을 넣으면 접속 수만 늘고 유저는 아무것도 얻지 못한다(PRD §14.5).
QUESTS: tuple[Quest, ...] = (
    Quest("view_short", "오늘 단기 탭 확인하기", 10),
    Quest("view_long", "장기 탭 확인하기", 10),
    Quest("ask_chat", "텃밭이에게 질문하기", 20),
)
QUEST_BY_CODE = {q.code: q for q in QUESTS}

# 레벨 곡선: 100exp당 1레벨(하루 다 하면 40exp → 2~3일에 1레벨).
EXP_PER_LEVEL = 100


@dataclass(frozen=True)
class PetStage:
    min_level: int
    label: str
    emoji: tuple[str, str]  # (새싹이, 흙강아지) 같은 순서로 PETS와 대응


# 4단계(요구 3단계 이상). 이모지를 쓰는 이유는 에셋 없이 지금 돌아가기 때문이다.
# ponytail: 이모지 = 임시 외형. 일러스트가 나오면 emoji 대신 이미지 경로로 갈아끼우면 된다.
PET_STAGES: tuple[PetStage, ...] = (
    PetStage(1, "씨앗", ("🌰", "🥚")),
    PetStage(3, "새싹", ("🌱", "🐣")),
    PetStage(6, "자람", ("🌿", "🐕")),
    PetStage(10, "열매", ("🌻", "🐕‍🦺")),
)

PETS: tuple[tuple[str, str], ...] = (("sprout", "새싹이"), ("pup", "흙강아지"))
PET_CODES = [code for code, _ in PETS]
DEFAULT_PET_CODE = PET_CODES[0]


def total_exp(db: Session, user_id: int) -> int:
    """완료 로그 전체를 경험치로 환산. 사라진 퀘스트 코드(카탈로그 개편)는 0점으로 무시한다 —
    옛 로그 때문에 조회가 죽는 것보다 낫다."""
    rows = (
        db.query(UserDailyQuest.quest_code, func.count())
        .filter(UserDailyQuest.user_id == user_id)
        .group_by(UserDailyQuest.quest_code)
        .all()
    )
    return sum(QUEST_BY_CODE[code].exp * n for code, n in rows if code in QUEST_BY_CODE)


def level_of(exp: int) -> int:
    return exp // EXP_PER_LEVEL + 1


def exp_into_level(exp: int) -> int:
    """현재 레벨 안에서 쌓은 경험치(진행바용). 다음 레벨까지는 EXP_PER_LEVEL - 이 값."""
    return exp % EXP_PER_LEVEL


def stage_of(level: int) -> PetStage:
    """레벨이 속한 펫 단계. 경계값 포함(min_level 이상 중 가장 높은 단계)."""
    matched = PET_STAGES[0]
    for stage in PET_STAGES:
        if level >= stage.min_level:
            matched = stage
    return matched


def pet_of(user: User) -> tuple[str, str, int]:
    """(코드, 이름, PETS 내 인덱스). 미선택(NULL)/모르는 코드는 기본 펫으로 읽는다."""
    code = user.pet_code if user.pet_code in PET_CODES else DEFAULT_PET_CODE
    index = PET_CODES.index(code)
    return code, PETS[index][1], index


def done_codes(db: Session, user_id: int, on: date) -> set[str]:
    rows = (
        db.query(UserDailyQuest.quest_code)
        .filter(UserDailyQuest.user_id == user_id, UserDailyQuest.quest_date == on)
        .all()
    )
    return {code for (code,) in rows}


def complete(db: Session, user_id: int, quest_code: str, on: date) -> None:
    """퀘스트 완료 기록. **멱등** — 같은 날 같은 퀘스트를 다시 부르면 아무 일도 없다.
    중복은 UNIQUE 제약이 막고(동시 요청 포함) IntegrityError를 여기서 흡수한다."""
    if quest_code not in QUEST_BY_CODE:
        raise AppError(404, "QUEST_NOT_FOUND", "없는 퀘스트입니다.")
    db.add(UserDailyQuest(user_id=user_id, quest_date=on, quest_code=quest_code))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # 이미 완료 — 정상 흐름이다


def progress(db: Session, user: User, on: date) -> dict[str, object]:
    """화면 하나를 채우는 상태 전부(레벨·펫·오늘 퀘스트). FE가 이 응답만으로 렌더한다."""
    exp = total_exp(db, user.id)
    level = level_of(exp)
    stage = stage_of(level)
    pet_code, pet_name, pet_index = pet_of(user)
    done = done_codes(db, user.id, on)
    return {
        "level": level,
        "exp": exp,
        "exp_into_level": exp_into_level(exp),
        "exp_per_level": EXP_PER_LEVEL,
        "pet": {
            "code": pet_code,
            "name": pet_name,
            "emoji": stage.emoji[pet_index],
            "stage_label": stage.label,
        },
        # 고를 수 있는 펫 목록도 같이 준다 — FE가 펫 카탈로그를 따로 들고 있으면 펫을 추가할 때
        # 두 곳을 고쳐야 하고, 한 곳을 잊으면 목록에 없는 펫이 생긴다.
        "pets": [
            {"code": code, "name": name, "emoji": stage.emoji[i]}
            for i, (code, name) in enumerate(PETS)
        ],
        "quests": [
            {"code": q.code, "label": q.label, "exp": q.exp, "is_done": q.code in done}
            for q in QUESTS
        ],
    }


def set_pet(db: Session, user: User, pet_code: str) -> None:
    """펫 교체. 화이트리스트 밖 코드는 거절한다(신뢰 경계 검증, CLAUDE.md §17)."""
    if pet_code not in PET_CODES:
        raise AppError(400, "PET_NOT_FOUND", "없는 펫입니다.")
    user.pet_code = pet_code
    db.commit()
