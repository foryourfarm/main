"""토양도 기반 토양특성 단면정보V2(SoilCharacSctnn) -> docs/seed/region_pnu_seed.csv의
대표 PNU마다 심토토성/심토자갈함량/경사도 조회 -> docs/seed/region_soil_profile_seed.csv.

[한계] region_pnu_seed.csv의 대표 PNU 자체가 시/군 단위 근사(대표 필지 1개)라
여기서 나오는 심토 정보도 시/군 평균이 아니라 "그 시/군의 필지 하나"짜리 근사치다.
UI/문서에 반드시 이 한계를 명시할 것(CLAUDE.md §4, §12).

기술명세서(ver1.0) 기준 요청/응답 필드명: PNU_CD(요청), PNU_Cd/Deepsoil_Qlt_Cd/
Deepsoil_Ston_Cd/Soilslope_Cd(응답). "_Code" 아님 — backend/app/infra/public_api/
soil_profile_client.py도 이 스펙에 맞게 같이 수정함.

사용법:
    python scripts/collect_region_soil_profile.py

출력: docs/seed/region_soil_profile_seed.csv
재실행 시 이미 처리된 id는 건너뛴다(중간에 죽어도 이어서 가능).
"""

import csv
import sys
import time
from pathlib import Path
from xml.etree import ElementTree

import httpx

ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = ROOT / "docs" / "seed"
ENV_PATH = ROOT / ".env"

BASE_URL = "http://apis.data.go.kr/1390802/SoilEnviron/SoilCharacSctnn/V2/getSoilCharacterSctnn"

# CLAUDE.md §12: 명세서의 초당 최대 트랜잭션(30 tps) 그대로 사용
TPS = 30
MAX_RETRIES = 3

# 코드표 (OPENAPI_soil_V2.pdf 3.1.1~3.1.3)
DEEPSOIL_TEXTURE = {
    "01": "사질", "02": "사양질", "03": "미사사양질",
    "04": "식양질", "05": "미사식양질", "06": "식질", "99": "기타",
}
DEEPSOIL_GRAVEL = {"01": "없음_0-15%", "02": "있음_15-35%", "03": "심함_35%이상", "99": "기타"}
SOIL_SLOPE = {
    "01": "경사_0-2%", "02": "경사_2-7%", "03": "경사_7-15%",
    "04": "경사_15-30%", "05": "경사_30-60%", "06": "경사_60-100%", "99": "기타",
}


def load_service_key() -> str:
    """루트 .env에서 인증키를 읽는다(soil_API — 토양도 기반 토양특성 단면정보 전용 키)."""
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("soil_API"):
            return line.split("=", 1)[1].strip()
    raise RuntimeError(f"{ENV_PATH}에서 soil_API 키를 찾지 못함")


def call(pnu_code: str, service_key: str) -> tuple[str, str, ElementTree.Element | None]:
    """(result_code, result_msg, item_element) 반환. item_element는 성공 시에만 유효."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = httpx.get(BASE_URL, params={"serviceKey": service_key, "PNU_CD": pnu_code}, timeout=10.0)
            resp.raise_for_status()
            root = ElementTree.fromstring(resp.text)
            code = root.findtext(".//header/Result_Code") or ""
            msg = root.findtext(".//header/Result_Msg") or ""
            item = root.find(".//body/items/item")
            return code, msg, item
        except (httpx.HTTPError, ElementTree.ParseError) as e:
            if attempt == MAX_RETRIES - 1:
                return "ERROR", str(e), None
            time.sleep(2**attempt)
    return "ERROR", "unreachable", None


def load_pnu_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def done_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open(encoding="utf-8", newline="") as f:
        return {row["id"] for row in csv.DictReader(f)}


def main() -> None:
    if len(sys.argv) != 1:
        print(f"사용법: python {Path(__file__).name}")
        raise SystemExit(1)

    service_key = load_service_key()
    in_path = SEED_DIR / "region_pnu_seed.csv"
    out_path = SEED_DIR / "region_soil_profile_seed.csv"
    fieldnames = ["id", "name", "sido", "bjd_code", "pnu_code", "deepsoil_texture", "deepsoil_gravel", "soil_slope"]

    regions = load_pnu_rows(in_path)
    done = done_ids(out_path)
    todo = [r for r in regions if r["id"] not in done]
    print(f"대상 {len(regions)}개 중 {len(todo)}개 진행 (기완료 {len(done)}개 스킵)")

    interval = 1.0 / TPS
    write_header = not out_path.exists()
    with out_path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()

        for i, r in enumerate(todo, 1):
            result_code, result_msg, item = call(r["pnu_code"], service_key)
            time.sleep(interval)

            if result_code == "301":  # 요청 데이터 없음 — 확정, 빈 값으로 기록
                row = {**r, "deepsoil_texture": "", "deepsoil_gravel": "", "soil_slope": ""}
            elif result_code == "200" and item is not None:
                fields = {child.tag: child.text for child in item}
                row = {
                    **r,
                    "deepsoil_texture": DEEPSOIL_TEXTURE.get(fields.get("Deepsoil_Qlt_Cd") or "", ""),
                    "deepsoil_gravel": DEEPSOIL_GRAVEL.get(fields.get("Deepsoil_Ston_Cd") or "", ""),
                    "soil_slope": SOIL_SLOPE.get(fields.get("Soilslope_Cd") or "", ""),
                }
            else:
                print(f"  [{r['name']}] {r['pnu_code']}: {result_code} {result_msg} - 이번엔 건너뜀(재실행 시 재시도)")
                continue

            writer.writerow(row)
            f.flush()
            if i % 20 == 0 or i == len(todo):
                print(f"  진행 {i}/{len(todo)}")

    print(f"완료 -> {out_path}")


if __name__ == "__main__":
    main()
