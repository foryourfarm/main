from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.infra.public_api.forecast_client import KST
from app.models import User
from app.schemas.common import ApiResponse
from app.schemas.dashboard import DashboardResponse
from app.services import dashboard_service

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


@router.get("/dashboard")
def get_dashboard(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[DashboardResponse]:
    # 단기 탭과 같은 시각 기준이어야 카드와 상세가 어긋나지 않는다.
    now = datetime.now(KST)
    data = dashboard_service.build_dashboard(
        db, current.id, settings.weather_forecast_api, now.date(), now
    )
    return ApiResponse.ok(data)
