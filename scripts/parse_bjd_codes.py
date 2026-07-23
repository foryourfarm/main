"""국토교통부 전국 법정동코드 CSV -> region 시드 + BJD코드-region 매핑 정리.

DB.md의 region 테이블(§3.2)은 시/군 단위(id, name, sido)로 설계되어 있어 읍면동/리까지는
안 담는다. 대신 유저가 밭 등록 시 입력하는 법정동코드(읍면동/리 단위)가 어느 시/군인지
찾을 수 있도록 매핑표를 같이 만든다.

원본 CSV 컬럼: 법정동코드,시도명,시군구명,읍면동명,리명,순위,생성일자
- 시도만 있고 시군구명이 빈 행 = 시/도 레벨(세종시처럼 예외적으로 시군구 레벨 행도 별도 존재)
- 읍면동명까지 있고 리명이 빈 행 = 읍면동 레벨
- 리명까지 있는 행 = 리 레벨
- 시군구명은 있는데 읍면동명이 빈 행 = 시/군 레벨 -> region 시드의 소스

사용법:
    python scripts/parse_bjd_codes.py "<원본 CSV 경로>"

출력 (docs/seed/):
    region_seed.csv      : id, name, sido, bjd_code   (시/군, DB.md region 시드용 — bjd_code는 참고용, region 테이블엔 안 들어감)
    bjd_to_region.csv     : bjd_code, sido, region_name, eupmyeondong, ri  (읍면동/리 -> region 매핑)
"""

import csv
import sys
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent.parent / "docs" / "seed"


def load_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def build_region_seed(rows: list[dict[str, str]]) -> list[tuple[int, str, str, str]]:
    """시군구명은 있고 읍면동명은 없는 행 = 시/군 레벨. 법정동코드 오름차순으로 안정적인 id 부여."""
    region_rows = [r for r in rows if r["시군구명"] and not r["읍면동명"]]
    region_rows.sort(key=lambda r: r["법정동코드"])
    seen: set[tuple[str, str]] = set()
    seed: list[tuple[int, str, str, str]] = []
    next_id = 1
    for r in region_rows:
        key = (r["시군구명"], r["시도명"])
        if key in seen:
            continue  # 동명 시군구가 광역시 산하 자치구 개편 등으로 중복 등장하는 경우 방어
        seen.add(key)
        seed.append((next_id, r["시군구명"], r["시도명"], r["법정동코드"]))
        next_id += 1
    return seed


def build_bjd_mapping(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """읍면동/리 레벨 행만 추출 — 시/도·시/군 레벨 행은 밭 주소로 선택될 일이 없어 제외."""
    return [
        {
            "bjd_code": r["법정동코드"],
            "sido": r["시도명"],
            "region_name": r["시군구명"],
            "eupmyeondong": r["읍면동명"],
            "ri": r["리명"],
        }
        for r in rows
        if r["읍면동명"]
    ]


def main() -> None:
    if len(sys.argv) != 2:
        print("사용법: python scripts/parse_bjd_codes.py <원본 CSV 경로>")
        raise SystemExit(1)

    rows = load_rows(Path(sys.argv[1]))
    SEED_DIR.mkdir(parents=True, exist_ok=True)

    region_seed = build_region_seed(rows)
    region_path = SEED_DIR / "region_seed.csv"
    with region_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "name", "sido", "bjd_code"])
        writer.writerows(region_seed)

    bjd_mapping = build_bjd_mapping(rows)
    mapping_path = SEED_DIR / "bjd_to_region.csv"
    with mapping_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["bjd_code", "sido", "region_name", "eupmyeondong", "ri"])
        writer.writeheader()
        writer.writerows(bjd_mapping)

    print(f"region 시드: {len(region_seed)}개 -> {region_path}")
    print(f"BJD 매핑: {len(bjd_mapping)}개 -> {mapping_path}")


if __name__ == "__main__":
    main()
