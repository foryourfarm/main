"""관측지점 → 구역 매핑 시드 생성 (오프라인, 앱 밖).

두 관측망을 `docs/seed/observation_point_seed.csv` 한 장으로 합친다. 계층별로 배정
메커니즘이 다르다 — 상세 근거는 `MappingReport.md`.

| 계층 | 관측망 | 배정 방법 | 이유 |
|---|---|---|---|
| 1차 | 농업기상 218 | **좌표 → 최근접 구역** | `getObsrSpotList`가 Instl_La/Lo를 준다(Sample-code.py) |
| 2차 | 기상청 AWS 534 | **좌표 → 최근접 구역** | 동일. 두 계층이 같은 메커니즘을 쓴다 |

**왜 CSV로 고정하는가**: 런타임에 API를 부르거나 좌표를 재계산하지 않기 위해서다. 배정 결과를
커밋해 두면 재현 가능하고, 지점이 신설·폐지되면 diff로 드러난다(§10 마스터 데이터는 시드로).

실행:
    backend/.venv/Scripts/python.exe scripts/gen_observation_point_seed.py
    backend/.venv/Scripts/python.exe scripts/gen_observation_point_seed.py --write
"""

import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.infra.public_api.kma_grid import latlon_to_grid  # noqa: E402
from app.infra.public_api.kma_station_client import get_aws_stations  # noqa: E402
from app.infra.public_api.agri_station_client import get_agri_stations  # noqa: E402

SEED_DIR = ROOT / "docs" / "seed"
REGION_GRID_SEED = SEED_DIR / "region_grid_seed.csv"
OUT_CSV = SEED_DIR / "observation_point_seed.csv"

# AWS 일람표 발표년월. 최신으로 올리면 신규·폐지 지점이 반영된다.
AWS_YEAR, AWS_MONTH = "2025", "1"

# 응답에 섞여 있는 테스트 지점. 실제 관측소가 아니라 적재하면 안 된다.
EXCLUDED_NAMES = {"동방로거테스트"}


def load_region_grids() -> dict[tuple[int, int], int]:
    """격자(nx, ny) → region_id.

    좌표 기반 배정에는 이것만 있으면 된다 — 구역명·읍면동 색인은 이름 매칭 시절의 유물이라
    함께 지웠다(§9.2). 좌표는 행정 명칭 체계를 따지지 않는다.
    """
    grid_to_region: dict[tuple[int, int], int] = {}
    with REGION_GRID_SEED.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            # 같은 격자에 여러 구역이 걸릴 수 있다(서울 종로/중구는 둘 다 60,127).
            # 먼저 나온 구역을 쓴다 — 5km 격자 안에서는 어느 쪽이든 기상값이 사실상 같다.
            grid_to_region.setdefault((int(row["nx"]), int(row["ny"])), int(row["region_id"]))

    return grid_to_region


GRID_KM = 5.0  # 기상청 단기예보 격자 간격
# 지점을 구역에 배정할 최대 거리. 이보다 멀면 "그 구역의 관측소"라고 부를 수 없다.
# 시군구 반경이 대략 10~30km라 40km로 둔다 — 초과분은 도서·격자 밖 지점이다.
MAX_ASSIGN_KM = 40.0


def resolve_by_coords(
    lat: float, lon: float, region_grids
) -> tuple[int | None, str, float | None, tuple[int, int] | None]:
    """AWS 지점 좌표 → **최근접 구역**. 행정계층 문제를 겪지 않는 경로.

    격자 정확 일치를 쓰지 않는 이유: `region_grid`는 구역당 대표 격자 1개(고유 224개)만
    갖는데 전국 격자는 149×253=37,697칸이다. 정확 일치를 요구하면 534개 지점 중 71개만
    붙는다(실측). 그래서 격자 거리 최근접으로 배정하고 **거리를 함께 기록**한다 —
    거리를 숨기면 40km 떨어진 관측값을 그 구역 값처럼 보이게 만든다(§18-4).
    """
    try:
        nx, ny = latlon_to_grid(lat, lon)
    except ValueError:
        return None, "격자범위밖", None, None

    best_id, best_d2 = None, None
    for (rnx, rny), region_id in region_grids:
        d2 = (nx - rnx) ** 2 + (ny - rny) ** 2
        if best_d2 is None or d2 < best_d2:
            best_id, best_d2 = region_id, d2

    if best_id is None:
        return None, "구역없음", None, (nx, ny)
    distance = (best_d2**0.5) * GRID_KM
    if distance > MAX_ASSIGN_KM:
        return None, f"최근접 구역도 {MAX_ASSIGN_KM:.0f}km 초과", distance, (nx, ny)
    return best_id, "좌표 최근접", distance, (nx, ny)


