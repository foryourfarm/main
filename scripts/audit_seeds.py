"""시드 적재 점검 — 배포 후 "조용히 비어 있는 테이블"을 화면에 증상이 뜨기 전에 잡는다.

**왜 필요한가**: 2026-08-01 프로덕션 갱신 배포에서 3개월전망(`weather_outlook`)이 비어 있는
것을 장기 탭 한계 문구("기상청 3개월전망이 적재되지 않아…")를 눈으로 읽고서야 알았다.
PR #28~29로 만든 tercile 보정이 그때까지 프로덕션에서 무효였다. 배포 절차가
`load_districts.py`만 돌리기 때문인데, 나머지 시드는 **없어도 예외가 나지 않고**
"데이터 부족"·"보정 없음"으로 조용히 degrade하도록 설계돼 있어(§12, §18-5) 증상이 늦게 뜬다.
그 설계는 옳지만, 그래서 적재 여부는 따로 세어봐야 한다.

읽기 전용이다 — count와 몇 개 집계만 돌린다.

실행 (프록시 띄운 뒤, DATABASE_URL이 잡힌 셸에서):
    backend/.venv/bin/python scripts/audit_seeds.py
"""

import sys
from pathlib import Path

from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.db.session import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Crop,
    CropGrowthGuide,
    CropGrowthStage,
    District,
    KmaObservationPoint,
    KnowledgeChunk,
    Region,
    RegionGrid,
    RegionOutlookZone,
    SoilChangeRule,
    WeatherClimatology,
    WeatherOutlook,
)

# (모델, 라벨, 기대행수 또는 None, 비었을 때 무엇이 깨지는지)
# 기대행수는 "이 값이어야 한다"가 아니라 "이보다 적으면 부분 적재를 의심한다"는 기준선이다.
# 근거: region/region_grid 256(시군구), district 20,275(읍면동 5,066 + 리 15,209),
# kma_observation_point 752(AWS 534 + 농업기상 218), crop 5종 고정.
CHECKS = [
    (Region, "region", 256, "지역 마스터 — 없으면 아무것도 못 돈다"),
    (RegionGrid, "region_grid", 256, "격자 없음 → 단기 탭·평년치 KNN 거리계산 불가"),
    (District, "district", 20275, "리 행 없으면 밭 등록이 FK 위반으로 실패"),
    (WeatherClimatology, "weather_climatology", None, "장기 탭이 12칸 '데이터 부족'"),
    (WeatherOutlook, "weather_outlook", None, "3개월전망 보정 무효(평년치만 사용)"),
    (RegionOutlookZone, "region_outlook_zone", 256, "지역↔전망구역 매핑 없음 → 보정 대상 못 찾음"),
    (KmaObservationPoint, "kma_observation_point", 752, "관측지점 폴백 경로 없음"),
    (KnowledgeChunk, "knowledge_chunk", None, "챗봇 근거 0건 → 전부 '확실치 않음' 폴백"),
    (Crop, "crop", 5, "작물 마스터"),
    (CropGrowthGuide, "crop_growth_guide", None, "생육 지침 없음 → 채점 불가"),
    (CropGrowthStage, "crop_growth_stage", None, "생육 단계 없음 → 단계 판정 불가"),
    (SoilChangeRule, "soil_change_rule", None, "토양변화 계수 없음"),
]


def main() -> None:
    db = SessionLocal()
    problems: list[str] = []
    try:
        print(f"{'테이블':<26}{'행수':>9}   상태")
        print("-" * 72)
        for model, label, expected, breaks in CHECKS:
            count = db.scalar(select(func.count()).select_from(model)) or 0
            if count == 0:
                status = f"비어 있음 — {breaks}"
                problems.append(f"{label}: 0행 — {breaks}")
            elif expected is not None and count < expected:
                status = f"부분 적재? (기대 {expected:,})"
                problems.append(f"{label}: {count:,}행 (기대 {expected:,}) — 부분 적재 의심")
            else:
                status = "OK"
            print(f"{label:<26}{count:>9,}   {status}")

        print("\n[세부]")

        # 평년치는 총 행수보다 '몇 개 지역을 덮는가'가 실제 커버리지다(지역당 12행).
        covered = db.scalar(select(func.count(func.distinct(WeatherClimatology.region_id)))) or 0
        total_regions = db.scalar(select(func.count()).select_from(Region)) or 0
        print(f"평년치 보유 지역        {covered} / {total_regions}  (나머지는 KNN 거리가중 대체)")

        # 3개월전망은 매월 갱신되므로 '있다'가 아니라 '얼마나 최신인가'를 봐야 한다.
        latest = db.scalar(select(func.max(WeatherOutlook.published_at)))
        print(f"3개월전망 최신 발표     {latest or '없음'}")

        # 두 관측망을 한 테이블에 담으므로(network로 구분) 한쪽만 적재된 것을 잡는다.
        rows = db.execute(
            select(KmaObservationPoint.network, func.count()).group_by(KmaObservationPoint.network)
        ).all()
        print(f"관측지점 network별      {dict(rows) or '없음'}")

        # 작물별로 조각이 없으면 그 작물 상담만 근거 없이 답한다 — 총량으로는 안 보인다.
        rows = db.execute(
            select(KnowledgeChunk.crop_id, func.count()).group_by(KnowledgeChunk.crop_id)
        ).all()
        print(f"RAG 조각 작물별         {dict(rows) or '없음'}")

        print()
        if problems:
            print(f"문제 {len(problems)}건:")
            for p in problems:
                print(f"  - {p}")
            sys.exit(1)
        print("시드 이상 없음.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
