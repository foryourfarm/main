from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.common import ApiResponse
from app.schemas.suitability import FarmMonthlyOutlook, FarmSuitability
from app.services import suitability_service

router = APIRouter(prefix="/api/v1", tags=["farms"])


@router.get("/farms/{farm_id}/suitability")
def get_farm_suitability(
    farm_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[FarmSuitability]:
    # 소유권 검증은 서비스 계층에서(user_id 스코프, §11). 없으면 404.
    data = suitability_service.compute_farm_suitability(db, current.id, farm_id, date.today())
    return ApiResponse.ok(FarmSuitability(**data))


@router.get("/farms/{farm_id}/monthly-outlook")
def get_farm_monthly_outlook(
    farm_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[FarmMonthlyOutlook]:
    """장기 탭 월별 히트맵. 올해 1~12월 — 연도 선택은 요구 생기면 쿼리파라미터로."""
    data = suitability_service.compute_monthly_outlook(
        db, current.id, farm_id, date.today().year
    )
    return ApiResponse.ok(FarmMonthlyOutlook(**data))
