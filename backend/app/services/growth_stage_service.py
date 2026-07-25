"""planting_date/달력 → 생육단계 resolver. 단계 범위는 crop_growth_stage 시드가 근거(§18-2).

결정론: 같은 (작물, 파종일, 기준일)이면 항상 같은 단계. 어느 범위에도 안 들거나 단계 시드가
없는 작물(오이·상추)은 None → 호출자는 전기간 공통(growth_stage=NULL) 지침으로 폴백한다.
"""
from datetime import date

from sqlalchemy.orm import Session

from app.models import CropGrowthStage

MODE_DAY_OF_YEAR = "day_of_year"
MODE_DAYS_AFTER_PLANTING = "days_after_planting"


def pick_stage(
    rows: list[CropGrowthStage], day_of_year: int, days_after_planting: int
) -> str | None:
    """시드 행들에서 현재 값이 드는 단계를 고른다. 겹치면 priority 큰(더 진행된) 단계 우선.

    순수 함수(DB 무관) — 경계·겹침·범위밖을 테스트로 검증한다.
    """
    best: CropGrowthStage | None = None
    for r in rows:
        value = day_of_year if r.mode == MODE_DAY_OF_YEAR else days_after_planting
        if r.range_start <= value <= r.range_end:
            if best is None or r.priority > best.priority:
                best = r
    return best.growth_stage if best else None


def resolve_growth_stage(
    db: Session, crop_id: int, planting_date: date, on_date: date
) -> str | None:
    """작물의 단계 시드를 읽어 on_date 기준 단계를 반환. 단계 시드 없으면 None."""
    rows = list(db.query(CropGrowthStage).filter(CropGrowthStage.crop_id == crop_id))
    if not rows:
        return None
    day_of_year = on_date.timetuple().tm_yday
    days_after_planting = (on_date - planting_date).days
    return pick_stage(rows, day_of_year, days_after_planting)
