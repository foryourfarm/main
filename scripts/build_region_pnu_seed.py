"""연속지적도(LSMD_CONT_LDREG, data.go.kr) DBF에서 시군구별 대표 PNU 1건 추출.

SoilCharacSctnn(심토토성/심토자갈함량/경사도) API는 PNU(19자리 지번코드) 단건 조회만
지원해 전국 필지 전수 조회는 불가능함(soil_profile_client.py 참고). 그래서 시군구
단위로만 하기로 함 — region_seed.csv의 시/군마다 대표 필지 1개를 골라 그 PNU로만
조회한다.
[한계] 시/군 내 필지 간 실제 토성 편차는 반영하지 못하는 시/군 단위 근사치다.
이 근사를 쓰는 다운스트림(soil_state 등)은 UI/문서에 "시/군 대표값" 한계를 명시해야
한다(CLAUDE.md §4, §12).

대표 필지 선정 기준: 시군구 shp의 DBF 레코드 순서상 첫 번째(삭제 마커 제외) 레코드.
기준 자체는 임의적이지만 같은 입력엔 항상 같은 출력이 나오는 결정론적 규칙이다(§2).

DBF는 PNU 필드 하나만 읽으면 돼서 GDAL/pyshp 같은 GIS 의존성 없이 stdlib(struct)로
직접 파싱한다.

사용법:
    python scripts/build_region_pnu_seed.py <shp_dir>
        <shp_dir>: LSMD_CONT_LDREG_*.dbf들이 있는 디렉터리(zip 압축 해제 결과)

출력:
    docs/seed/region_pnu_seed.csv : id, name, sido, bjd_code, pnu_code
"""

import csv
import struct
import sys
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent.parent / "docs" / "seed"


def read_first_pnu(dbf_path: Path) -> str | None:
    """DBF 레코드 중 삭제되지 않은 첫 레코드의 PNU 필드값(없으면 None)."""
    data = dbf_path.read_bytes()
    header_len, record_len = struct.unpack("<HH", data[8:12])

    fields: list[tuple[str, int, int]] = []  # (name, offset_in_record, length)
    offset = 0
    pos = 32
    while data[pos : pos + 1] != b"\r":
        name = data[pos : pos + 11].split(b"\x00")[0].decode("ascii")
        length = data[pos + 16]
        fields.append((name, offset, length))
        offset += length
        pos += 32

    pnu_field = next(((o, ln) for n, o, ln in fields if n == "PNU"), None)
    if pnu_field is None:
        return None
    pnu_offset, pnu_len = pnu_field

    body = data[header_len:]
    for i in range(0, len(body) - record_len + 1, record_len):
        record = body[i : i + record_len]
        if record[0:1] == b"*":  # 삭제 마커 레코드는 건너뜀
            continue
        raw = record[1 + pnu_offset : 1 + pnu_offset + pnu_len].strip()
        # 일부 배치는 PNU 필드에 "47850100030001-대실-2" 같은 지명 텍스트가 섞여 들어옴(이상치).
        # 숫자 19자리가 아니면 유효 PNU로 안 보고 다음 레코드로 건너뜀(§12 이상치 방어).
        if raw.isascii() and raw.isdigit():
            return raw.decode("ascii")
    return None


def find_dbf(shp_dir: Path, sgg_code: str) -> Path | None:
    matches = sorted(shp_dir.glob(f"LSMD_CONT_LDREG_{sgg_code}_*.dbf"))
    return matches[0] if matches else None


def main() -> None:
    if len(sys.argv) != 2:
        print("사용법: python scripts/build_region_pnu_seed.py <shp_dir>")
        raise SystemExit(1)

    shp_dir = Path(sys.argv[1])
    with (SEED_DIR / "region_seed.csv").open(encoding="utf-8") as f:
        regions = list(csv.DictReader(f))

    rows: list[dict[str, str]] = []
    missing: list[str] = []
    for r in regions:
        sgg_code = r["bjd_code"][:5]
        dbf_path = find_dbf(shp_dir, sgg_code)
        pnu = read_first_pnu(dbf_path) if dbf_path else None
        if pnu is None:
            missing.append(f"{r['sido']} {r['name']}({sgg_code})")
            continue
        rows.append({**r, "pnu_code": pnu})

    out_path = SEED_DIR / "region_pnu_seed.csv"
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "name", "sido", "bjd_code", "pnu_code"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"대표 PNU 매핑: {len(rows)}개 -> {out_path}")
    if missing:
        print(f"[확인 필요] shp 못 찾음/PNU 없음 {len(missing)}개: {missing}")


if __name__ == "__main__":
    main()
