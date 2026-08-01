"""토양 지표가 비거나 낡은 밭을 흙토람 재조회로 복구한다.

두 가지를 고친다.

**① 완전 결측(원래 목적)** — 리 코드 버그(읍·면은 리 코드로만 조회된다)로 농촌 밭의
`soil_state`가 전부 NULL로 박혀 있었고, 실패 결과가 `district_soil`에 캐시돼 재시도도 안 됐다.
코드는 고쳤지만 이미 등록된 밭은 등록 시점에 복사된 NULL을 그대로 들고 있다.

**② 치환성 양이온 결측(2026-08-01 추가)** — `0024`로 `k`·`ca`·`mg` 지표가 생겼다. 흙토람은
그 값을 원래부터 주고 있었지만(`POSIFERT_K/CA/MG`) 저장할 컬럼이 없어 버렸다. 그래서:

- 기존 `soil_state` 행은 양이온이 NULL이다 → 사과·배·상추가 그 세 지표를 채점하지 못한다.
- **`district_soil` 캐시 행도 NULL이다.** 이쪽이 더 중요하다 — `get_or_fetch`는
  `sample_count > 0`이면 캐시를 그대로 주므로, **이미 캐시된 읍면동에 새로 등록하는 밭도**
  양이온이 빈 채로 시작한다. 그래서 밭만 훑으면 안 되고 캐시를 먼저 갱신해야 한다.

일회성 복구 스크립트다 — 상시 경로가 아니다. 재실행해도 안전하다(이미 값이 있으면 건너뛴다).
양이온 표본이 실제로 없는 읍면동은 재조회해도 NULL로 남는다 — 그건 결함이 아니라 사실이고,
출력에서 구분해 알려준다(그런 곳은 다시 돌려도 또 조회하니 반복 실행은 피할 것).

    cd backend && python ../scripts/repair_empty_soil_state.py [--apply]

--apply 없이 돌리면 무엇이 바뀔지만 출력한다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.session import SessionLocal  # noqa: E402
from app.models import Crop, DistrictSoil, SoilState, UserFarm  # noqa: E402
from app.services.district_soil_service import get_or_fetch  # noqa: E402

# 기존 지표 — 이게 전부 비어 있으면 "완전 결측"(①)이다.
BASE_FIELDS = ("ph", "ec", "p2o5", "organic_matter")
# 0024로 추가된 치환성 양이온(cmol/kg). 이것만 비어 있는 경우가 ②다.
CATION_FIELDS = ("k", "ca", "mg")
ALL_FIELDS = BASE_FIELDS + CATION_FIELDS


def _all_missing(row: object, fields: tuple[str, ...]) -> bool:
    return all(getattr(row, f) is None for f in fields)


def _refresh_cache_without_cations(db, apply: bool) -> tuple[int, list[str]]:
    """양이온이 없는 `district_soil` 캐시를 강제 재조회한다. (갱신 시도 수, 여전히 없는 코드).

    표본이 0건인 행은 건너뛴다 — 그건 ①의 문제이고 `get_or_fetch`가 평소 경로에서 이미
    매번 재시도한다. 여기서 노리는 것은 "표본은 있는데 양이온만 없는" 행이다.
    """
    rows = (
        db.query(DistrictSoil)
        .filter(DistrictSoil.sample_count > 0)
        .order_by(DistrictSoil.bjd_code)
        .all()
    )
    targets = [r for r in rows if _all_missing(r, CATION_FIELDS)]
    if not targets:
        print("district_soil 캐시: 양이온 결측 행 없음")
        return 0, []

    print(f"district_soil 캐시 {len(targets)}건 재조회 (양이온 결측)")
    still_empty: list[str] = []
    for row in targets:
        # refresh=True — 캐시가 있어도 다시 부른다. 같은 fetch에서 온 값으로 행 전체가
        # 갱신되므로 지표 간 출처가 섞이지 않는다(양이온만 새 표본에서 오는 상황 방지).
        fresh = get_or_fetch(db, row.bjd_code, row.field_type, refresh=True)
        cations = {f: getattr(fresh, f) for f in CATION_FIELDS}
        if all(v is None for v in cations.values()):
            still_empty.append(f"{row.bjd_code}/{row.field_type}")
            print(f"  {row.bjd_code} 경지{row.field_type}: 양이온 표본 없음 (표본 {fresh.sample_count}건)")
        else:
            print(
                f"  {row.bjd_code} 경지{row.field_type}: "
                f"k={cations['k']} ca={cations['ca']} mg={cations['mg']} "
                f"(표본 {fresh.sample_count}건)"
            )
    if not apply:
        # 재조회 자체는 이미 세션에 반영됐다 — 아래 main이 rollback한다.
        pass
    return len(targets), still_empty


def main(apply: bool) -> int:
    db = SessionLocal()
    try:
        refreshed, still_empty = _refresh_cache_without_cations(db, apply)
        print()

        farms = (
            db.query(UserFarm, SoilState, Crop)
            .join(SoilState, SoilState.user_farm_id == UserFarm.id)
            .join(Crop, Crop.id == UserFarm.crop_id)
            .order_by(UserFarm.id)
            .all()
        )

        repaired = 0
        for farm, soil, crop in farms:
            needs_base = _all_missing(soil, BASE_FIELDS)
            needs_cations = _all_missing(soil, CATION_FIELDS)
            if not (needs_base or needs_cations):
                continue
            if farm.bjd_code is None or crop.exam_field_type is None:
                print(
                    f"farm {farm.id}: 건너뜀 "
                    f"(bjd_code={farm.bjd_code}, 경지구분={crop.exam_field_type})"
                )
                continue

            district = get_or_fetch(db, farm.bjd_code, crop.exam_field_type)
            if district.sample_count == 0:
                print(f"farm {farm.id} ({farm.bjd_code}, {crop.name}): 여전히 표본 0건 — {district.source}")
                continue

            reason = "완전 결측" if needs_base else "양이온 결측"
            print(
                f"farm {farm.id} ({farm.bjd_code}, {crop.name}, {reason}): "
                f"ph={district.ph} ec={district.ec} p2o5={district.p2o5} "
                f"om={district.organic_matter} k={district.k} ca={district.ca} mg={district.mg} "
                f"[{district.source}]"
            )
            if apply:
                for field in ALL_FIELDS:
                    setattr(soil, field, getattr(district, field))
                soil.base_source = district.source
            repaired += 1

        # 어느 밭도 안 쓰는 0건 캐시도 알린다 — 남겨두면 다음 등록이 또 그 행을 집는다.
        stale = db.query(DistrictSoil).filter(DistrictSoil.sample_count == 0).all()
        if stale:
            print(f"\n표본 0건 캐시 {len(stale)}건: {[s.bjd_code for s in stale]}")
        if still_empty:
            print(f"\n양이온 표본이 실제로 없는 캐시 {len(still_empty)}건: {still_empty}")
            print("  → 결함이 아니다. 그 읍면동 검정 기록에 양이온 항목이 없다는 뜻이다.")

        if apply:
            db.commit()
            print(f"\n적용 완료 — 캐시 {refreshed}건 재조회, 밭 {repaired}개 복구.")
        else:
            db.rollback()
            print(
                f"\n(미적용) 캐시 재조회 대상 {refreshed}건, 복구 대상 밭 {repaired}개. "
                "--apply 를 붙여 실행하세요."
            )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main("--apply" in sys.argv))
