"""구역·법정동 대표 고도 시드 생성 (오프라인·재실행 가능, 앱 밖).

**왜 필요한가**: 기온은 고도에 직접 지배된다(환경감률 약 0.65℃/100m). 실측(10km 이내
지점쌍, 7월 일최고기온)에서 고도차 200~500m면 MAE 2.29℃, 500m 넘으면 5.07℃다. 거리를
좁혀도 안 잡힌다 — 평년치 도너를 거리만으로 고르면 한라산 지점과 해안 지점이 같은 후보에
든다(서귀포시 도너 고도 산포 1,524m). 고도를 알아야 도너를 거르고, 밭 위치로 감률 보정을
한다. nexttodo.md "구역·밭 고도 확보" 참고.

**표고 출처: SRTM 30m (NASA, 공공도메인)** — OpenTopoData 공개 API로 조회하고 **값만**
시드 CSV에 커밋한다(런타임 의존 없음). 대안 검토 결과:
  - VWorld: 고도 Open API가 2019년 종료됐고, 약관상 저장 금지라 시드 용도에 부적합
    (`gen_region_grid_seed.py`가 지오코딩을 버린 것과 같은 이유).
  - 국토지리정보원 DEM(data.go.kr 15059920, 이용허락 제한 없음): 5m급으로 가장 정확하나
    IMG 래스터 도엽 단위 + 로그인 다운로드 + GDAL 계열 의존성이 필요하다.
  - SRTM을 **우리 관측지점 752개의 실측 고도**에 대고 검증했다:
        MAE 8.8m / median 3.0m / p90 19m / bias +1.7m
    감률 환산 **0.06℃**다. 잡으려는 오차가 2.29~5.07℃라 DEM 5m급으로 올려 얻는
    이득(0.06→0.01℃)이 의미가 없다. 100m 넘게 튄 10개는 급경사지 지점 좌표 반올림으로 보인다.

**좌표 출처는 두 개이고, 층마다 우선순위가 다르다.**

    리      : 리 폴리곤 중심점 → 소속 읍·면 대표점 → 시군구 대표점
    읍면동  : 읍면동 대표점(취락) → 읍면동 폴리곤 중심점 → 시군구 대표점

  1. **기상청 격자 엑셀** — 읍면동마다 점 하나(실질적으로 주민센터·관청 자리 = 취락).
     시군구는 행정구역코드로 256/256 직매칭. 읍면동 행은 **행정동 코드**라 법정동 직매칭이
     1,408건뿐이어서 (시도, 시군구, 읍면동) **이름**으로 붙인다(20,275건 중 17,123건).
     엑셀은 리 좌표를 주지 않으므로 리에 대해서는 **소속 읍·면**의 점이 된다
     — 그래서 같은 면의 리끼리 값이 같아진다.
  2. **국토지리정보원 공간정보공동활용 폴리곤**(`bjd_polygon.py`) — 법정구역 경계의 기하
     중심. 이용허락 제한 없음, 로그인 없이 직접 다운로드, 좌표가 이미 WGS84, 의존성 0.
     리 15,209건 중 92.6%가 붙는다(2023-09 기준이라 코드 지연을 3단계로 되짚는다).

**왜 층마다 우선순위가 다른가 — 단위 크기 때문이다.** 폴리곤 중심점은 취락이 아니라 도형의
중심이라 **영역이 넓고 산이 끼면 사람 없는 고지대로 올라간다.** 시군구에서 격자중심(서귀포
209m)을 버리고 관청 소재지(76m)를 택한 것과 같은 실패 모드다. 실측(취락점 대비):

    리(면적 작음)     편향 **0m** / MAE 61m               산간 63개 리
    읍면동(면적 큼)   편향 **+53m** / p90 204m / max 484m
                      예) 달성군 가창면 취락 102m vs 폴리곤 597m (면 전체가 비슬산 자락)

그래서 **자기 취락 점이 있으면 그걸 쓰고, 없으면 폴리곤, 그것도 없으면 상위 단위**다.
리는 애초에 자기 취락 점이 없어서 폴리곤이 1순위가 되고, 도시 법정동(엑셀 이름매칭 실패분)도
같은 이유로 폴리곤이 시군구 폴백보다 앞선다.

**리에 폴리곤을 쓰면 없어지는 것은 계통 편향이다.** 종전엔 산간 면 6곳 **전부**에서 면
대표점이 리들보다 낮았고(평균 +170m ≈ 1.1℃), 그건 모든 산간 밭 기온을 일관되게 과대평가하는
방향이었다 — 서리·저온 위험을 과소평가하는 쪽이다. 61m 랜덤 오차는 방향이 갈려 상쇄된다.

**한계**: 리 대표점도 밭의 실측 고도가 아니다. 리 영역이 산으로 뻗은 곳은 여전히 어긋난다
(63개 중 8개가 120m 초과 — 진부면 화의리 +385m, 시천면 사리 −252m).

실행(폴리곤은 선택 — 안 주면 종전 엑셀 전용 동작으로 돌아간다):
    backend/.venv/Scripts/python.exe scripts/gen_altitude_seed.py "<격자_위경도.xlsx>" \
        --ri-polygon <LP_AA_RI.csv> --emd-polygon <LP_AA_EMD.csv>
"""

