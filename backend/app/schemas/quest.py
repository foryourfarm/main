from pydantic import BaseModel


class PetState(BaseModel):
    stage_code: str  # FE가 이 코드로 단계 일러스트를 찾는다(frontend/lib/pet.ts STAGE_IMAGE)
    name: str
    emoji: str  # 일러스트를 못 쓰는 자리의 폴백
    stage_label: str


class QuestState(BaseModel):
    code: str
    label: str
    exp: int
    is_done: bool


class QuestProgress(BaseModel):
    """펫·레벨·오늘 퀘스트 = 화면 하나를 채우는 상태 전부(PRD.md §14.5).
    조회/완료 둘 다 이걸 돌려줘 FE가 응답을 통째로 갈아끼우면 되게 한다."""

    level: int
    exp: int
    exp_into_level: int  # 현재 레벨 안에서 쌓은 양(진행바)
    exp_per_level: int
    pet: PetState
    quests: list[QuestState]
