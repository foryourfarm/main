from datetime import date

from pydantic import BaseModel, Field


class RegionOut(BaseModel):
    """온보딩 시/군 선택지."""

    id: int
    name: str
    sido: str


class DistrictOut(BaseModel):
    """온보딩 읍면동 선택지. bjd_code가 흙토람 토양 조회 키다(PRD.md §5)."""

    bjd_code: str
    name: str


class CropOut(BaseModel):
    id: int
    name: str


class FarmCreate(BaseModel):
    """밭 등록 입력. region(시/군)과 bjd_code(읍면동)를 함께 받는다 — 기상은 시/군, 토양은 읍면동."""

    region_id: int
    bjd_code: str = Field(min_length=10, max_length=10)
    crop_id: int
    planting_date: date
    label: str | None = Field(default=None, max_length=50)


class FarmUpdate(BaseModel):
    """밭 정보 수정(설정 화면). 보낸 필드만 바꾼다 — 라우터에서 `exclude_unset`으로 추출한다.

    시/군을 바꿀 때는 `bjd_code`도 함께 보내야 한다(토양은 읍면동 단위 — PRD.md §5).
    `label`은 명시적 null로 지울 수 있다(안 보내면 유지).
    """

    region_id: int | None = None
    bjd_code: str | None = Field(default=None, min_length=10, max_length=10)
    crop_id: int | None = None
    planting_date: date | None = None
    label: str | None = Field(default=None, max_length=50)


class FarmOut(BaseModel):
    id: int
    region_id: int
    region_name: str | None
    bjd_code: str | None
    """읍면동. 0014 이전 등록 밭은 null일 수 있다 — 설정에서 다시 고르면 채워진다."""
    district_name: str | None
    crop_id: int
    crop_name: str | None
    planting_date: date
    label: str | None
    soil_source: str | None
    """토양 기준값 출처(조회 단위·표본수 포함). None이면 토양 초기화를 건너뜀."""
