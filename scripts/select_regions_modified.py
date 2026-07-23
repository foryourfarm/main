"""
150개 지역 선정 스크립트.

data/raw/weather_observatory.csv (농업기상 관측지점 218개소, 이미 API로 확보된 데이터)의
관측지점명(Obsr_Spot_Nm)을 data/raw/beopjeongdong_code_utf8.tsv (행안부 법정동코드 전체자료,
사용자 제공)와 매칭해 각 관측지점에 해당하는 법정동코드(STDG_CD)를 찾는다.

이 방식을 쓰는 이유:
- 관측지점 = 실제 기상 관측이 이뤄지는 곳이므로, 이걸 지역으로 선정하면
  "03_weather_monthly.csv 관측지점 매핑" 문제가 자동으로 해결된다(매핑 자체가 필요 없음).
- weather_observatory.csv에 이미 Clmt_Zone_Code(기상지대, 22종)가 있어 기후대 다양성 축을
  별도 조사 없이 확보할 수 있다.

출력: data/raw/selected_regions.csv (region_code, region_name, obsr_spot_code, obsr_spot_name,
       do_se_code, clmt_zone_code, instl_la, instl_lo)
"""
import csv
import sys

BASE = r"C:\Users\k9643\OneDrive\바탕 화면\AI 해커톤"

def load_code_master(path):
    """법정동코드 마스터를 로드. 활성(존재) 항목만, 읍면동 레벨과 시군구 레벨을 분리해 반환."""
    eupmyeondong = {}  # 법정동명(전체) -> code, 읍면동 레벨(코드 뒤 6자리가 000000이 아님)
    sigungu = {}        # "시도 시군구" -> code, 시군구 레벨(코드 뒤 6자리가 000000, 앞 8자리는 0아님)
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)
        for row in reader:
            if len(row) < 3:
                continue
            code, name, status = row[0], row[1], row[2]
            if status != "존재":
                continue
            suffix6 = code[4:10]
            suffix8 = code[2:10]
            if suffix6 != "000000":
                eupmyeondong[name] = code
            elif suffix8 != "00000000":
                sigungu[name] = code
    return eupmyeondong, sigungu


def match_region(obsr_spot_nm, eupmyeondong, sigungu):
    """관측지점명(예: '아산시 염치읍')을 법정동명 접미사로 매칭해 법정동코드를 찾는다.
    1) 읍면동 레벨 완전 접미사 매칭 시도
    2) 실패 시 시군구 레벨(첫 토큰만) 접미사 매칭 시도 (fallback, 정밀도 낮음)
    반환: (code, matched_name, level) 또는 (None, None, None)
    """
    target = obsr_spot_nm.strip()
    # 1) 읍면동 레벨: 법정동명이 target으로 끝나는 것 찾기
    candidates = [(name, code) for name, code in eupmyeondong.items() if name.endswith(target)]
    if len(candidates) == 1:
        name, code = candidates[0]
        return code, name, "eupmyeondong"
    if len(candidates) > 1:
        # 가장 짧은 이름(가장 정확히 일치) 우선
        candidates.sort(key=lambda x: len(x[0]))
        name, code = candidates[0]
        return code, name, "eupmyeondong"

    # 2) 시군구 레벨 fallback: target의 첫 단어(시군구로 추정)만 사용
    parts = target.split()
    if not parts:
        return None, None, None
    gu_guess = parts[0]
    candidates = [(name, code) for name, code in sigungu.items() if name.endswith(gu_guess)]
    if len(candidates) == 1:
        name, code = candidates[0]
        return code, name, "sigungu"
    if len(candidates) > 1:
        candidates.sort(key=lambda x: len(x[0]))
        name, code = candidates[0]
        return code, name, "sigungu"

    return None, None, None


def main():
    eupmyeondong, sigungu = load_code_master(f"{BASE}/data/raw/beopjeongdong_code_utf8.tsv")
    print(f"법정동코드 마스터 로드: 읍면동 {len(eupmyeondong)}개, 시군구 {len(sigungu)}개", file=sys.stderr)

    stations = []
    with open(f"{BASE}/data/raw/weather_observatory.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stations.append(row)
    print(f"관측지점 {len(stations)}개 로드", file=sys.stderr)

    matched = []
    unmatched = []
    seen_codes = set()
    for st in stations:
        obsr_nm = st["Obsr_Spot_Nm"]
        code, matched_name, level = match_region(obsr_nm, eupmyeondong, sigungu)
        if code is None:
            unmatched.append(obsr_nm)
            continue
        if code in seen_codes:
            continue  # 중복 지역 스킵 (같은 법정동에 관측지점 2개 이상인 경우)
        seen_codes.add(code)
        matched.append({
            "region_code": code,
            "region_name": matched_name,
            "match_level": level,
            "obsr_spot_code": st["Obsr_Spot_Code"],
            "obsr_spot_name": obsr_nm,
            "do_se_code": st["Do_Se_Code"],
            "clmt_zone_code": st["Clmt_Zone_Code"],
            "instl_la": st["Instl_La"],
            "instl_lo": st["Instl_Lo"],
        })

    print(f"매칭 성공: {len(matched)}개, 매칭 실패: {len(unmatched)}개", file=sys.stderr)
    print("매칭 실패 목록:", unmatched, file=sys.stderr)

    eup_count = sum(1 for m in matched if m["match_level"] == "eupmyeondong")
    sgg_count = sum(1 for m in matched if m["match_level"] == "sigungu")
    print(f"  - 읍면동 레벨 매칭: {eup_count}개", file=sys.stderr)
    print(f"  - 시군구 레벨 매칭(fallback): {sgg_count}개", file=sys.stderr)

    # 기후대(clmt_zone_code) 분포 확인
    from collections import Counter
    zone_counter = Counter(m["clmt_zone_code"] for m in matched)
    print(f"기상지대 분포({len(zone_counter)}종): {dict(sorted(zone_counter.items()))}", file=sys.stderr)

    # 150개 선정: 기상지대 다양성을 위해 지대별로 최대한 고르게, 부족하면 있는 만큼 전부 사용
    target_n = 150
    if len(matched) <= target_n:
        selected = matched
    else:
        # 지대별로 그룹핑 후 라운드로빈으로 뽑아 다양성 확보
        by_zone = {}
        for m in matched:
            by_zone.setdefault(m["clmt_zone_code"], []).append(m)
        selected = []
        idx = 0
        zones = list(by_zone.keys())
        while len(selected) < target_n:
            zone = zones[idx % len(zones)]
            bucket = by_zone[zone]
            if bucket:
                selected.append(bucket.pop(0))
            idx += 1
            if all(not v for v in by_zone.values()):
                break

    print(f"최종 선정: {len(selected)}개 지역", file=sys.stderr)

    out_path = f"{BASE}/data/raw/selected_regions.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "region_code", "region_name", "match_level", "obsr_spot_code", "obsr_spot_name",
            "do_se_code", "clmt_zone_code", "instl_la", "instl_lo",
        ])
        writer.writeheader()
        for row in selected:
            writer.writerow(row)
    print(f"저장 완료: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
