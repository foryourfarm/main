"""대시보드 집계 — 유저의 모든 밭을 작물 카드로. 당일 적합도 + 이름/단계/타입 조인.

점수는 **오늘 예보 기준**이다(단기). 평년치 기반 시즌 적합도는 장기 탭이 따로 보여준다 —
카드가 "현재"라고 적어놓고 평년 점수를 주면 오늘 날씨와 무관한 값이 된다(PRD.md §4.3).
"""
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models import Crop, Region, UserFarm
from app.schemas.dashboard import DashboardCard, DashboardResponse
from app.services.short_term_service import compute_short_term

# 생육단계 코드 → 화면 표시용 한국어 라벨(표현용, 농업 기준값 아님).
STAGE_LABELS = {
    "fruit_growth": "결실비대기",
    "coloring": "착색기",
    "maturity": "성숙기",
    "growing": "생육기",
    "early": "초기 생육",
    "tuber": "괴경비대기",
    "spring": "봄 작기",
    "fall": "가을 작기",
}


def _stage_label(stage: str | None, status: str) -> str | None:
    if stage is not None:
        return STAGE_LABELS.get(stage, stage)
    if status == "out_of_season":
        return "제철 아님"
    # 기상 판정 근거가 없는 달 — "전기간"이라고 하면 정상 산출로 오해된다.
    # "휴면기"는 과수에만 맞는 말이라 쓰지 않는다 — 상추가 작기 밖에서 이 상태에 들어오는데
    # 한해살이는 휴면하지 않는다(0025). `statusLabel`이 이미 쓰던 표현으로 맞춘다.
    if status == "dormant":
        return "생육기 아님"
    return "전기간"


ORCHARD_FIELD_TYPE = "4"  # 농사로 경지구분 코드. 시드 0010이 사과·배에 부여한다.


def _crop_lookup(db: Session, crop_ids: set[int]) -> dict[int, Crop]:
    """작물 ID → Crop. 대시보드가 밭마다 이름·과수여부를 따로 조회하던 것을 한 번으로 묶는다.

    작물이 5종 고정이라(§2 YAGNI) 밭이 몇 개든 이 쿼리는 최대 5행이다.
    """
    if not crop_ids:
        return {}
    rows = db.query(Crop).filter(Crop.id.in_(crop_ids)).all()
    return {c.id: c for c in rows}


def _region_name_lookup(db: Session, region_ids: set[int]) -> dict[int, str]:
    if not region_ids:
        return {}
    rows = db.query(Region.id, Region.name).filter(Region.id.in_(region_ids)).all()
    return dict(rows)


# 예보를 못 구한 날 카드가 조용히 비어 있으면 "위험 없음"으로 읽힌다(§18-4·§12).
NO_FORECAST_LIMITATION = "오늘 예보를 확보하지 못해 당일 적합도를 계산하지 못했습니다."


def today_values(short_term: dict[str, object], on_date: date) -> dict[str, object]:
    """단기 결과에서 **오늘 하루**를 골라 카드에 실을 값으로. 순수 함수.

    `days[0]`을 쓰지 않고 날짜로 찾는다 — 발표시각에 따라 첫 행이 내일일 수 있고, 그러면
    카드가 조용히 내일 점수를 오늘로 보여준다. 장기 점수로 폴백하지도 않는다 — 출처가
    다른 값을 같은 자리에 끼워 넣으면 유저는 무엇을 보고 있는지 알 수 없다(§18-4).
    """
    days: list[dict[str, object]] = short_term["days"]  # type: ignore[assignment]
    limitations: list[str] = short_term["limitations"]  # type: ignore[assignment]
    day = next((d for d in days if d["target_date"] == on_date), None)
    if day is None:
        return {
            "growth_stage": None,
            "score": None,
            "grade": None,
            "status": "insufficient_data",
            "limitations": [NO_FORECAST_LIMITATION, *limitations],
        }
    return {
        "growth_stage": day["growth_stage"],
        "score": day["score"],
        "grade": day["grade"],
        "status": day["status"],
        "limitations": limitations,
    }


def build_dashboard(
    db: Session, user_id: int, service_key: str, on_date: date, now: datetime
) -> DashboardResponse:
    """유저 소유 밭 전체를 카드로. 소유권은 user_id 스코프(§11).

    밭마다 단기 예보를 타지만 `get_forecast_rows`가 (지역, 발표시각) 단위로 캐시하므로
    같은 시/군 밭이 여러 개여도 외부 호출은 한 번이다(§18-1).
    """
    farms = (
        db.query(UserFarm)
        .filter(UserFarm.user_id == user_id)
        .order_by(UserFarm.id)
        .all()
    )
    # 작물명·지역명·과수여부는 밭마다 달라지지 않는 소수 값이라 한 번에 모아둔다 —
    # 종전엔 밭 개수만큼 3연속 조회가 반복됐다(N+1). 예보 조회(compute_short_term)는
    # 밭마다 지역이 달라 배치가 안 된다 — 그건 진짜 N개의 외부 API 호출이다.
    crops = _crop_lookup(db, {f.crop_id for f in farms})
    region_names = _region_name_lookup(db, {f.region_id for f in farms})

    cards: list[DashboardCard] = []
    for farm in farms:
        st = compute_short_term(db, user_id, farm.id, service_key, on_date, now)
        s = today_values(st, on_date)
        crop = crops.get(farm.crop_id)
        cards.append(
            DashboardCard(
                farm_id=farm.id,
                crop_id=farm.crop_id,
                crop_name=crop.name if crop else None,
                region_name=region_names.get(farm.region_id),
                crop_type="orchard" if crop and crop.exam_field_type == ORCHARD_FIELD_TYPE else "field",
                growth_stage=s["growth_stage"],
                growth_stage_label=_stage_label(s["growth_stage"], s["status"]),
                score=s["score"],
                grade=s["grade"],
                status=s["status"],
                label=st["label"],
                limitations=s["limitations"],
            )
        )
    return DashboardResponse(as_of=on_date, farms=cards)
