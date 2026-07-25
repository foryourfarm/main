"""대시보드 집계 — 유저의 모든 밭을 작물 카드로. 적합도(P2) + 이름/단계/타입 조인."""
from datetime import date

from sqlalchemy.orm import Session

from app.models import Crop, CropGrowthStage, Region, UserFarm
from app.schemas.dashboard import DashboardCard, DashboardResponse
from app.services.suitability_service import compute_farm_suitability

# 생육단계 코드 → 화면 표시용 한국어 라벨(표현용, 농업 기준값 아님).
STAGE_LABELS = {
    "fruit_growth": "결실비대기",
    "coloring": "착색기",
    "maturity": "성숙기",
    "growing": "생육기",
    "early": "초기 생육",
    "tuber": "괴경비대기",
}


def _stage_label(stage: str | None, status: str) -> str | None:
    if stage is not None:
        return STAGE_LABELS.get(stage, stage)
    return "제철 아님" if status == "out_of_season" else "전기간"


def _is_orchard(db: Session, crop_id: int) -> bool:
    # 과수(사과·배)는 연중일자 단계를 갖는다 — 시드에서 파생(하드코딩 아님).
    row = (
        db.query(CropGrowthStage.id)
        .filter(CropGrowthStage.crop_id == crop_id, CropGrowthStage.mode == "day_of_year")
        .first()
    )
    return row is not None


def build_dashboard(db: Session, user_id: int, on_date: date) -> DashboardResponse:
    """유저 소유 밭 전체를 카드로. 소유권은 user_id 스코프(§11)."""
    farms = (
        db.query(UserFarm)
        .filter(UserFarm.user_id == user_id)
        .order_by(UserFarm.id)
        .all()
    )
    cards: list[DashboardCard] = []
    for farm in farms:
        # ponytail: 밭당 조회 반복(N+1). 밭 수가 한 자릿수라 방치, 커지면 배치 조회로.
        s = compute_farm_suitability(db, user_id, farm.id, on_date)
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
                label=s["label"],
                limitations=s["limitations"],
            )
        )
    return DashboardResponse(as_of=on_date, farms=cards)
