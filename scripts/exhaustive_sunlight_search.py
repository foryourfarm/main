#!/usr/bin/env python3
"""
일조시간 데이터 철저한 조사
- 모든 218개 지점
- 여러 연도 (2025, 2024, 2023, 2022, 2021, 2020)
- getWeatherYearMonList3 사용
"""
import requests
import xml.etree.ElementTree as ET
import json
from datetime import datetime
from collections import defaultdict

# .env에서 serviceKey 로드
service_key = None
with open('.env', 'r', encoding='utf-8') as f:
    for line in f:
        if 'weather_API' in line and '=' in line:
            service_key = line.split('=')[1].strip().split('#')[0].strip()
            if service_key:
                break

BASE_URL = 'http://apis.data.go.kr/1390802/AgriWeather/WeatherObsrInfo/V3/GnrlWeather'

print("="*100)
print("일조시간 데이터 철저한 조사")
print("="*100)
print()

# ============================================================================
# Step 1: 관측지점 목록 조회
# ============================================================================

print("Step 1: 관측지점 목록 조회...")

all_spots = []
for page_no in range(1, 4):
    url = 'http://apis.data.go.kr/1390802/AgriWeather/getObsrSpotList'
    params = {
        'serviceKey': service_key,
        'Page_No': str(page_no),
        'Page_Size': '100'
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        root = ET.fromstring(response.content)
        items = root.findall('body/items/item')

        for item in items:
            spot_code = item.findtext('Obsr_Spot_Code')
            spot_name = item.findtext('Obsr_Spot_Nm')
            region = item.findtext('Do_Se_Nm', 'Unknown')

            if spot_code:
                all_spots.append({
                    'code': spot_code,
                    'name': spot_name,
                    'region': region
                })

        print(f"  page {page_no}: {len(items)} spots (total: {len(all_spots)})")

        if not items:
            break

    except Exception as e:
        print(f"  ERROR page {page_no}: {e}")

print(f"\n✅ 총 {len(all_spots)}개 지점 확인\n")

# ============================================================================
# Step 2: 모든 지점 × 여러 연도 조사
# ============================================================================

print("="*100)
print("Step 2: 지점별 일조시간 데이터 조사")
print("="*100)
print(f"대상: {len(all_spots)}개 지점 × 6개 연도 (총 {len(all_spots)*6}건)\n")

years = ['2025', '2024', '2023', '2022', '2021', '2020']
endpoint = f"{BASE_URL}/getWeatherYearMonList3"

# 결과 집계
region_stats = defaultdict(lambda: {
    'total_spots': 0,
    'spots_with_sunlight': set(),
    'spots_tested': 0,
    'years_with_data': defaultdict(int)
})

total_checked = 0
total_with_sunlight = 0
spots_with_data = {}  # {spot_code: {year: has_data}}

for idx, spot in enumerate(all_spots):
    spot_code = spot['code']
    region = spot['region']

    if region not in region_stats:
        region_stats[region]['total_spots'] = 0
    region_stats[region]['total_spots'] += 1
    region_stats[region]['spots_tested'] += 1

    has_data_in_any_year = False

    # 여러 연도 시도
    for year in years:
        params = {
            'serviceKey': service_key,
            'Page_No': '1',
            'Page_Size': '12',
            'search_Year': year,
            'obsr_Spot_Cd': spot_code
        }

        try:
            response = requests.get(endpoint, params=params, timeout=30)
            root = ET.fromstring(response.content)

            result_code = root.findtext('header/result_Code')

            if result_code == '200':
                items = root.findall('body/items/item')

                sun_times = []
                for item in items:
                    sun_time_elem = item.find('sun_Time')
                    if sun_time_elem is not None and sun_time_elem.text:
                        sun_times.append(sun_time_elem.text)

                if sun_times:
                    has_data_in_any_year = True
                    region_stats[region]['spots_with_sunlight'].add(spot_code)
                    region_stats[region]['years_with_data'][year] += 1

                    if spot_code not in spots_with_data:
                        spots_with_data[spot_code] = {}
                    spots_with_data[spot_code][year] = True

        except Exception as e:
            pass

        total_checked += 1

    if has_data_in_any_year:
        total_with_sunlight += 1

    if (idx + 1) % 30 == 0 or (idx + 1) == len(all_spots):
        print(f"  Progress: {idx+1}/{len(all_spots)} | Found: {total_with_sunlight}")

# ============================================================================
# Step 3: 결과 집계
# ============================================================================

print("\n" + "="*100)
print("📊 최종 결과")
print("="*100)

print(f"\n{'지역':<20} {'총':<8} {'일조':<8} {'비율':<10} {'년도별':<40}")
print("-" * 100)

total_all = 0
total_with = 0

for region in sorted(region_stats.keys()):
    stats = region_stats[region]
    total = stats['total_spots']
    with_sun = len(stats['spots_with_sunlight'])
    ratio = 100 * with_sun / total if total > 0 else 0

    total_all += total
    total_with += with_sun

    # 년도별 통계
    years_info = ', '.join([f"{y}({stats['years_with_data'][y]})" for y in years if stats['years_with_data'][y] > 0])
    if not years_info:
        years_info = "없음"

    mark = "✅" if ratio >= 50 else "⚠️" if ratio >= 20 else "❌"
    print(f"{region:<20} {total:<8} {with_sun:<8} {mark} {ratio:>6.1f}% {years_info:<40}")

overall_ratio = 100 * total_with / total_all if total_all > 0 else 0

print("-" * 100)
print(f"{'합계':<20} {total_all:<8} {total_with:<8} {overall_ratio:>6.1f}%")

# ============================================================================
# Step 4: 데이터 있는 지점 샘플 출력
# ============================================================================

if spots_with_data:
    print("\n" + "="*100)
    print("💡 일조시간 데이터가 있는 지점 샘플")
    print("="*100)
    print()

    sample_count = 0
    for spot in all_spots:
        if spot['code'] in spots_with_data:
            years_str = ', '.join(sorted(spots_with_data[spot['code']].keys()))
            print(f"✅ {spot['region']:<15} | {spot['name']:<20} | {spot['code']:<15} | {years_str}")
            sample_count += 1
            if sample_count >= 15:
                print(f"... 외 {len(spots_with_data) - sample_count}개 지점")
                break

# ============================================================================
# 결론
# ============================================================================

print("\n" + "="*100)
print("🎯 결론")
print("="*100)

print(f"\n일조시간 데이터 커버율: {overall_ratio:.1f}% ({total_with}/{total_all}개 지점)")

if overall_ratio >= 70:
    print("\n✅ 높은 커버율 - 실측 우선 + 계산 보조 가능")
elif overall_ratio >= 30:
    print("\n⚠️ 부분 커버 - 혼합 처리 필요 (실측 + 계산)")
elif overall_ratio > 0:
    print("\n⚠️ 낮은 커버율 - Angstrom 계산 기반 + 극소수 실측")
else:
    print("\n❌ 실측 일조시간 데이터 없음 - Angstrom 계산 필수")

# ============================================================================
# 결과 저장
# ============================================================================

output = {
    'timestamp': datetime.now().isoformat(),
    'total_spots': total_all,
    'spots_with_sunlight': total_with,
    'coverage_percent': round(overall_ratio, 1),
    'years_tested': years,
    'region_stats': {
        region: {
            'total': stats['total_spots'],
            'with_sunlight': len(stats['spots_with_sunlight']),
            'coverage_percent': round(100 * len(stats['spots_with_sunlight']) / stats['total_spots'], 1) if stats['total_spots'] > 0 else 0,
            'years_with_data': dict(stats['years_with_data'])
        }
        for region, stats in sorted(region_stats.items())
    },
    'sample_spots_with_data': {
        spot_code: list(years_dict.keys())
        for spot_code, years_dict in list(spots_with_data.items())[:20]
    }
}

with open('docs/data/exhaustive_sunlight_investigation.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"\n📁 상세 결과 저장: docs/data/exhaustive_sunlight_investigation.json")
print("\n✅ 조사 완료")
