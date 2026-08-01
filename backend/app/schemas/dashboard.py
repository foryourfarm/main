from datetime import date
from typing import Literal

from pydantic import BaseModel


class DashboardCard(BaseModel):
    """대시보드 작물 카드 1장. 당일 적합도 요약 + 헤더(작물·지역·단계) + 타입 배지.

    점수·등급은 **오늘 예보 기준**이다(단기 탭 days 중 오늘). 평년치 기반 시즌 적합도는
    장기 탭에 있다 — 같은 자리에 섞으면 유저가 무엇을 보는지 알 수 없다(§18-4).
    예보를 못 구하면 status=insufficient_data + limitations에 사유가 실린다.
    """

    farm_id: int
    crop_id: int
    crop_name: str | None
    region_name: str | None
    crop_type: Literal["orchard", "field"]  # 🌳 과수 / 🌾 밭
    growth_stage: str | None
    growth_stage_label: str | None
    score: float | None
    grade: str | None  # S | A | B | C | null
    status: Literal["ok", "dormant", "out_of_season", "insufficient_data"]
    label: str  # 항상 "문헌 기반 예상 적합도"
    limitations: list[str]


class DashboardResponse(BaseModel):
    as_of: date
    farms: list[DashboardCard]
