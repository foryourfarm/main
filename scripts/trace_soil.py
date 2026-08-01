"""밭 하나의 토양 데이터가 어디서 어떻게 들어오는지 단계별로 출력한다.

읽기 전용 — 아무것도 쓰지 않는다. 각 hop에서 실제 값과 출처를 찍어
"어느 단계에서 값이 사라지는지"를 눈으로 확인하는 용도.

    cd backend && python ../scripts/trace_soil.py 11
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.session import SessionLocal  # noqa: E402
from app.infra.public_api.soil_exam_client import get_soil_exam_list  # noqa: E402
from app.models import Crop, District, DistrictSoil, SoilState, UserFarm  # noqa: E402
from app.services.district_soil_service import (  # noqa: E402
    PAGE_SIZE,
    RI_SAMPLE_LIMIT,
    legacy_bjd_code,
    ri_codes,
    summarize,
)


def rule(title: str) -> None:
    print(f"\n{'─' * 70}\n{title}\n{'─' * 70}")


def main(farm_id: int) -> int:
    db = SessionLocal()
    farm = db.get(UserFarm, farm_id)
    if farm is None:
        print(f"farm {farm_id} 없음")
        return 1
    crop = db.get(Crop, farm.crop_id)
    district = db.query(District).filter(District.bjd_code == farm.bjd_code).first()

    rule("1. 밭 등록 정보 (user_farm)")
    print(f"  farm_id       {farm.id}")
    print(f"  작물          {crop.name} (crop_id={crop.id})")
    print(f"  경지구분      {crop.exam_field_type}  ← crop.exam_field_type. 이 코드로 표본을 거른다")
    print(f"  읍면동        {farm.bjd_code} {district.name if district else '(district 없음)'}")
    print(f"  시/군         region_id={farm.region_id}")
    if farm.bjd_code is None:
        print("\n  ⚠ bjd_code가 없다 — 토양 조회 자체가 불가능한 밭이다(구버전 등록).")
        return 0

    rule("2. 흙토람에 어떤 코드로 묻는가 (district_soil_service._fetch_exams)")
    print(f"  ① 읍면동 코드 그대로   {farm.bjd_code}")
    old = legacy_bjd_code(farm.bjd_code)
    print(f"  ② 통합전 코드          {old or '(해당 없음)'}")
    ris = ri_codes(farm.bjd_code)
    print(f"  ③ 리 코드 {len(ris)}개 중 앞 {RI_SAMPLE_LIMIT}개  {ris[:RI_SAMPLE_LIMIT] or '(리 없는 동)'}")
    print("     ①②가 비면 ③으로 간다. 읍·면은 흙토람이 리 코드로만 갖고 있다.")

    rule("3. 실제 API 응답 (호출 발생 — 느릴 수 있음)")
    pooled = []
    for label, code in [("읍면동", farm.bjd_code), ("통합전", old)]:
        if code is None:
            continue
        try:
            exams = get_soil_exam_list(code, page_no=1, page_size=PAGE_SIZE)
            print(f"  {label:5} {code} → {len(exams)}건")
            if exams:
                pooled = exams
                break
        except Exception as e:  # noqa: BLE001 — 조사 스크립트, 모든 실패를 보여준다
            print(f"  {label:5} {code} → {e}")
    if not pooled:
        for ri in ris[:RI_SAMPLE_LIMIT]:
            try:
                exams = get_soil_exam_list(ri, page_no=1, page_size=PAGE_SIZE)
                addr = exams[0].address.rsplit(" ", 1)[0] if exams else ""
                print(f"  리    {ri} → {len(exams):3}건  {addr}")
                pooled.extend(exams)
            except Exception as e:  # noqa: BLE001
                print(f"  리    {ri} → {e}")
    print(f"\n  합계 {len(pooled)}건")
    if pooled:
        by_type: dict[str, int] = {}
        for e in pooled:
            by_type[e.field_type_code or "?"] = by_type.get(e.field_type_code or "?", 0) + 1
        print(f"  경지구분별 분포: {dict(sorted(by_type.items()))}  (1논 2밭 3시설 4과수 …)")
        sample = pooled[0]
        print(f"  표본 예: {sample.address} pH={sample.ph} EC={sample.ec} "
              f"유효인산={sample.avail_p} 유기물={sample.organic_matter}")

    rule(f"4. 경지구분 '{crop.exam_field_type}' 만 골라 평균 (summarize)")
    summary = summarize(pooled, crop.exam_field_type)
    print(f"  표본 {summary['sample_count']}건 → ph={summary['ph']} ec={summary['ec']} "
          f"p2o5={summary['p2o5']} organic_matter={summary['organic_matter']}")
    if summary["sample_count"] == 0 and pooled:
        print(f"  ⚠ 표본은 있는데 경지구분 {crop.exam_field_type}이 하나도 없다 → 전부 결측")

    rule("5. 현재 DB에 저장된 값")
    cached = (
        db.query(DistrictSoil)
        .filter(
            DistrictSoil.bjd_code == farm.bjd_code,
            DistrictSoil.field_type == crop.exam_field_type,
        )
        .first()
    )
    if cached is None:
        print("  district_soil: (캐시 없음)")
    else:
        print(f"  district_soil: ph={cached.ph} ec={cached.ec} p2o5={cached.p2o5} "
              f"om={cached.organic_matter} 표본={cached.sample_count}")
        print(f"                 source={cached.source}")
        print(f"                 fetched_at={cached.fetched_at}")
    soil = db.query(SoilState).filter(SoilState.user_farm_id == farm.id).first()
    if soil is None:
        print("  soil_state:    (없음)")
    else:
        print(f"  soil_state:    ph={soil.ph} ec={soil.ec} p2o5={soil.p2o5} "
              f"om={soil.organic_matter}")
        print(f"                 base_source={soil.base_source}")
    print("\n  soil_state는 밭 등록 시점에 district_soil을 복사한 것이다"
          "(farm_service._init_soil_state).")
    print("  등록 시점에 조회가 실패했으면 NULL이 복사돼 그대로 굳는다"
          " → scripts/repair_empty_soil_state.py")

    rule("6. 적합도에서 이 값이 어떻게 쓰이나")
    print("  gather_indicator_values(soil, …)  suitability_service.py")
    print(f"    ph    → {soil.ph if soil else None}")
    print(f"    ec    → {soil.ec if soil else None}")
    print(f"    p2o5  → {soil.p2o5 if soil else None}")
    print(f"    organic → {soil.organic_matter if soil else None}")
    print("  None인 지표는 채점에서 빠지고, 남은 지표만으로 가중평균한다.")
    print("  빠진 지표는 limitations의 '채점 커버리지' 문구로 노출된다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 11))
