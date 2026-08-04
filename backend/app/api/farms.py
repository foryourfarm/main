from datetime import date, datetime

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.infra.llm_client import make_llm_client
from app.infra.public_api.forecast_client import KST
from app.models import Crop, District, Region, SoilState, User, UserFarm
from app.schemas.common import ApiResponse
from app.schemas.farm import CropOut, DistrictOut, FarmCreate, FarmOut, FarmUpdate, RegionOut
from app.schemas.short_term import DailyAdvice, FarmShortTerm
from app.schemas.suitability import FarmMonthlyOutlook, FarmSuitability
from app.services import advice_service, farm_service, short_term_service, suitability_service
from app.services.dashboard_service import stage_label
from app.services.district_soil_service import effective_source

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


def _farm_out(db: Session, farm: UserFarm) -> FarmOut:
    """밭 1건을 화면 표시용으로. 이름은 설정 화면이 "지금 값"을 보여줄 수 있게 함께 준다."""
    soil = db.query(SoilState).filter(SoilState.user_farm_id == farm.id).first()
    district_name = (
        db.query(District.name).filter(District.bjd_code == farm.bjd_code).scalar()
        if farm.bjd_code is not None
        else None
    )
    return FarmOut(
        id=farm.id,
        region_id=farm.region_id,
        region_name=db.query(Region.name).filter(Region.id == farm.region_id).scalar(),
        bjd_code=farm.bjd_code,
        district_name=district_name,
        crop_id=farm.crop_id,
        crop_name=db.query(Crop.name).filter(Crop.id == farm.crop_id).scalar(),
        planting_date=farm.planting_date,
        label=farm.label,
        # 저장된 문구를 그대로 주지 않는다 — 리 전환 전 등록 밭은 안내가 반대로 나간다.
        soil_source=(
            effective_source(
                farm.bjd_code,
                soil.base_source,
                any(v is not None for v in (soil.ph, soil.ec, soil.p2o5, soil.organic_matter)),
            )
            if soil
            else None
        ),
    )


@router.get("/farms")
def get_farms(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[list[FarmOut]]:
    """설정 화면용 밭 목록(등록 정보만 — 적합도는 /dashboard)."""
    # ponytail: 밭당 이름 조회 반복(N+1). 밭 수가 한 자릿수라 방치, 커지면 join으로.
    return ApiResponse.ok([_farm_out(db, f) for f in farm_service.list_farms(db, current.id)])


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
    return ApiResponse.ok(_farm_out(db, farm))


@router.patch("/farms/{farm_id}")
def update_farm(
    farm_id: int,
    body: FarmUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[FarmOut]:
    """밭 정보 수정. 보낸 필드만 반영(PATCH). 위치·작물이 바뀌면 토양 기준값을 다시 조회한다."""
    farm = farm_service.update_farm(
        db, current.id, farm_id, body.model_dump(exclude_unset=True)
    )
    return ApiResponse.ok(_farm_out(db, farm))


@router.delete("/farms/{farm_id}")
def delete_farm(
    farm_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[str]:
    """밭 삭제. 딸린 토양 상태·기록도 함께 사라진다(CASCADE) — 되돌릴 수 없다."""
    farm_service.delete_farm(db, current.id, farm_id)
    return ApiResponse.ok("deleted")


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
    """장기 탭 월별 히트맵. 오늘이 속한 달부터 3개월(PRD §4.4) — 해를 넘길 수 있다."""
    data = suitability_service.compute_monthly_outlook(
        db, current.id, farm_id, date.today()
    )
    return ApiResponse.ok(FarmMonthlyOutlook(**data))


@router.get("/farms/{farm_id}/short-term")
def get_farm_short_term(
    farm_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[FarmShortTerm]:
    """단기 탭. 기상청 단기예보(최대 3일) + 날짜별 위험신호(PRD.md §4.5).

    행동추천은 여기 싣지 않는다 — `/advice`로 분리했다. 한 응답에 묶었더니 LLM 동기
    재시도가 탭 전체를 막아 화면이 "불러오는 중…"으로 12초간 비는 것을 실측했다.
    """
    now = datetime.now(KST)
    data = short_term_service.compute_short_term(
        db, current.id, farm_id, settings.weather_forecast_api, now.date(), now
    )
    return ApiResponse.ok(FarmShortTerm(**data))


@router.get("/farms/{farm_id}/advice")
def get_farm_advice(
    farm_id: int,
    background: BackgroundTasks,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[DailyAdvice]:
    """오늘의 행동추천(PRD §10-1). 단기 탭과 **별도 요청**이라 탭 렌더를 막지 않는다.

    예보는 캐시 히트라 여기서 다시 계산해도 비용이 거의 없다(실측 0.02초). 대신 위험
    판정 로직이 한 곳(`compute_short_term`)에 머물러 두 경로가 어긋나지 않는다.
    """
    now = datetime.now(KST)
    data = short_term_service.compute_short_term(
        db, current.id, farm_id, settings.weather_forecast_api, now.date(), now
    )
    days: list[dict[str, object]] = data["days"]  # type: ignore[assignment]
    crop = db.get(Crop, data["crop_id"])
    crop_name = crop.name if crop else ""
    label = stage_label(days[0]["growth_stage"], days[0]["status"]) if days else None

    text, is_llm, needs_polish = advice_service.get_or_create(
        db,
        farm_id=farm_id,
        crop_name=crop_name,
        days=days,
        persistent=data["persistent_risks"],  # type: ignore[arg-type]
        stage_label=label,
        today=now.date(),
        # 동기 재시도는 짧은 타임아웃으로 — 유저가 기다리는 경로다(config 주석).
        llm=make_llm_client(timeout_s=settings.advice_llm_timeout_s),
    )
    if needs_polish:
        # 응답을 보낸 뒤 다듬는다. Cloud Run 스로틀링으로 완주 못 하면 다음 조회가 메운다.
        background.add_task(
            advice_service.polish_in_background,
            farm_id,
            crop_name,
            now.date(),
            text,
            make_llm_client(),
        )
    return ApiResponse.ok(
        DailyAdvice(
            text=text,
            is_llm=is_llm,
            soil_text=advice_service.soil_advice(db, farm_id, days, crop_name),
        )
    )
