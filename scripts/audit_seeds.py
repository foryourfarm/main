"""시드 적재 점검 — 배포 후 "조용히 비어 있는 테이블·컬럼"을 화면에 증상이 뜨기 전에 잡는다.

**왜 필요한가**: 2026-08-01 프로덕션 갱신 배포에서 3개월전망(`weather_outlook`)이 비어 있는
것을 장기 탭 한계 문구("기상청 3개월전망이 적재되지 않아…")를 눈으로 읽고서야 알았다.
PR #28~29로 만든 tercile 보정이 그때까지 프로덕션에서 무효였다. 배포 절차가
`load_districts.py`만 돌리기 때문인데, 나머지 시드는 **없어도 예외가 나지 않고**
"데이터 부족"·"보정 없음"으로 조용히 degrade하도록 설계돼 있어(§12, §18-5) 증상이 늦게 뜬다.
그 설계는 옳지만, 그래서 적재 여부는 따로 세어봐야 한다.

**컬럼 단위 검사를 왜 더했나(2026-08-03)**: 행수만 세다가 더 큰 것을 놓쳤다. 프로덕션
`weather_climatology`는 1,392행으로 "OK"였는데 **`temp_night_min_normal`이 전 행 NULL**이었다
— 문제정의서가 A씨 실패 원인으로 지목했고 예선 PPT 7장의 차별점인 야간 저온이 그날까지
**한 번도 채점된 적이 없었다.** 같은 날 `solar_radiation_normal`·`region/district.altitude_m`도
전부 0행으로 드러났다. 원인은 배포 런북에 그 ETL들이 빠진 것이고, 행수 검사로는 안 보였다.

**이 파일이 곧 "어느 스크립트가 무엇을 채우는가" 지도다.** 별도 문서로 두면 코드와
어긋난다 — 아래 COLUMN_CHECKS의 세 번째 필드가 그 매핑이고, 비어 있으면 그 스크립트를
돌리라는 뜻이다.

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
]

# `soil_change_rule`은 검사 대상이 아니다 — **0행이 정상이다.** 토양변화는 shadow 전용이라
# 읽는 코드가 0건이고(`short_term_service.py` SOIL_LIMITATION 주석), 그래도 "문제 1건"으로
#세는 바람에 진짜 문제와 섞여 신호가 흐려졌다. 그 기능이 유저 경로에 붙는 날 되살린다.
_UNUSED_TABLES = {SoilChangeRule: "shadow 전용 — 읽는 코드 0건이라 0행이 정상"}

# (모델, 컬럼, 채우는 스크립트, 비었을 때 무엇이 깨지는지)
#
# **행수가 아니라 값이 있는 행수를 센다.** 테이블에 행이 있어도 특정 컬럼이 전 행 NULL이면
# 그 지표는 채점되지 않는데, 행수 검사로는 "OK"로 보인다(2026-08-03에 실제로 그랬다).
COLUMN_CHECKS = [
    (
        WeatherClimatology, "temp_avg_normal",
        "load_weather_climatology.py (농업기상) + load_aws_climatology.py (AWS)",
        "장기 탭 기온 채점 불가",
    ),
    (
        WeatherClimatology, "temp_night_min_normal",
        "load_aws_climatology.py — **이것만 채운다**",
        "야간 저온 채점 불가 (문제정의서가 지목한 A씨 실패 원인)",
    ),
    (
        WeatherClimatology, "rainfall_normal",
        "load_weather_climatology.py + load_aws_climatology.py",
        "강수 지표 결측",
    ),
    (
        WeatherClimatology, "solar_radiation_normal",
        "load_solar_radiation_normal.py",
        "일조 지표가 계속 빈다 (일조는 이 값에서 환산한다)",
    ),
    (
        Region, "altitude_m", "load_altitudes.py",
        "구역 대표 고도 없음 → 평년치 KNN 고도 필터 무효",
    ),
    (
        District, "altitude_m", "load_altitudes.py",
        "밭 고도 없음 → 기온 감률 보정(0.65℃/100m) 전부 미적용",
    ),
]

# 부분 결측이 **구조적으로 정상**인 컬럼 — 이유를 안 적으면 볼 때마다 다시 의심하게 된다.
# 2026-08-03 실측으로 확인한 값이며, 결측이 이보다 커지면 그때는 진짜 신호다.
_EXPECTED_PARTIAL = {
    "weather_climatology.temp_night_min_normal": (
        "농업기상 소스에 야간최저 항목이 없다 — AWS가 채운 구역만 값이 있다. "
        "2026-08-03 기준 1,392행(=116구역×12) 결측이 정상이다."
    ),
    "weather_climatology.temp_avg_normal": (
        "관측소 공백 구역(계룡·곡성·신안·영광·영동·영암·증평 7곳). "
        "load_aws_climatology는 '농업기상 1순위 보호'로 **구역 단위** 스킵이라 "
        "빈 칸도 안 채운다 — 읽기 시점 KNN 대체가 담당한다."
    ),
    "weather_climatology.rainfall_normal": "관측소 공백 구역(곡성·증평 2곳). 위와 같은 이유.",
    "weather_climatology.solar_radiation_normal": (
        "일사 관측소가 없는 구역(울릉 12개월·강화 2개월). 일사는 지점이 177개뿐이라 "
        "기온·강수보다 커버리지가 좁다."
    ),
}

# 전 행 NULL이어도 정상인 컬럼 — 이유를 적어 두지 않으면 다음 사람이 "결손"으로 오해한다.
_BY_DESIGN_NULL = {
    "weather_climatology.sunlight_normal": (
        "설계상 비어 있다 — 일조는 저장하지 않고 solar_radiation_normal에서 읽을 때 "
        "환산한다(보정계수가 바뀌면 저장값이 낡기 때문). 실측 일조가 생기면 쓰는 우선 필드."
    ),
}


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

        # 컬럼 단위 — 행은 있는데 값이 전부 NULL인 것을 잡는다.
        print(f"\n{'컬럼':<44}{'값있음/전체':>16}   상태")
        print("-" * 88)
        for model, column, filled_by, breaks in COLUMN_CHECKS:
            table = model.__tablename__
            total = db.scalar(select(func.count()).select_from(model)) or 0
            filled = db.scalar(
                select(func.count()).select_from(model).where(getattr(model, column).isnot(None))
            ) or 0
            label = f"{table}.{column}"
            ratio = f"{filled:,}/{total:,}"
            if total == 0:
                status = "테이블 자체가 빔(위 참고)"
            elif filled == 0:
                status = f"전 행 NULL — {breaks}"
                problems.append(f"{label}: 전 행 NULL — {breaks} → {filled_by} 실행 필요")
            elif filled < total:
                # 부분 결측은 관측망 커버리지 차이라 정상일 수 있다 — 실패로 치지 않는다.
                # 알려진 사유가 있으면 함께 찍는다. 사유 없는 결측만 눈에 띄게 하려는 것이다.
                note = _EXPECTED_PARTIAL.get(label)
                status = f"부분 결측 {total - filled:,}행"
                if note:
                    status += f" — 예상됨: {note}"
            else:
                status = "OK"
            print(f"{label:<44}{ratio:>16}   {status}")

        for name, why in _BY_DESIGN_NULL.items():
            print(f"{name:<44}{'(검사 안 함)':>16}   {why}")
        for model, why in _UNUSED_TABLES.items():
            print(f"{model.__tablename__:<44}{'(검사 안 함)':>16}   {why}")

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