import argparse
import csv
import json
import time
import urllib.request
from pathlib import Path

import openpyxl

from bjd_polygon import augment_by_name, legacy_sgg_map, load_centroids, resolve

ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = ROOT / "docs" / "seed"
REGION_SEED = SEED_DIR / "region_seed.csv"
BJD_SEED = SEED_DIR / "bjd_to_region.csv"
REGION_OUT = SEED_DIR / "region_altitude_seed.csv"
DISTRICT_OUT = SEED_DIR / "district_altitude_seed.csv"

# OpenTopoData 공개 인스턴스 제한: 100 locations/call, 1 call/sec, 1000 call/day.
# 좌표를 중복 제거하면 약 3,800점 → 38콜이라 제한 안쪽이다.
API = "https://api.opentopodata.org/v1/srtm30m"
BATCH = 100
SLEEP_SEC = 1.2

# `altitude_source` 값 — 근사 정도가 달라 한계 문구가 이걸 보고 갈린다(§18-4).
SOURCE_RI_POLYGON = "ri_polygon"  # 리 자기 경계의 중심점
SOURCE_EMD = "emd_point"  # 읍·면·동 대표점(취락). 리 행이면 **소속 읍·면**의 점이다
SOURCE_EMD_POLYGON = "emd_polygon"  # 읍·면·동 자기 경계의 중심점
SOURCE_REGION = "region_point"  # 시군구 대표점 — 마지막 폴백

COL_CODE, COL_SIDO, COL_SGG, COL_EMD = 1, 2, 3, 4
COL_LON, COL_LAT = 13, 14


