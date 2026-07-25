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


class FarmOut(BaseModel):
    id: int
    region_id: int
    crop_id: int
    planting_date: date
    label: str | None
    soil_source: str | None
    """토양 기준값 출처(조회 단위·표본수 포함). None이면 토양 초기화를 건너뜀."""
