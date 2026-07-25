# -*- coding: utf-8 -*-
"""
150개 선정 지역(data/raw/selected_regions.csv)을 대상으로 4개 CSV를 생성한다.
  - data/04_treatment_reference.csv : 기존 확보한 fertilizer.csv 재가공 (정적)
  - data/01_soil_chemistry.csv      : 농경지화학성 통계 API (pH/유기물/유효인산, 면적구간→가중평균 근사)
  - data/02_soil_physical.csv       : 토양검정 목록(PNU 확보) + 토양특성단면 API
  - data/03_weather_monthly.csv     : 농업기상 월별 API (최근 5년, 관측지점=선정지역 자체)
  - data/99_codebook.csv            : 위 과정에서 쓰인 코드 매핑 정리

실행 중 개별 지역 실패는 절대 전체를 죽이지 않고 NA 처리 후 계속 진행한다(PRD/CLAUDE.md의
"결측/이상치에도 산출 지속" 원칙과 동일하게 적용).
"""
import csv
import re
import sys
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

BASE = Path(r"C:\Users\k9643\OneDrive\바탕 화면\AI 해커톤")
DATA = BASE / "data"
RAW = DATA / "raw"

KEY = "ae177bc44d5648796cb031d4252477723b22644bb851d221867411fa75953cef"
TIMEOUT = 15
SESSION = requests.Session()


def get_xml(url, params, retries=2):
    params = dict(params)
    params["serviceKey"] = KEY
    for attempt in range(retries + 1):
        try:
            r = SESSION.get(url, params=params, timeout=TIMEOUT)
            r.encoding = "utf-8"
            root = ET.fromstring(r.text)
            return root
        except Exception as e:
            if attempt == retries:
                print(f"  [실패] {url} params={params} err={e}", file=sys.stderr)
                return None
            time.sleep(0.5)
    return None


def find_text(item, tag, alt_tag=None):
    el = item.find(tag)
    if el is None and alt_tag:
        el = item.find(alt_tag)
    return el.text if el is not None and el.text is not None else None