def read_excel(path: Path) -> tuple[dict[str, tuple[float, float]], dict[tuple, tuple[float, float]]]:
    """(행정구역코드→시군구 좌표, (시도,시군구,읍면동)→좌표)."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = list(wb[wb.sheetnames[0]].iter_rows(values_only=True))
    wb.close()

    by_code: dict[str, tuple[float, float]] = {}
    by_name: dict[tuple, tuple[float, float]] = {}
    for r in rows[1:]:
        try:
            point = (float(r[COL_LAT]), float(r[COL_LON]))
        except (TypeError, ValueError):
            continue
        if r[COL_EMD]:
            by_name[(r[COL_SIDO], r[COL_SGG], r[COL_EMD])] = point
        elif r[COL_SGG]:
            by_code[str(r[COL_CODE])] = point
    return by_code, by_name


def fetch_altitudes(points: list[tuple[float, float]]) -> dict[tuple[float, float], float]:
    """좌표 → 표고(m). 좌표를 중복 제거해 부르므로 호출 수가 지점 수보다 훨씬 적다(§18-1)."""
    out: dict[tuple[float, float], float] = {}
    for i in range(0, len(points), BATCH):
        chunk = points[i : i + BATCH]
        query = "|".join(f"{lat},{lon}" for lat, lon in chunk)
        with urllib.request.urlopen(f"{API}?locations={query}", timeout=60) as resp:
            results = json.load(resp)["results"]
        for point, res in zip(chunk, results):
            # 해상 격자 등은 null이 온다. 값을 지어내지 않고 비운다(§18-4).
            if res.get("elevation") is not None:
                out[point] = float(res["elevation"])
        print(f"  표고 {min(i + BATCH, len(points))}/{len(points)}", flush=True)
        time.sleep(SLEEP_SEC)
    return out


def polygon_point(
    bjd_code: str, centroids: dict[str, tuple[float, float]], legacy: dict[str, str]
) -> tuple[float, float] | None:
    """폴리곤이 없으면(미지정 실행 포함) None — 호출부가 다음 후보로 넘어간다."""
    if not centroids:
        return None
    return resolve(bjd_code, centroids, legacy)


def main() -> None:
    ap = argparse.ArgumentParser(description="구역·법정동 대표 고도 시드 생성")
    ap.add_argument("excel", help="기상청 격자_위경도 xlsx")
    ap.add_argument("--ri-polygon", type=Path, help="LP_AA_RI.csv (data.go.kr 15123130)")
    ap.add_argument("--emd-polygon", type=Path, help="LP_AA_EMD.csv (data.go.kr 15123128)")
    args = ap.parse_args()

    legacy = legacy_sgg_map()
    # 폴리곤은 선택이다 — 없으면 종전 엑셀 전용 동작으로 돌아간다(팀원이 292MB를 받지
    # 않고도 시드를 재생성할 수 있어야 한다).
    ri_poly, ri_names = (
        load_centroids(args.ri_polygon) if args.ri_polygon else ({}, {})
    )
    emd_poly, emd_names = (
        load_centroids(args.emd_polygon, "00") if args.emd_polygon else ({}, {})
    )
    if ri_poly or emd_poly:
        print(f"폴리곤 로드: 리 {len(ri_poly)}건 / 읍면동 {len(emd_poly)}건")

    by_code, by_name = read_excel(Path(args.excel))
    districts_all = list(csv.DictReader(BJD_SEED.open(encoding="utf-8")))

    # 코드로 못 찾은 것을 이름으로 이어 붙인다 — 구(區) 신설처럼 코드가 통째로 재부여된
    # 구역은 코드 규칙으로는 못 푼다. 찾은 것은 현행 코드를 키로 폴리곤 표에 합쳐 두면
    # 아래 조회부가 그대로 직접 히트로 찾는다.
    if ri_poly:
        added = augment_by_name(
            [(d["bjd_code"], d["ri"]) for d in districts_all if d["ri"]],
            ri_poly, ri_names, legacy,
        )
        ri_poly.update(added)
        print(f"  리 이름 매칭으로 추가 확보 {len(added)}건")
    if emd_poly:
        added = augment_by_name(
            [(d["bjd_code"], d["eupmyeondong"]) for d in districts_all if not d["ri"]],
            emd_poly, emd_names, legacy,
        )
        emd_poly.update(added)
        print(f"  읍면동 이름 매칭으로 추가 확보 {len(added)}건")
    regions = list(csv.DictReader(REGION_SEED.open(encoding="utf-8")))
    districts = districts_all

    # 구역 좌표
    region_point: dict[str, tuple[float, float]] = {}
    for r in regions:
        point = by_code.get(r["bjd_code"])
        if point is not None:
            region_point[r["id"]] = point
    missing_regions = [r["name"] for r in regions if r["id"] not in region_point]

    # 법정동 좌표 — 층마다 우선순위가 다르다(모듈 docstring "왜 층마다 다른가" 참고).
    region_id_by_name = {(r["sido"], r["name"]): r["id"] for r in regions}
    district_point: dict[str, tuple[tuple[float, float], str]] = {}
    for d in districts:
        excel = by_name.get((d["sido"], d["region_name"], d["eupmyeondong"]))
        region_id = region_id_by_name.get((d["sido"], d["region_name"]))
        region_fallback = region_point.get(region_id) if region_id else None

        if d["ri"]:
            # 리: 자기 폴리곤 → 소속 읍·면 대표점 → 시군구. 엑셀은 리 좌표를 아예 주지
            # 않아서 `excel`은 **소속 면**의 점이다 — 같은 면 리끼리 값이 같아진다.
            candidates = [
                (polygon_point(d["bjd_code"], ri_poly, legacy), SOURCE_RI_POLYGON),
                (excel, SOURCE_EMD),
                (region_fallback, SOURCE_REGION),
            ]
        else:
            # 읍면동: 취락 점(엑셀) → 자기 폴리곤 → 시군구. 폴리곤을 뒤로 두는 건 측정
            # 결과다 — 읍면동은 영역이 넓어 기하 중심이 산으로 올라간다(실측 편향 +53m,
            # 달성군 가창면은 마을 102m vs 폴리곤 597m).
            candidates = [
                (excel, SOURCE_EMD),
                (polygon_point(d["bjd_code"], emd_poly, legacy), SOURCE_EMD_POLYGON),
                (region_fallback, SOURCE_REGION),
            ]

        for point, source in candidates:
            if point is not None:
                district_point[d["bjd_code"]] = (point, source)
                break

    unique = sorted({*region_point.values(), *(p for p, _ in district_point.values())})
    print(f"구역 {len(region_point)}/{len(regions)}개, 법정동 {len(district_point)}/{len(districts)}개")
    print(f"중복 제거 좌표 {len(unique)}점 → API {(len(unique) + BATCH - 1) // BATCH}콜\n")

    altitude = fetch_altitudes(unique)

    with REGION_OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["region_id", "altitude_m"])
        w.writeheader()
        for region_id, point in sorted(region_point.items(), key=lambda t: int(t[0])):
            if point in altitude:
                w.writerow({"region_id": region_id, "altitude_m": round(altitude[point])})

    by_source: dict[str, int] = {}
    with DISTRICT_OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["bjd_code", "altitude_m", "altitude_source"])
        w.writeheader()
        for bjd_code, (point, source) in sorted(district_point.items()):
            if point not in altitude:
                continue
            by_source[source] = by_source.get(source, 0) + 1
            w.writerow(
                {
                    "bjd_code": bjd_code,
                    "altitude_m": round(altitude[point]),
                    "altitude_source": source,
                }
            )

    print(f"\n{REGION_OUT.relative_to(ROOT)}  {sum(1 for p in region_point.values() if p in altitude)}행")
    print(f"{DISTRICT_OUT.relative_to(ROOT)}  {sum(by_source.values())}행 {by_source}")
    if missing_regions:
        # 조용히 빠지면 그 구역만 고도 필터가 꺼진다 — 반드시 드러낸다.
        print(f"[확인 필요] 엑셀에 좌표 없는 구역 {len(missing_regions)}개: {missing_regions}")


if __name__ == "__main__":
    main()
