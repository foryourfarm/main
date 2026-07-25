"""밭 등록(온보딩) — 유효성 검증 → user_farm 생성 → 읍면동 토양 기준값으로 soil_state 초기화.

PRD.md §4.2. 지역은 시/군(region) + 읍면동(district) 두 단위를 함께 받는다 — 기상·적합도는
시/군 단위, 토양은 읍면동 단위이기 때문(§5).
"""

from datetime import date

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Crop, District, Region, SoilState, UserFarm
from app.services.district_soil_service import get_or_fetch


def list_regions(db: Session) -> list[Region]:
    """온보딩 자동완성용 전국 시/군. 256개라 페이징 없이 한 번에 준다."""
    return list(db.query(Region).order_by(Region.sido, Region.name))


def list_districts(db: Session, region_id: int) -> list[District]:
    """시/군에 속한 읍면동. 존재하지 않는 region이면 404(화이트리스트 검증, §17)."""
    if db.query(Region.id).filter(Region.id == region_id).first() is None:
        raise AppError(404, "REGION_NOT_FOUND", "지역을 찾을 수 없습니다.")
    return list(db.query(District).filter(District.region_id == region_id).order_by(District.name))


def list_crops(db: Session) -> list[Crop]:
    return list(db.query(Crop).order_by(Crop.id))


def create_farm(
    db: Session,
    user_id: int,
    region_id: int,
    bjd_code: str,
    crop_id: int,
    planting_date: date,
    label: str | None,
) -> UserFarm:
    """밭 생성 + 토양 기준값 초기화. 한 트랜잭션으로 처리한다(§10 트랜잭션 경계는 서비스).

    입력은 마스터 화이트리스트로 검증한다 — 임의 region/crop/읍면동을 받지 않는다(§17).
    읍면동이 선택한 시/군 소속인지도 확인해 앞뒤가 안 맞는 조합을 막는다.
    """
    crop = db.query(Crop).filter(Crop.id == crop_id).first()
    if crop is None:
        raise AppError(404, "CROP_NOT_FOUND", "작물을 찾을 수 없습니다.")
    if db.query(Region.id).filter(Region.id == region_id).first() is None:
        raise AppError(404, "REGION_NOT_FOUND", "지역을 찾을 수 없습니다.")

    district = db.query(District).filter(District.bjd_code == bjd_code).first()
    if district is None:
        raise AppError(404, "DISTRICT_NOT_FOUND", "읍면동을 찾을 수 없습니다.")
    if district.region_id != region_id:
        raise AppError(400, "DISTRICT_REGION_MISMATCH", "선택한 시/군에 속한 읍면동이 아닙니다.")

    farm = UserFarm(
        user_id=user_id,
        region_id=region_id,
        crop_id=crop_id,
        planting_date=planting_date,
        label=label,
    )
    db.add(farm)
    db.flush()  # farm.id 확보

    # 작물 재배 형태에 맞는 경지구분 표본만 평균해 기준값으로 삼는다(§3.9).
    # exam_field_type이 없는 작물이면 토양 초기화를 건너뛴다 — 임의 경지구분을 고르지 않는다.
    if crop.exam_field_type is not None:
        soil = get_or_fetch(db, bjd_code, crop.exam_field_type)
        db.add(
            SoilState(
                user_farm_id=farm.id,
                ph=soil.ph,
                ec=soil.ec,
                p2o5=soil.p2o5,
                organic_matter=soil.organic_matter,
                base_source=soil.source,  # 조회 단위·표본수 포함 — 재현성(§12)
                # 읍면동 표본 평균이라 실측이지만 이 밭의 실측은 아니다. 행위 반영 전이므로
                # is_estimated=false로 두어 "기준값" 단계임을 표시한다(§3.9).
                is_estimated=False,
            )
        )

    db.commit()
    db.refresh(farm)
    return farm
