"""밭 등록(온보딩) — 유효성 검증 → user_farm 생성 → 읍면동 토양 기준값으로 soil_state 초기화.

PRD.md §4.2. 지역은 시/군(region) + 읍면동(district) 두 단위를 함께 받는다 — 기상·적합도는
시/군 단위, 토양은 읍면동 단위이기 때문(§5).
"""

from datetime import date

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Crop, District, Region, SoilState, UserFarm
from app.services.district_soil_service import get_or_fetch, is_leaf_bjd


def list_regions(db: Session) -> list[Region]:
    """온보딩 자동완성용 전국 시/군. 256개라 페이징 없이 한 번에 준다."""
    return list(db.query(Region).order_by(Region.sido, Region.name))


def list_districts(db: Session, region_id: int) -> list[District]:
    """시/군에 속한 법정동 **말단**. 존재하지 않는 region이면 404(화이트리스트 검증, §17).

    리가 있는 읍·면(전국 1,411개)은 제외한다 — 그 코드로는 흙토람 검정 기록을 못 가져오므로
    고르게 하면 안 된다. 대신 그 면의 리들이 목록에 있다. 행 자체는 DB에 남아 있다 — 리 전환
    전에 면 코드로 등록된 밭이 FK를 걸고 있어서다. 설계: docs/design/ri-level-district.md

    name이 `"공음면 구암리"`라 name 정렬만으로 같은 면의 리가 붙어 나온다.
    """
    if db.query(Region.id).filter(Region.id == region_id).first() is None:
        raise AppError(404, "REGION_NOT_FOUND", "지역을 찾을 수 없습니다.")
    rows = db.query(District).filter(District.region_id == region_id).order_by(District.name)
    return [d for d in rows if is_leaf_bjd(d.bjd_code)]


def list_crops(db: Session) -> list[Crop]:
    return list(db.query(Crop).order_by(Crop.id))


def get_owned_farm(db: Session, user_id: int, farm_id: int) -> UserFarm:
    """요청 유저 소유 밭만 돌려준다. 없으면 404 — 남의 밭 존재를 노출하지 않는다(§11)."""
    farm = (
        db.query(UserFarm).filter(UserFarm.user_id == user_id, UserFarm.id == farm_id).first()
    )
    if farm is None:
        raise AppError(404, "FARM_NOT_FOUND", "밭을 찾을 수 없습니다.")
    return farm


def list_farms(db: Session, user_id: int) -> list[UserFarm]:
    """설정 화면용 밭 목록. 대시보드와 달리 적합도 계산을 하지 않는다(등록 정보만)."""
    return list(db.query(UserFarm).filter(UserFarm.user_id == user_id).order_by(UserFarm.id))


def _validate_location_and_crop(db: Session, region_id: int, bjd_code: str, crop_id: int) -> Crop:
    """마스터 화이트리스트 검증 — 임의 region/crop/읍면동을 받지 않는다(§17).

    읍면동이 선택한 시/군 소속인지도 확인해 앞뒤가 안 맞는 조합을 막는다.
    """
    crop = db.query(Crop).filter(Crop.id == crop_id).first()
    if crop is None:
        raise AppError(404, "CROP_NOT_FOUND", "작물을 찾을 수 없습니다.")
    if db.query(Region.id).filter(Region.id == region_id).first() is None:
        raise AppError(404, "REGION_NOT_FOUND", "지역을 찾을 수 없습니다.")

    # 여기서 말단(is_leaf_bjd)까지 요구하면 안 된다 — 리 단위 전환 전에 면 코드로 등록된 밭은
    # 라벨만 고쳐도 이 검증을 다시 타므로, 자기 주소를 못 고치게 된다. 말단 제한은 선택지를
    # 좁히는 쪽(list_districts)에서만 한다.
    district = db.query(District).filter(District.bjd_code == bjd_code).first()
    if district is None:
        raise AppError(404, "DISTRICT_NOT_FOUND", "읍면동을 찾을 수 없습니다.")
    if district.region_id != region_id:
        raise AppError(400, "DISTRICT_REGION_MISMATCH", "선택한 시/군에 속한 읍면동이 아닙니다.")
    return crop


def _init_soil_state(db: Session, farm_id: int, bjd_code: str, crop: Crop) -> None:
    """(읍면동, 작물 경지구분) 기준값을 이 밭의 토양 상태로 복사한다(§3.9).

    exam_field_type이 없는 작물이면 건너뛴다 — 임의 경지구분을 고르지 않는다.
    """
    if crop.exam_field_type is None:
        return
    soil = get_or_fetch(db, bjd_code, crop.exam_field_type)
    db.add(
        SoilState(
            user_farm_id=farm_id,
            ph=soil.ph,
            ec=soil.ec,
            p2o5=soil.p2o5,
            organic_matter=soil.organic_matter,
            base_source=soil.source,  # 조회 단위·표본수 포함 — 재현성(§12)
            # 법정동 말단(리 또는 동) 표본 평균이라 실측이지만 이 밭의 실측은 아니다.
            # 행위 반영 전이므로 is_estimated=false로 두어 "기준값" 단계임을 표시한다(§3.9).
            is_estimated=False,
        )
    )