# ---------------------------------------------------------------------------
# 1) 04_treatment_reference.csv — 이미 확보된 fertilizer.csv 재가공 (정적, API 재호출 불필요)
# ---------------------------------------------------------------------------
def build_treatment_reference():
    out_rows = []
    with open(RAW / "fertilizer.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            n = float(row["pre_Fert_N"] or 0) + float(row["post_Fert_N"] or 0)
            p = float(row["pre_Fert_P"] or 0) + float(row["post_Fert_P"] or 0)
            k = float(row["pre_Fert_K"] or 0) + float(row["post_Fert_K"] or 0)
            out_rows.append({
                "crop_code": row["fstd_Crop_Code"],
                "crop_name": row["fstd_Crop_Nm"],
                "std_nitrogen": n,
                "std_phosphate": p,
                "std_potash": k,
            })
    with open(DATA / "04_treatment_reference.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["crop_code", "crop_name", "std_nitrogen", "std_phosphate", "std_potash"])
        w.writeheader()
        w.writerows(out_rows)
    print(f"04_treatment_reference.csv 생성 완료: {len(out_rows)}행", file=sys.stderr)


# ---------------------------------------------------------------------------
# 2) 01_soil_chemistry.csv — 농경지화학성 통계(면적구간) → 가중평균 근사
# ---------------------------------------------------------------------------
STAT_BASE = "http://apis.data.go.kr/1390802/SoilEnviron/SoilExamStat/V2"

# (필드접미사, 대표값) — 구간 중앙값 근사. 개방형 구간(이하/이상)은 인접 구간 폭으로 추정.
PH_BINS_NORMAL = [  # 논/밭/과수 공통
    ("1", 4.25), ("2", 4.8), ("3", 5.3), ("4", 5.8), ("5", 6.3), ("6", 6.8),
]
PH_BINS_FACHS = [  # 시설
    ("1", 4.75), ("2", 5.3), ("3", 5.8), ("4", 6.3), ("5", 6.8), ("6", 7.3),
]
OM_BINS = [  # 논/밭/시설/과수 공통 (g/kg)
    ("1", 5.0), ("2", 15.5), ("3", 25.5), ("4", 35.5), ("5", 45.5), ("6", 55.0),
]
AP_BINS_RFLD = [("1", 25.0), ("2", 75.5), ("3", 125.5), ("4", 175.5), ("5", 225.5), ("6", 275.0)]
AP_BINS_PFLD = [("1", 100.0), ("2", 250.5), ("3", 350.5), ("4", 450.5), ("5", 550.5), ("6", 650.0)]
AP_BINS_FACHS = [("1", 200.0), ("2", 600.5), ("3", 1000.5), ("4", 1400.5), ("5", 1800.5), ("6", 2200.0)]
AP_BINS_FRUIT = [("1", 100.0), ("2", 250.5), ("3", 350.5), ("4", 450.5), ("5", 550.5), ("6", 650.0)]

LANDTYPES = ["Rfld", "Pfld", "Fachs", "Fruit"]


def weighted_avg_from_stat(root, prefix, bins_by_landtype):
    """농경지화학성 통계 응답(root)에서 prefix_<Landtype><n>_Area 필드들을 모아 가중평균."""
    if root is None:
        return None
    item = root.find(".//item")
    if item is None:
        return None
    total_w = 0.0
    total_area = 0.0
    for lt in LANDTYPES:
        bins = bins_by_landtype[lt]
        for suffix, repr_val in bins:
            field = f"{prefix}_{lt}{suffix}_Area"
            txt = find_text(item, field)
            if txt in (None, ""):
                continue
            try:
                area = float(txt)
            except ValueError:
                continue
            total_area += area
            total_w += area * repr_val
    if total_area <= 0:
        return None
    return round(total_w / total_area, 3)


def fetch_soil_chemistry_row(region):
    code = region["region_code"]
    ph_root = get_xml(f"{STAT_BASE}/getFarmExamPhInfo", {"STDG_CD": code})
    om_root = get_xml(f"{STAT_BASE}/getFarmExamOmInfo", {"STDG_CD": code})
    ap_root = get_xml(f"{STAT_BASE}/getFarmExamApInfo", {"STDG_CD": code})

    ph = weighted_avg_from_stat(ph_root, "acid", {
        "Rfld": PH_BINS_NORMAL, "Pfld": PH_BINS_NORMAL, "Fachs": PH_BINS_FACHS, "Fruit": PH_BINS_NORMAL,
    })
    om = weighted_avg_from_stat(om_root, "om", {lt: OM_BINS for lt in LANDTYPES})
    ap = weighted_avg_from_stat(ap_root, "vldpha", {
        "Rfld": AP_BINS_RFLD, "Pfld": AP_BINS_PFLD, "Fachs": AP_BINS_FACHS, "Fruit": AP_BINS_FRUIT,
    })

    return {
        "region_code": code,
        "year": "NA",  # 이 API는 연도 파라미터/필드가 없음(현재 스냅샷 1건) — DataReport.md §2.1 참고
        "pH": ph if ph is not None else "NA",
        "organic_matter": om if om is not None else "NA",
        "available_p": ap if ap is not None else "NA",
        "k": "NA", "ca": "NA", "mg": "NA", "silicic_acid": "NA",  # 확장용, 이번 배치에서는 미수집
    }


def build_soil_chemistry(regions):
    rows = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        for i, row in enumerate(ex.map(fetch_soil_chemistry_row, regions)):
            rows.append(row)
            if (i + 1) % 20 == 0:
                print(f"  01_soil_chemistry 진행: {i + 1}/{len(regions)}", file=sys.stderr)
    with open(DATA / "01_soil_chemistry.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "region_code", "year", "pH", "organic_matter", "available_p", "k", "ca", "mg", "silicic_acid",
        ])
        w.writeheader()
        w.writerows(rows)
    print(f"01_soil_chemistry.csv 생성 완료: {len(rows)}행", file=sys.stderr)


# ---------------------------------------------------------------------------
# 3) 02_soil_physical.csv — 토양검정 목록(PNU 텍스트주소 확보) → PNU 역산 → 토양특성단면 조회
# ---------------------------------------------------------------------------
EXAM_BASE = "http://apis.data.go.kr/1390802/SoilEnviron/SoilExam/V2"
CHARAC_BASE = "http://apis.data.go.kr/1390802/SoilEnviron/SoilCharacSctnn/V2"


def load_children_codes():
    """법정동코드 마스터에서 자식(리/동) 코드 목록을 두 단위로 구성:
    - by_prefix8: '읍/면/동 코드(8자리)'의 하위 리 코드 (예: 강동면 -> 강동면 산하 각 리)
    - by_prefix5: '시/군/구 코드(5자리)'의 하위 모든 읍면동/리 코드 (시군구 레벨 코드 폴백용)
    """
    by_prefix8 = {}
    by_prefix5 = {}
    with open(RAW / "beopjeongdong_code_utf8.tsv", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        next(reader)
        for row in reader:
            if len(row) < 3 or row[2] != "존재":
                continue
            code = row[0]
            if code[4:10] == "000000":
                continue  # 시군구 레벨은 제외 (자식 후보 자체가 아님)
            by_prefix8.setdefault(code[:8], []).append(code)
            by_prefix5.setdefault(code[:5], []).append(code)
    return {"prefix8": by_prefix8, "prefix5": by_prefix5}


def parse_pnu_from_address(pnu_nm, stdg_code):
    """'... 모전리 75-1' 또는 '... 모전리 산 15-2' 형태의 주소를 19자리 PNU로 역산 구성(근사)."""
    tokens = pnu_nm.strip().split()
    if not tokens:
        return None
    last = tokens[-1]
    is_san = False
    if last.startswith("산"):
        is_san = True
        last = last[1:]
    elif len(tokens) >= 2 and tokens[-2] == "산":
        is_san = True
    m = re.match(r"^(\d+)(?:-(\d+))?$", last)
    if not m:
        return None
    bon = int(m.group(1))
    bu = int(m.group(2) or 0)
    san_flag = "2" if is_san else "1"
    return f"{stdg_code}{san_flag}{bon:04d}{bu:04d}"


def fetch_soil_physical_row(region, children_map):
    code = region["region_code"]
    if code[4:10] == "000000":  # 시군구 레벨 코드 -> 5자리 기준 자식 탐색 (더 넓게)
        siblings = children_map["prefix5"].get(code[:5], [])[:10]
    else:
        siblings = children_map["prefix8"].get(code[:8], [])[:6]
    candidate_codes = [code] + siblings

    pnu_cd = None
    for cand in candidate_codes:
        root = get_xml(f"{EXAM_BASE}/getSoilExamList", {"Page_Size": 1, "Page_No": 1, "STDG_CD": cand})
        if root is None:
            continue
        result_code = find_text(root, ".//Result_Code", ".//result_Code")
        if result_code != "200":
            continue
        item = root.find(".//item")
        if item is None:
            continue
        pnu_nm = find_text(item, "PNU_Nm", "Pnu_Nm")
        stdg_cd_used = find_text(item, "Stdg_Cd") or cand
        if pnu_nm:
            pnu_cd = parse_pnu_from_address(pnu_nm, stdg_cd_used)
            if pnu_cd:
                break

    if not pnu_cd:
        return {
            "region_code": code, "subsoil_texture_code": "NA",
            "subsoil_gravel_code": "NA", "slope_code": "NA",
        }

    root = get_xml(f"{CHARAC_BASE}/getSoilCharacterSctnn", {"PNU_CD": pnu_cd})
    if root is None:
        return {
            "region_code": code, "subsoil_texture_code": "NA",
            "subsoil_gravel_code": "NA", "slope_code": "NA",
        }
    item = root.find(".//item")
    if item is None:
        return {
            "region_code": code, "subsoil_texture_code": "NA",
            "subsoil_gravel_code": "NA", "slope_code": "NA",
        }
    return {
        "region_code": code,
        "subsoil_texture_code": find_text(item, "Deepsoil_Qlt_Cd") or "NA",
        "subsoil_gravel_code": find_text(item, "Deepsoil_Ston_Cd") or "NA",
        "slope_code": find_text(item, "Soilslope_Cd") or "NA",
    }


def build_soil_physical(regions):
    children_map = load_children_codes()
    rows = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = [ex.submit(fetch_soil_physical_row, r, children_map) for r in regions]
        for i, fut in enumerate(futures):
            rows.append(fut.result())
            if (i + 1) % 20 == 0:
                print(f"  02_soil_physical 진행: {i + 1}/{len(regions)}", file=sys.stderr)
    with open(DATA / "02_soil_physical.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["region_code", "subsoil_texture_code", "subsoil_gravel_code", "slope_code"])
        w.writeheader()
        w.writerows(rows)
    na_count = sum(1 for r in rows if r["subsoil_texture_code"] == "NA")
    print(f"02_soil_physical.csv 생성 완료: {len(rows)}행 (NA {na_count}행)", file=sys.stderr)


# ---------------------------------------------------------------------------
# 4) 03_weather_monthly.csv — 농업기상 월별(최근 5년), 관측지점=선정지역 자체
# ---------------------------------------------------------------------------
WEATHER_BASE = "http://apis.data.go.kr/1390802/AgriWeather/WeatherObsrInfo/V3/GnrlWeather"
YEARS = [2021, 2022, 2023, 2024, 2025]


def fetch_weather_rows(region):
    code = region["region_code"]
    spot = region["obsr_spot_code"]
    out = []
    for year in YEARS:
        root = get_xml(f"{WEATHER_BASE}/getWeatherYearMonList3", {
            "Page_No": 1, "Page_Size": 12, "search_Year": year, "obsr_Spot_Cd": spot,
        })
        if root is None:
            continue
        for item in root.findall(".//item"):
            date_txt = find_text(item, "date")  # "YYYY-MM"
            if not date_txt or "-" not in date_txt:
                continue
            y, m = date_txt.split("-")
            temp = find_text(item, "temp")
            rn = find_text(item, "rn")
            out.append({
                "region_code": code,
                "year": y,
                "month": m,
                "avg_temp": temp if temp not in (None, "") else "NA",
                "precipitation": rn if rn not in (None, "") else "NA",
            })
    return out


def build_weather_monthly(regions):
    rows = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = [ex.submit(fetch_weather_rows, r) for r in regions]
        for i, fut in enumerate(futures):
            rows.extend(fut.result())
            if (i + 1) % 20 == 0:
                print(f"  03_weather_monthly 진행: {i + 1}/{len(regions)}", file=sys.stderr)
    with open(DATA / "03_weather_monthly.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["region_code", "year", "month", "avg_temp", "precipitation"])
        w.writeheader()
        w.writerows(rows)
    print(f"03_weather_monthly.csv 생성 완료: {len(rows)}행", file=sys.stderr)


# ---------------------------------------------------------------------------
def load_regions():
    with open(RAW / "selected_regions.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    regions = load_regions()
    print(f"대상 지역 {len(regions)}개 로드", file=sys.stderr)

    build_treatment_reference()

    t0 = time.time()
    build_soil_chemistry(regions)
    print(f"  경과 {time.time()-t0:.0f}s", file=sys.stderr)

    t0 = time.time()
    build_soil_physical(regions)
    print(f"  경과 {time.time()-t0:.0f}s", file=sys.stderr)

    t0 = time.time()
    build_weather_monthly(regions)
    print(f"  경과 {time.time()-t0:.0f}s", file=sys.stderr)

    print("전체 완료", file=sys.stderr)


if __name__ == "__main__":
    main()
