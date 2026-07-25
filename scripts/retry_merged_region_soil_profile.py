"""전남광주통합특별시(병합) 지역 26개 재시도 — SoilCharacSctnn API가 아직 신규 통합
행정코드(12xx)를 인식 못 해서(201 PARAM_VALI_ERROR) region_soil_profile_seed.csv에서
빠진 건들을, 병합 전 옛 시군구코드로 바꿔치기한 PNU로 재조회한다.

신/구 코드 대응 검증 방법: 병합 전 원본(20250415.csv, 삭제일자 컬럼 있음 -> 그 시점 기준
유효한 시/군 코드만 필터)과 병합 후(20260630.csv 유래 bjd_to_region.csv)의 읍면동명을
직접 대조 -> 앞 5자리(시도+시군구)만 바뀌고 읍면동 이하 5자리는 그대로임을 확인함
(예: 목포시 용당동 신12110/구46110, 둘 다 010100). 그래서 PNU 19자리 중 앞 5자리만
옛 코드로 치환하고 나머지(읍면동 5자리+산/일반 1자리+본번 4자리+부번 4자리)는 그대로 둔다.

region_pnu_seed.csv/region_soil_profile_seed.csv엔 신규 통합코드 PNU를 그대로 유지한다
(다음 분기 API 갱신되면 그걸로 다시 조회 가능해야 하므로) — 옛 코드 PNU는 이번 조회에만
쓰는 임시 우회 수단이다.

사용법:
    python scripts/retry_merged_region_soil_profile.py <병합전_법정동코드_CSV>
        예: python scripts/retry_merged_region_soil_profile.py 20250415.csv

출력: docs/seed/region_soil_profile_seed.csv에 성공한 건만 append(재실행 시 이미 있는 id 스킵)
"""

import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_region_soil_profile import (  # noqa: E402
    DEEPSOIL_GRAVEL,
    DEEPSOIL_TEXTURE,
    SOIL_SLOPE,
    TPS,
    call,
    load_service_key,
)

ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = ROOT / "docs" / "seed"


def load_old_sgg_codes(old_bjd_csv: Path) -> dict[str, str]:
    """병합 전 법정동코드 파일에서 시군구명 -> 옛 5자리 시군구코드(그 시점 기준 유효한 것만)."""
    with old_bjd_csv.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        code_col, sido_col, sgg_col, dong_col, ri_col, _, _, del_col, _ = reader.fieldnames
        rows = list(reader)

    mapping: dict[str, str] = {}
    for r in rows:
        if r[sido_col] not in ("전라남도", "광주광역시"):
            continue
        if r[dong_col] or r[ri_col] or r[del_col]:  # 읍면동/리 레벨이거나 이미 폐지된 코드는 제외
            continue
        if not r[sgg_col]:
            continue
        mapping[r[sgg_col]] = r[code_col][:5]
    return mapping


def main() -> None:
    if len(sys.argv) != 2:
        print(f"사용법: python {Path(__file__).name} <병합전_법정동코드_CSV>")
        raise SystemExit(1)

    old_sgg_by_name = load_old_sgg_codes(Path(sys.argv[1]))

    with (SEED_DIR / "region_pnu_seed.csv").open(encoding="utf-8") as f:
        all_regions = list(csv.DictReader(f))

    out_path = SEED_DIR / "region_soil_profile_seed.csv"
    fieldnames = ["id", "name", "sido", "bjd_code", "pnu_code", "deepsoil_texture", "deepsoil_gravel", "soil_slope"]
    with out_path.open(encoding="utf-8", newline="") as f:
        done_ids = {row["id"] for row in csv.DictReader(f)}

    todo = [r for r in all_regions if r["id"] not in done_ids]
    print(f"미완료 {len(todo)}개 중 옛 코드 매칭 가능한 건만 재시도")

    service_key = load_service_key()
    interval = 1.0 / TPS
    matched = 0
    with out_path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        for r in todo:
            old_sgg = old_sgg_by_name.get(r["name"])
            if old_sgg is None:
                print(f"  [{r['name']}] 옛 코드 매칭 실패 - 스킵")
                continue
            old_pnu = old_sgg + r["pnu_code"][5:]
            matched += 1

            result_code, result_msg, item = call(old_pnu, service_key)
            time.sleep(interval)

            if result_code == "301":
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
                print(f"  [{r['name']}] 옛PNU {old_pnu}: {result_code} {result_msg} - 여전히 실패")
                continue

            writer.writerow(row)
            f.flush()
            print(f"  [{r['name']}] 옛PNU {old_pnu} -> 성공")

    print(f"옛 코드 매칭 {matched}개 시도, 완료 -> {out_path}")


if __name__ == "__main__":
    main()