def _field_type(db: Session, crop_id: int) -> str | None:
    """작물의 흙토람 경지구분. 토양 기준값 캐시 키의 절반이다."""
    return db.query(Crop.exam_field_type).filter(Crop.id == crop_id).scalar()


def create_farm(
    db: Session,
    user_id: int,
    region_id: int,
    bjd_code: str,
    crop_id: int,
    planting_date: date,
    label: str | None,
) -> UserFarm:
    """밭 생성 + 토양 기준값 초기화. 한 트랜잭션으로 처리한다(§10 트랜잭션 경계는 서비스)."""
    crop = _validate_location_and_crop(db, region_id, bjd_code, crop_id)

    farm = UserFarm(
        user_id=user_id,
        region_id=region_id,
        bjd_code=bjd_code,
        crop_id=crop_id,
        planting_date=planting_date,
        label=label,
    )
    db.add(farm)
    db.flush()  # farm.id 확보
    _init_soil_state(db, farm.id, bjd_code, crop)

    db.commit()
    db.refresh(farm)
    return farm


# 설정 화면에서 고칠 수 있는 필드. 그 외 키가 오면 무시가 아니라 거절한다(오타를 조용히 삼키지 않기).
EDITABLE_FIELDS = frozenset({"region_id", "bjd_code", "crop_id", "planting_date", "label"})


def update_farm(db: Session, user_id: int, farm_id: int, changes: dict[str, object]) -> UserFarm:
    """밭 정보 수정. `changes`는 보낸 필드만 담긴다(PATCH, exclude_unset).

    위치(읍면동)나 작물이 바뀌면 토양 기준값의 출처 자체가 바뀌므로 `soil_state`를 다시 만든다.
    반면 `soil_state_snapshot`(실측 이력)·`farm_action_log`(유저 행위 기록)는 지우지 않는다 —
    유저가 실제로 한 일/측정한 값이라 위치 변경으로 없앨 사실이 아니다. 대신 그 이력이 이전
    위치 기준이라는 점은 남는다(P1 재검정에서 다뤄야 할 [확인 필요] 항목).
    """
    unknown = set(changes) - EDITABLE_FIELDS
    if unknown:
        raise AppError(400, "FIELD_NOT_EDITABLE", f"수정할 수 없는 항목: {', '.join(sorted(unknown))}")

    farm = get_owned_farm(db, user_id, farm_id)

    region_id = changes.get("region_id", farm.region_id)
    bjd_code = changes.get("bjd_code", farm.bjd_code)
    crop_id = changes.get("crop_id", farm.crop_id)
    # 시/군을 바꾸면 읍면동도 함께 와야 한다 — 옛 읍면동은 새 시/군에 속하지 않으므로
    # 검증에서 걸리거나(운 나쁘면) 엉뚱한 토양을 쓰게 된다.
    # 0014 이전 등록 밭은 bjd_code가 NULL이라 지역만 수정하려 해도 읍면동을 함께 골라야 한다.
    if bjd_code is None:
        raise AppError(400, "BJD_CODE_REQUIRED", "읍/면/동을 선택해야 합니다.")
    # 타입은 pydantic(FarmUpdate)에서 이미 검증됐다. dict[str, object]라 mypy에만 알려주는 좁히기.
    assert isinstance(region_id, int) and isinstance(crop_id, int) and isinstance(bjd_code, str)

    crop = _validate_location_and_crop(db, region_id, bjd_code, crop_id)

    # 토양 기준값은 (읍면동, 작물 경지구분)에서 나온다 — 둘 중 하나라도 바뀌면 다시 조회한다.
    soil_basis_changed = bjd_code != farm.bjd_code or crop.exam_field_type != _field_type(
        db, farm.crop_id
    )

    for field, value in changes.items():
        setattr(farm, field, value)
    farm.bjd_code = bjd_code

    if soil_basis_changed:
        db.query(SoilState).filter(SoilState.user_farm_id == farm.id).delete()
        db.flush()  # unique(user_farm_id) 충돌 방지 — 새 행 넣기 전에 삭제를 반영
        _init_soil_state(db, farm.id, bjd_code, crop)

    db.commit()
    db.refresh(farm)
    return farm


def delete_farm(db: Session, user_id: int, farm_id: int) -> None:
    """밭 삭제. 딸린 토양 상태·기록·추천은 FK ON DELETE CASCADE로 함께 지워진다(DB.md §3.7~3.11)."""
    farm = get_owned_farm(db, user_id, farm_id)
    db.delete(farm)
    db.commit()