def main() -> None:
    write = "--write" in sys.argv
    grid_to_region = load_region_grids()
    rows: list[dict] = []
    stats: dict[str, int] = defaultdict(int)

    # ── 2차: 기상청 AWS (좌표 기반) ──
    region_grids = [(g, rid) for g, rid in grid_to_region.items()]
    print(f"기상청 AWS 지점 조회 ({AWS_YEAR}-{AWS_MONTH})...")
    for st in get_aws_stations(AWS_YEAR, AWS_MONTH):
        if st.name in EXCLUDED_NAMES:
            continue
        region_id, how, distance, grid = resolve_by_coords(
            st.latitude, st.longitude, region_grids
        )
        stats[f"aws/{how}"] += 1
        rows.append(
            {
                "point_code": st.point_code,
                "name": st.name,
                "lat": round(st.latitude, 6),
                "lon": round(st.longitude, 6),
                "altitude": st.altitude,
                "nx": grid[0] if grid else "",
                "ny": grid[1] if grid else "",
                "region_id": region_id or "",
                "distance_km": "" if distance is None else round(distance, 1),
                "network": "kma_aws",
            }
        )
    print(f"  {len(rows)}개")

    # ── 1차: 농업기상 (좌표 기반 — AWS와 동일 메커니즘) ──
    # getObsrSpotList가 Instl_La/Instl_Lo를 주므로 지점명 문자열 파싱이 필요 없다.
    # (이전에는 관측 응답에 좌표가 없어 이름을 파싱했고 광역시·통합시에서 깨졌다.)
    print("농업기상 지점 조회(getObsrSpotList)...")
    agri_stations = get_agri_stations()
    print(f"  {len(agri_stations)}개")
    for st in agri_stations:
        if st.name in EXCLUDED_NAMES:
            stats["agri/테스트지점제외"] += 1
            continue
        region_id, how, distance, grid = resolve_by_coords(
            st.latitude, st.longitude, region_grids
        )
        stats[f"agri/{how}"] += 1
        rows.append(
            {
                "point_code": st.point_code,
                "name": st.name,
                "lat": round(st.latitude, 6),
                "lon": round(st.longitude, 6),
                "altitude": st.altitude,
                "nx": grid[0] if grid else "",
                "ny": grid[1] if grid else "",
                "region_id": region_id or "",
                "distance_km": "" if distance is None else round(distance, 1),
                "network": "agri",
            }
        )

    print("\n배정 결과:")
    for key in sorted(stats):
        print(f"  {key:34s} {stats[key]:4d}")

    # ── 커버리지: 구역 관점으로 본다 ──
    # 지점→구역 배정(위)만 세면 "그 구역 안에 지점이 있는가"만 나온다. 정작 필요한 것은
    # "구역이 쓸 지점이 있는가"이고, 최근접 지점을 허용하면 답이 달라진다(§6.3 대체 로직).
    total_regions = sum(1 for _ in csv.DictReader(REGION_GRID_SEED.open(encoding="utf-8")))
    inside = defaultdict(set)
    for r in rows:
        if r["region_id"]:
            inside[r["network"]].add(r["region_id"])
    union_inside = inside["agri"] | inside["kma_aws"]
    print(f"\n구역 커버리지 (전체 {total_regions}개)")
    print("  [구역 안에 지점이 있는 경우]")
    print(f"    농업기상(1차): {len(inside['agri'])}   AWS(2차): {len(inside['kma_aws'])}"
          f"   합집합: {len(union_inside)}")

    grids = [(int(r["nx"]), int(r["ny"]), r["network"]) for r in rows if r["nx"] != ""]
    worst = 0.0
    resolved = 0
    for region_grid, _rid in grid_to_region.items():
        best = min(
            (((region_grid[0] - nx) ** 2 + (region_grid[1] - ny) ** 2) ** 0.5 * GRID_KM
             for nx, ny, _n in grids),
            default=None,
        )
        if best is not None:
            resolved += 1
            worst = max(worst, best)
    print("  [최근접 지점 대체 허용 — 확정된 다중지점 규칙]")
    print(f"    배정 가능 구역: {resolved} / {len(grid_to_region)} 격자  (최대 거리 {worst:.1f}km)")
    print(f"    → 격자 매핑이 있는 모든 구역이 지점을 갖는다. 거리는 UI에 표기해야 한다(§18-4).")

    if not write:
        print("\n(--write 를 주면 시드를 갱신한다)")
        return

    with OUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "point_code", "name", "lat", "lon", "altitude",
                "nx", "ny", "region_id", "distance_km", "network",
            ],
        )
        w.writeheader()
        w.writerows(rows)
    print(f"\n갱신: {OUT_CSV.relative_to(ROOT)} ({len(rows)}행)")


if __name__ == "__main__":
    main()
