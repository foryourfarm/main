from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
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
    data = dashboard_service.build_dashboard(db, current.id, date.today())
    return ApiResponse.ok(data)
