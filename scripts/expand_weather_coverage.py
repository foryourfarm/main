"""weather_climatology 커버리지 확장 — 미사용 관측지점으로 빈 지역을 채운다.

배경: ML용 03_weather_monthly_modified.csv는 218개 농업기상 관측지점 중 **150개만**
선정해 만들었다(data/raw/selected_regions_modified.csv — Data-Guideline.md §3의 층화표집
다양성 기준을 만족하는 표본을 뽑은 것이라 전국 커버가 목적이 아니었다). 그 결과
weather_climatology가 256개 시/군 중 102개만 채워졌다.

이 스크립트는 **선정에서 빠진 나머지 관측지점**을 마저 매칭해서, 지금 climatology가
없는 지역 중 몇 개나 실제 관측지점으로 채울 수 있는지 확인하고, 있으면 그 지점의
5년치를 실제 API로 받아온다. 지오코딩·대체값이 아니라 **그 지역 자체의 실측**이라
region_grid 격자-거리 대체보다 정확하다.

호출 방식(검증됨 — build_datasets_modified.py가 이미 이 형태로 9,000행을 성공 수신):
    GET {WEATHER_BASE}/getWeatherYearMonList3?obsr_Spot_Cd=...&search_Year=...
    응답 item: date("YYYY-MM"), temp, rn

사용법:
    backend/.venv/Scripts/python.exe scripts/expand_weather_coverage.py

출력: data/03_weather_monthly_modified.csv에 신규 지역 행을 append(기존 로더가 그대로
읽으므로 scripts/load_weather_climatology.py 재실행만 하면 DB에 반영된다).
"""

import csv
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models import Region, WeatherClimatology  # noqa: E402

RAW = ROOT / "data" / "raw"
STATIONS_CSV = RAW / "weather_observatory.csv"
BEOPJEONGDONG_TSV = RAW / "beopjeongdong_code_utf8_modified.tsv"
SELECTED_CSV = RAW / "selected_regions_modified.csv"
WEATHER_CSV = ROOT / "data" / "03_weather_monthly_modified.csv"
BJD_TO_REGION = ROOT / "docs" / "seed" / "bjd_to_region.csv"
REGION_SEED = ROOT / "docs" / "seed" / "region_seed.csv"

WEATHER_BASE = "http://apis.data.go.kr/1390802/AgriWeather/WeatherObsrInfo/V3/GnrlWeather"
YEARS = [2021, 2022, 2023, 2024, 2025]
TIMEOUT = 15.0


