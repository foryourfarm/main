"""region 256개 → 기상청 장기예보 권역 매핑 시드 SQL 생성 (개발 보조 스크립트).

기상청 3개월전망 RSS는 13개 권역(전국 + 12권역) 단위로만 나오는데 우리 region은 시/군
256개다. 그 매핑을 마스터 시드로 남기기 위한 SQL을 docs/seed/region_seed.csv에서 생성한다.

매핑 근거:
- 시/도 단위 권역은 KMA 권역명과 우리 sido를 명시 대응(문자열 매칭 금지 — 시드의
  '전남광주통합특별시'는 KMA의 '광주ㆍ전라남도'와 이름이 다르다).
- 강원 영서/영동은 시/군 단위 분리라 명시 열거(대관령 기준 통상 분류).
- 태백시는 영서/영동 어느 쪽인지 공식 근거를 찾지 못해 '전국' 권역으로 폴백하고
  is_fallback=true로 남긴다(추측으로 지역값을 단정하지 않음 — CLAUDE.md §18-4).

사용법: python scripts/gen_outlook_zone_seed.py   (표준출력의 SQL을 마이그레이션에 붙인다)
"""

import csv
import sys
from pathlib import Path

SEED_CSV = Path(__file__).resolve().parent.parent / "docs" / "seed" / "region_seed.csv"

# KMA 3개월전망 RSS의 local_ta_name(공백/가운뎃점 정규화 후) → 우리 sido 목록
SIDO_TO_ZONE: dict[str, str] = {
    "서울특별시": "서울ㆍ인천ㆍ경기도",
    "인천광역시": "서울ㆍ인천ㆍ경기도",
    "경기도": "서울ㆍ인천ㆍ경기도",
    "대전광역시": "대전ㆍ세종ㆍ충청남도",
    "세종특별자치시": "대전ㆍ세종ㆍ충청남도",
    "충청남도": "대전ㆍ세종ㆍ충청남도",
    "충청북도": "충청북도",
    "전남광주통합특별시": "광주ㆍ전라남도",  # 시드 이름 ≠ KMA 이름 — 명시 대응 필수
    "전북특별자치도": "전북자치도",
    "부산광역시": "부산ㆍ울산ㆍ경상남도",
    "울산광역시": "부산ㆍ울산ㆍ경상남도",
    "경상남도": "부산ㆍ울산ㆍ경상남도",
    "대구광역시": "대구ㆍ경상북도",
    "경상북도": "대구ㆍ경상북도",
    "제주특별자치도": "제주도",
}

# 강원특별자치도는 시/군 단위로 갈린다(sido로 유도 불가).
GANGWON_YEONGSEO = {
    "춘천시", "원주시", "홍천군", "횡성군", "영월군",
    "평창군", "정선군", "철원군", "화천군", "양구군", "인제군",
}
GANGWON_YEONGDONG = {"강릉시", "동해시", "속초시", "삼척시", "고성군", "양양군"}

NATIONWIDE_ZONE = "전국(제주도,북한제외)"


def resolve_zone(name: str, sido: str) -> tuple[str, bool]:
    """(권역명, 폴백여부). 권역을 특정할 수 없으면 전국 권역 + 폴백 플래그."""
    if sido == "강원특별자치도":
        if name in GANGWON_YEONGSEO:
            return "강원도 영서", False
        if name in GANGWON_YEONGDONG:
            return "강원도 영동", False
        # 태백시: 공식 분류 근거 없음 → 전국값으로 폴백(UI에 '권역 미특정' 병기 대상)
        return NATIONWIDE_ZONE, True
    zone = SIDO_TO_ZONE.get(sido)
    if zone is None:
        return NATIONWIDE_ZONE, True
    return zone, False


def main() -> None:
    rows = list(csv.DictReader(SEED_CSV.open(encoding="utf-8")))
    values: list[str] = []
    fallbacks: list[str] = []
    for r in rows:
        zone, is_fallback = resolve_zone(r["name"], r["sido"])
        values.append(f"    ({r['id']}, '{zone}', {'true' if is_fallback else 'false'})")
        if is_fallback:
            fallbacks.append(f"{r['sido']} {r['name']}")

    print("        INSERT INTO region_outlook_zone (region_id, zone_name, is_fallback) VALUES")
    print(",\n".join(values))
    print("        ON CONFLICT (region_id) DO UPDATE")
    print("            SET zone_name = EXCLUDED.zone_name, is_fallback = EXCLUDED.is_fallback;")
    print(f"\n-- 총 {len(rows)}행, 폴백 {len(fallbacks)}건: {fallbacks}", file=sys.stderr)


if __name__ == "__main__":
    main()
