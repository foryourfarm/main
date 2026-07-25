from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import SoilState, User
from app.schemas.common import ApiResponse
from app.schemas.farm import CropOut, DistrictOut, FarmCreate, FarmOut, RegionOut
from app.schemas.suitability import FarmMonthlyOutlook, FarmSuitability
from app.services import farm_service, suitability_service

router = APIRouter(prefix="/api/v1", tags=["farms"])


@router.get("/regions")
def get_regions(db: Session = Depends(get_db)) -> ApiResponse[list[RegionOut]]:
    """온보딩 시/군 선택지(마스터). 인증 불필요 — 공개 마스터 데이터다."""
    regions = farm_service.list_regions(db)
    return ApiResponse.ok([RegionOut(id=r.id, name=r.name, sido=r.sido) for r in regions])


@router.get("/regions/{region_id}/districts")
def get_districts(region_id: int, db: Session = Depends(get_db)) -> ApiResponse[list[DistrictOut]]:
    """선택한 시/군의 읍면동. 토양 기준값 조회 단위(PRD.md §5)."""
    districts = farm_service.list_districts(db, region_id)
    return ApiResponse.ok([DistrictOut(bjd_code=d.bjd_code, name=d.name) for d in districts])


@router.get("/crops")
def get_crops(db: Session = Depends(get_db)) -> ApiResponse[list[CropOut]]:
    crops = farm_service.list_crops(db)
    return ApiResponse.ok([CropOut(id=c.id, name=c.name) for c in crops])


@router.post("/farms", status_code=201)
def create_farm(
    body: FarmCreate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[FarmOut]:
    """밭 등록. 생성과 토양 기준값 초기화를 한 트랜잭션으로(§10)."""
    farm = farm_service.create_farm(
        db,
        current.id,
        body.region_id,
        body.bjd_code,
        body.crop_id,
        body.planting_date,
        body.label,
    )
    soil = db.query(SoilState).filter(SoilState.user_farm_id == farm.id).first()
    return ApiResponse.ok(
        FarmOut(
            id=farm.id,
            region_id=farm.region_id,
            crop_id=farm.crop_id,
            planting_date=farm.planting_date,
            label=farm.label,
            soil_source=soil.base_source if soil else None,
        )
    )


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