def load_code_master(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    """법정동코드 마스터 → (읍면동명→코드, 시군구명→코드). '존재' 상태만."""
    eupmyeondong: dict[str, str] = {}
    sigungu: dict[str, str] = {}
    with path.open(encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        next(reader)
        for row in reader:
            if len(row) < 3:
                continue
            code, name, status = row[0], row[1], row[2]
            if status != "존재":
                continue
            suffix6, suffix8 = code[4:10], code[2:10]
            if suffix6 != "000000":
                eupmyeondong[name] = code
            elif suffix8 != "00000000":
                sigungu[name] = code
    return eupmyeondong, sigungu


def match_station(name: str, eupmyeondong: dict[str, str], sigungu: dict[str, str]) -> str | None:
    """관측지점명(예: '아산시 염치읍') → 법정동코드. 읍면동 완전접미사 우선, 실패시 시군구."""
    target = name.strip()
    candidates = [(n, c) for n, c in eupmyeondong.items() if n.endswith(target)]
    if candidates:
        candidates.sort(key=lambda x: len(x[0]))
        return candidates[0][1]
    first_token = target.split()[0]
    sgg_candidates = [(n, c) for n, c in sigungu.items() if n.endswith(first_token)]
    if sgg_candidates:
        sgg_candidates.sort(key=lambda x: len(x[0]))
        return sgg_candidates[0][1]
    return None


def load_bjd_to_region_id() -> dict[str, int]:
    """법정동코드(읍면동/시군구 모두) → region_id. load_weather_climatology.py와 동일 매핑."""
    region_id_by_key: dict[tuple[str, str], int] = {}
    with REGION_SEED.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            region_id_by_key[(r["sido"], r["name"])] = int(r["id"])

    code_to_id: dict[str, int] = {}
    with BJD_TO_REGION.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rid = region_id_by_key.get((r["sido"], r["region_name"]))
            if rid is not None:
                code_to_id[r["bjd_code"]] = rid
    with REGION_SEED.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            code_to_id.setdefault(r["bjd_code"], int(r["id"]))
    return code_to_id


def fetch_weather_rows(bjd_code: str, station_code: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for year in YEARS:
        try:
            resp = httpx.get(
                f"{WEATHER_BASE}/getWeatherYearMonList3",
                params={
                    "serviceKey": settings.weather_api,
                    "Page_No": 1,
                    "Page_Size": 12,
                    "search_Year": year,
                    "obsr_Spot_Cd": station_code,
                },
                timeout=TIMEOUT,
            )
            root = ET.fromstring(resp.text)
        except (httpx.HTTPError, ET.ParseError) as e:
            print(f"  [실패] {station_code} {year}: {e}", file=sys.stderr)
            continue
        for item in root.findall(".//item"):
            date_el = item.find("date")
            if date_el is None or not date_el.text or "-" not in date_el.text:
                continue
            y, m = date_el.text.split("-")
            temp_el = item.find("temp")
            rn_el = item.find("rn")
            out.append(
                {
                    "region_code": bjd_code,
                    "year": y,
                    "month": m,
                    "avg_temp": temp_el.text if temp_el is not None and temp_el.text else "NA",
                    "precipitation": rn_el.text if rn_el is not None and rn_el.text else "NA",
                }
            )
        time.sleep(0.2)  # 연속 호출 완급 조절
    return out


def main() -> None:
    eupmyeondong, sigungu = load_code_master(BEOPJEONGDONG_TSV)
    stations = list(csv.DictReader(STATIONS_CSV.open(encoding="utf-8")))
    already_selected = {
        r["obsr_spot_code"] for r in csv.DictReader(SELECTED_CSV.open(encoding="utf-8"))
    }
    bjd_to_region_id = load_bjd_to_region_id()

    db = SessionLocal()
    try:
        covered = {r[0] for r in db.query(WeatherClimatology.region_id).distinct()}
        total_regions = db.query(Region.id).count()
    finally:
        db.close()

    print(f"현재 커버리지: {len(covered)}/{total_regions} 지역")

    # 미사용 관측지점만 골라 매칭 → 아직 안 채워진 region_id에 1지점씩만 배정.
    candidates: dict[int, tuple[str, str]] = {}  # region_id -> (bjd_code, station_code)
    unused = [s for s in stations if s["Obsr_Spot_Code"] not in already_selected]
    for s in unused:
        code = match_station(s["Obsr_Spot_Nm"], eupmyeondong, sigungu)
        if code is None:
            continue
        region_id = bjd_to_region_id.get(code)
        if region_id is None or region_id in covered or region_id in candidates:
            continue
        candidates[region_id] = (code, s["Obsr_Spot_Code"])

    print(f"미사용 관측지점 {len(unused)}개 중 신규 채움 가능 지역: {len(candidates)}개")
    if not candidates:
        print("추가할 지역이 없습니다.")
        return

    new_rows: list[dict[str, str]] = []
    for i, (region_id, (bjd_code, station_code)) in enumerate(candidates.items(), start=1):
        rows = fetch_weather_rows(bjd_code, station_code)
        new_rows.extend(rows)
        if i % 10 == 0 or i == len(candidates):
            print(f"  진행: {i}/{len(candidates)} (region_id={region_id} 완료, 누적 {len(new_rows)}행)")

    if not new_rows:
        print("[확인 필요] 매칭은 됐으나 API 응답이 전부 비었습니다 — 서비스키/지점코드 재확인 필요.")
        return

    with WEATHER_CSV.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["region_code", "year", "month", "avg_temp", "precipitation"])
        w.writerows(new_rows)

    print(f"append 완료: {len(new_rows)}행 -> {WEATHER_CSV.relative_to(ROOT)}")
    print("다음: backend/.venv/Scripts/python.exe scripts/load_weather_climatology.py 재실행")


if __name__ == "__main__":
    main()
