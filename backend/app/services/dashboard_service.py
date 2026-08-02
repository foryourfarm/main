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


def _is_orchard(db: Session, crop_id: int) -> bool:
    """재배 형태를 `crop.exam_field_type`(0010 시드)에서 읽는다.

    종전엔 "연중일자 단계를 가지면 과수"로 추론했는데, 0025가 상추에 달력 기준 작기
    단계를 세우면서 그 추론이 깨졌다(상추가 과수로 판정). 재배 형태를 실제로 적어둔
    컬럼이 이미 있으므로 그것을 읽는다.
    """
    return (
        db.query(Crop.exam_field_type).filter(Crop.id == crop_id).scalar() == ORCHARD_FIELD_TYPE
    )


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
    cards: list[DashboardCard] = []
    for farm in farms:
        # ponytail: 밭당 조회 반복(N+1). 밭 수가 한 자릿수라 방치, 커지면 배치 조회로.
        st = compute_short_term(db, user_id, farm.id, service_key, on_date, now)
        s = today_values(st, on_date)
        crop_name = db.query(Crop.name).filter(Crop.id == farm.crop_id).scalar()
        region_name = db.query(Region.name).filter(Region.id == farm.region_id).scalar()
        cards.append(
            DashboardCard(
                farm_id=farm.id,
                crop_id=farm.crop_id,
                crop_name=crop_name,
                region_name=region_name,
                crop_type="orchard" if _is_orchard(db, farm.crop_id) else "field",
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
