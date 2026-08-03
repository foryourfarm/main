"""토양 지표가 비거나 낡은 밭을 흙토람 재조회로 복구한다.

세 가지를 고친다.

**① 완전 결측(원래 목적)** — 리 코드 버그(읍·면은 리 코드로만 조회된다)로 농촌 밭의
`soil_state`가 전부 NULL로 박혀 있었고, 실패 결과가 `district_soil`에 캐시돼 재시도도 안 됐다.
코드는 고쳤지만 이미 등록된 밭은 등록 시점에 복사된 NULL을 그대로 들고 있다.

**② 치환성 양이온 결측(2026-08-01 추가)** — `0024`로 `k`·`ca`·`mg` 지표가 생겼다. 흙토람은
그 값을 원래부터 주고 있었지만(`POSIFERT_K/CA/MG`) 저장할 컬럼이 없어 버렸다. 그래서:

- 기존 `soil_state` 행은 양이온이 NULL이다 → 사과·배·상추가 그 세 지표를 채점하지 못한다.
- **`district_soil` 캐시 행도 NULL이다.** 이쪽이 더 중요하다 — `get_or_fetch`는
  `sample_count > 0`이면 캐시를 그대로 주므로, **이미 캐시된 읍면동에 새로 등록하는 밭도**
  양이온이 빈 채로 시작한다. 그래서 밭만 훑으면 안 되고 캐시를 먼저 갱신해야 한다.

**③ 표본 절단(2026-08-03 추가)** — `_fetch_exams`가 1페이지(100건)만 읽어 지역 기준값이
"첫 100건 평균"이었다. 코드는 고쳤지만(`_fetch_all_pages`) **이미 캐시된 행과 그것을 복사한
`soil_state`는 절단된 값을 그대로 들고 있다.** 실측 크기: 부여 장암면 석동리 과수가 표본
3 → 8건, 유효인산 80.13 → 317.30(결핍 판정이 적정~과다로 뒤집힌다).

**③은 값싼 탐지 신호가 없어서 전량 재조회한다.** `sample_count == 100`인 행만 고르면 될 것
같지만 틀렸다 — `summarize`의 `sample_count`는 **경지구분 필터 후** 개수(`len(matched)`)이고
절단은 필터 **전** 100건 상한에서 일어난다. 실측: 고창읍 5279025035는 리 전체가 162건인데
밭 표본은 16건으로 저장돼 있었다(논이 74→135로 늘었고 밭은 안 늘었다). 즉 `sample_count`가
어떤 값이든 절단됐을 수 있다. 대상 행은 "밭이 등록된 (법정동 × 경지구분)"뿐이라 수십 건
수준이고, 일회성 스크립트라 전량 재조회 비용이 문제되지 않는다(§18-1은 상시 경로 얘기다).

일회성 복구 스크립트다 — 상시 경로가 아니다. 재실행해도 안전하다.
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


def _differs(a: object, b: object) -> bool:
    """두 지표값이 실질적으로 다른가. Decimal 표기 차이(6.6 vs 6.60)를 같게 본다.

    `summarize`는 소수 2자리로 반올림하지만 DB Numeric은 저장된 표기를 그대로 돌려주므로
    직접 `!=` 비교하면 값이 같은데 다르다고 나올 수 있다 — 그러면 "복구했다"는 보고가
    부풀어 실제 변화를 못 알아본다.
    """
    if a is None or b is None:
        return (a is None) != (b is None)
    return round(float(a), 2) != round(float(b), 2)


def _fmt(v: object) -> str:
    # 결측 표시에 em dash(—)를 쓰면 안 된다 — Windows 한국어 콘솔(cp949)이 인코딩하지 못해
    # 스크립트가 UnicodeEncodeError로 죽는다(실측). ASCII만 쓴다.
    return "null" if v is None else f"{float(v):g}"


def _refresh_all_cache(db) -> tuple[int, list[str]]:
    """표본이 있는 `district_soil` 캐시를 **전량** 강제 재조회한다. (갱신 수, 양이온 없는 코드).

    표본이 0건인 행은 건너뛴다 — 그건 ①의 문제이고 `get_or_fetch`가 평소 경로에서 이미
    매번 재시도한다.

    **종전엔 "양이온이 전부 빈 행"만 골랐다.** ③(표본 절단)이 추가되면서 그 필터로는 부족해졌다
    — 절단된 행은 양이온이 있을 수도 있고, `sample_count`로도 판별할 수 없다(모듈 docstring ③).
    그래서 전량으로 넓혔다. 절단 여부를 알 수 없으니 "다 다시 물어보고 바뀐 것만 보고한다"가
    유일하게 정확한 방법이다.
    """
    rows = (
        db.query(DistrictSoil)
        .filter(DistrictSoil.sample_count > 0)
        .order_by(DistrictSoil.bjd_code)
        .all()
    )
    if not rows:
        print("district_soil 캐시: 표본 있는 행 없음")
        return 0, []

    print(f"district_soil 캐시 {len(rows)}건 전량 재조회")
    still_empty: list[str] = []
    for row in rows:
        # 재조회 전 값을 붙잡아 둔다 — refresh가 같은 객체를 제자리 갱신하므로 미리 떠야 한다.
        before = {f: getattr(row, f) for f in ALL_FIELDS}
        before_n = row.sample_count
        # refresh=True — 캐시가 있어도 다시 부른다. 같은 fetch에서 온 값으로 행 전체가
        # 갱신되므로 지표 간 출처가 섞이지 않는다(양이온만 새 표본에서 오는 상황 방지).
        fresh = get_or_fetch(db, row.bjd_code, row.field_type, refresh=True)

        changed = [f for f in ALL_FIELDS if _differs(before[f], getattr(fresh, f))]
        tag = f"{row.bjd_code} 경지{row.field_type}"
        if before_n != fresh.sample_count or changed:
            diffs = " ".join(
                f"{f} {_fmt(before[f])}→{_fmt(getattr(fresh, f))}" for f in changed
            )
            print(f"  {tag}: 표본 {before_n}→{fresh.sample_count}건  {diffs}")
        else:
            print(f"  {tag}: 변화 없음 (표본 {fresh.sample_count}건)")

        if _all_missing(fresh, CATION_FIELDS):
            still_empty.append(f"{row.bjd_code}/{row.field_type}")
    return len(rows), still_empty


def _selfcheck() -> None:
    """`_differs`가 유일한 비자명 로직이라 여기서 고정한다.

    왜 pytest가 아니라 인라인인가: 이 리포는 `scripts/`를 테스트하는 관례가 없다(테스트 0건).
    프레임워크를 새로 들이는 대신 스크립트와 같이 사는 assert를 둔다 — 매 실행 시 돌아가고
    로직이 깨지면 복구를 시작하기 전에 죽는다.
    """
    from decimal import Decimal

    assert not _differs(None, None)
    assert _differs(None, Decimal("1"))
    assert _differs(Decimal("1"), None)
    # 표기만 다른 같은 값 — 이걸 다르다고 보면 "복구했다"는 보고가 부풀어 실제 변화를 가린다.
    assert not _differs(Decimal("6.6"), Decimal("6.60"))
    assert not _differs(Decimal("6.601"), Decimal("6.604"))  # 둘 다 6.6으로 반올림
    assert _differs(Decimal("80.13"), Decimal("317.30"))  # 실제로 잡아야 하는 절단 사례
    assert _fmt(None) == "null" and _fmt(Decimal("6.60")) == "6.6"


def main(apply: bool) -> int:
    _selfcheck()
    db = SessionLocal()
    try:
        refreshed, still_empty = _refresh_all_cache(db)
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
            # **종전엔 "전부 결측"인 밭만 고쳤다.** ③(절단)은 값이 **있으면서 낡은** 경우라
            # 그 조건에 걸리지 않는다. 그래서 판정을 "기준값과 어긋나는가"로 바꿨다 —
            # ①②③을 한 조건으로 덮고 특수 케이스 분기도 사라진다.
            #
            # `is_estimated=True`를 "행위 영향이 반영된 상태"로 보고 건너뛰려 했는데 **틀렸다.**
            # 그 컬럼은 DB `server_default=true`(0001)이고 **앱 어디서도 True로 쓰지 않는다** —
            # `_init_soil_state`가 명시적으로 False를 넣는 것만 있다. 즉 True는 "기본값 그대로
            # 남은 낡은 행"이라 오히려 복구 대상이다(실측: farm 1·2가 base_source='흙토람'
            # 스텁인 채 True였다). 그래서 가드를 넣지 않는다.
            #
            # 토양변화 Δ가 실제로 적용되기 시작하면(지금은 shadow 전용, §2-b) `soil_state`가
            # 기준값과 정당하게 달라진다 — **그때는 이 스크립트가 유저의 누적 변화를 덮어쓴다.**
            # 그 시점에 "Δ가 적용됐는가"를 가리는 플래그를 새로 두고 여기서 건너뛰어야 한다.
            if farm.bjd_code is None or crop.exam_field_type is None:
                print(
                    f"farm {farm.id}: 건너뜀 "
                    f"(bjd_code={farm.bjd_code}, 경지구분={crop.exam_field_type})"
                )
                continue

            # 위 전량 재조회가 이미 갱신했으므로 여기선 캐시를 그대로 읽는다(추가 호출 없음).
            district = get_or_fetch(db, farm.bjd_code, crop.exam_field_type)
            if district.sample_count == 0:
                print(f"farm {farm.id} ({farm.bjd_code}, {crop.name}): 여전히 표본 0건 — {district.source}")
                continue

            stale = [f for f in ALL_FIELDS if _differs(getattr(soil, f), getattr(district, f))]
            if not stale and soil.base_source == district.source:
                continue

            if _all_missing(soil, BASE_FIELDS):
                reason = "완전 결측"
            elif _all_missing(soil, CATION_FIELDS):
                reason = "양이온 결측"
            else:
                reason = "기준값 낡음(표본 절단 등)"
            diffs = " ".join(
                f"{f} {_fmt(getattr(soil, f))}→{_fmt(getattr(district, f))}" for f in stale
            )
            print(
                f"farm {farm.id} ({farm.bjd_code}, {crop.name}, {reason}): {diffs or '값 동일, 출처만 갱신'}"
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
