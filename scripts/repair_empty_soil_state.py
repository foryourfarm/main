"""토양 지표가 비어 있는 밭을 흙토람 재조회로 복구한다.

리 코드 버그(읍·면은 리 코드로만 조회된다)로 농촌 밭의 `soil_state`가 전부 NULL로
박혀 있었고, 실패 결과가 `district_soil`에 캐시돼 재시도도 안 됐다. 코드는 고쳤지만
이미 등록된 밭은 등록 시점에 복사된 NULL을 그대로 들고 있어 한 번 훑어줘야 한다.

일회성 복구 스크립트다 — 상시 경로가 아니다. 재실행해도 안전하다(이미 값이 있는
밭은 건너뛴다).

    cd backend && python ../scripts/repair_empty_soil_state.py [--apply]

--apply 없이 돌리면 무엇이 바뀔지만 출력한다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.session import SessionLocal  # noqa: E402
from app.models import Crop, DistrictSoil, SoilState, UserFarm  # noqa: E402
from app.services.district_soil_service import get_or_fetch  # noqa: E402

FIELDS = ("ph", "ec", "p2o5", "organic_matter")


def main(apply: bool) -> int:
    db = SessionLocal()
    farms = (
        db.query(UserFarm, SoilState, Crop)
        .join(SoilState, SoilState.user_farm_id == UserFarm.id)
        .join(Crop, Crop.id == UserFarm.crop_id)
        .order_by(UserFarm.id)
        .all()
    )

    repaired = 0
    for farm, soil, crop in farms:
        if any(getattr(soil, f) is not None for f in FIELDS):
            continue  # 이미 값이 있다
        if farm.bjd_code is None or crop.exam_field_type is None:
            print(f"farm {farm.id}: 건너뜀 (bjd_code={farm.bjd_code}, 경지구분={crop.exam_field_type})")
            continue

        district = get_or_fetch(db, farm.bjd_code, crop.exam_field_type)
        if district.sample_count == 0:
            print(f"farm {farm.id} ({farm.bjd_code}, {crop.name}): 여전히 표본 0건 — {district.source}")
            continue

        print(
            f"farm {farm.id} ({farm.bjd_code}, {crop.name}): "
            f"ph={district.ph} ec={district.ec} p2o5={district.p2o5} om={district.organic_matter} "
            f"[{district.source}]"
        )
        if apply:
            soil.ph = district.ph
            soil.ec = district.ec
            soil.p2o5 = district.p2o5
            soil.organic_matter = district.organic_matter
            soil.base_source = district.source
        repaired += 1

    # 어느 밭도 안 쓰는 0건 캐시도 치운다 — 남겨두면 다음 등록이 또 그 행을 집는다.
    stale = db.query(DistrictSoil).filter(DistrictSoil.sample_count == 0).all()
    if stale:
        print(f"\n표본 0건 캐시 {len(stale)}건: {[s.bjd_code for s in stale]}")

    if apply:
        db.commit()
        print(f"\n적용 완료 — 밭 {repaired}개 복구.")
    else:
        db.rollback()
        print(f"\n(미적용) 복구 대상 밭 {repaired}개. --apply 를 붙여 실행하세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--apply" in sys.argv))
