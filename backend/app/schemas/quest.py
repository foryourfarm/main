from pydantic import BaseModel, Field


class PetState(BaseModel):
    code: str
    name: str
    emoji: str  # 현재 레벨 단계의 외형(ponytail: 임시 — 일러스트 나오면 이미지 URL로 교체)
    stage_label: str


class PetOption(BaseModel):
    """고를 수 있는 펫. emoji는 **현재 레벨 기준** 외형이라 "지금 바꾸면 이렇게 보인다"가 된다."""

    code: str
    name: str
    emoji: str


class QuestState(BaseModel):
    code: str
    label: str
    exp: int
    is_done: bool


class QuestProgress(BaseModel):
    """펫·레벨·오늘 퀘스트 = 화면 하나를 채우는 상태 전부(PRD.md §14.5).
    조회/완료/펫교체 셋 다 이걸 돌려줘 FE가 응답을 통째로 갈아끼우면 되게 한다."""

    level: int
    exp: int
    exp_into_level: int  # 현재 레벨 안에서 쌓은 양(진행바)
    exp_per_level: int
    pet: PetState
    pets: list[PetOption]
    quests: list[QuestState]


class PetChangeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=32)  # 실제 유효성은 서비스가 화이트리스트로 검증
