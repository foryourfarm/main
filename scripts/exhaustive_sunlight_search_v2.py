#!/usr/bin/env python3
import requests
import xml.etree.ElementTree as ET
import json
from datetime import datetime
from collections import defaultdict
import sys

sys.stdout.reconfigure(encoding='utf-8')

service_key = None
with open('.env', 'r', encoding='utf-8') as f:
    for line in f:
        if 'weather_API' in line and '=' in line:
            service_key = line.split('=')[1].strip().split('#')[0].strip()
            if service_key:
                break

BASE_URL = 'http://apis.data.go.kr/1390802/AgriWeather/WeatherObsrInfo/V3/GnrlWeather'

print("="*100)
print("Comprehensive Sunlight Investigation")
print("="*100)
print()

# Step 1: Get all observation points
print("Step 1: Fetching all observation points...")

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

        print(f"  Page {page_no}: {len(items)} spots (total: {len(all_spots)})")

        if not items:
            break

    except Exception as e:
        print(f"  ERROR page {page_no}: {e}")

print(f"\nTotal spots: {len(all_spots)}\n")

# Step 2: Test all spots across years
print("="*100)
print("Step 2: Testing all spots across years 2025, 2024, 2023, 2022, 2021, 2020")
print("="*100)
print()

years = ['2025', '2024', '2023', '2022', '2021', '2020']
endpoint = f"{BASE_URL}/getWeatherYearMonList3"

region_stats = defaultdict(lambda: {
    'total_spots': 0,
    'spots_with_sunlight': set(),
    'years_with_data': defaultdict(int)
})

total_with_sunlight = 0
spots_with_data = {}

for idx, spot in enumerate(all_spots):
    spot_code = spot['code']
    region = spot['region']

    region_stats[region]['total_spots'] += 1

    has_data_in_any_year = False

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

    if has_data_in_any_year:
        total_with_sunlight += 1

    if (idx + 1) % 30 == 0 or (idx + 1) == len(all_spots):
        print(f"Progress: {idx+1}/{len(all_spots)} | Found: {total_with_sunlight}")

# Step 3: Aggregate results
print("\n" + "="*100)
print("RESULTS BY REGION")
print("="*100)
print()

print(f"{'Region':<25} {'Total':<8} {'Has Data':<10} {'Coverage %':<12} {'Years':<40}")
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

    years_info = ', '.join([f"{y}({stats['years_with_data'][y]})" for y in years if stats['years_with_data'][y] > 0])
    if not years_info:
        years_info = "None"

    print(f"{region:<25} {total:<8} {with_sun:<10} {ratio:>6.1f}% {years_info:<40}")

overall_ratio = 100 * total_with / total_all if total_all > 0 else 0

print("-" * 100)
print(f"{'TOTAL':<25} {total_all:<8} {total_with:<10} {overall_ratio:>6.1f}%")

# Step 4: Show sample spots with data
if spots_with_data:
    print("\n" + "="*100)
    print("SAMPLE SPOTS WITH SUNLIGHT DATA")
    print("="*100)
    print()

    sample_count = 0
    for spot in all_spots:
        if spot['code'] in spots_with_data:
            years_str = ', '.join(sorted(spots_with_data[spot['code']].keys()))
            print(f"[OK] {spot['region']:<15} | {spot['name']:<20} | {spot['code']:<15} | Years: {years_str}")
            sample_count += 1
            if sample_count >= 15:
                remaining = len(spots_with_data) - sample_count
                if remaining > 0:
                    print(f"... and {remaining} more spots")
                break

# Conclusion
print("\n" + "="*100)
print("CONCLUSION")
print("="*100)

print(f"\nSunlight data coverage: {overall_ratio:.1f}% ({total_with}/{total_all} points)")

if overall_ratio >= 70:
    print("\nCoverage: HIGH - Use real measurements where available + calculated as backup")
elif overall_ratio >= 30:
    print("\nCoverage: MEDIUM - Mixed approach (real + calculated)")
elif overall_ratio > 0:
    print("\nCoverage: LOW - Angstrom-based calculation + few real measurements")
else:
    print("\nCoverage: NONE - Angstrom calculation mandatory")

# Save results
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
    }
}

with open('docs/data/exhaustive_sunlight_investigation.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"\nResults saved: docs/data/exhaustive_sunlight_investigation.json")
print("\nDone.")
