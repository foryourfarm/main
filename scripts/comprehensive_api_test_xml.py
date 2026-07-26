#!/usr/bin/env python3
"""
농업기상 API 전수 조사 - XML 응답 파싱
"""
import requests
import xml.etree.ElementTree as ET
import json

# .env에서 serviceKey 로드
service_key = None
with open('.env', 'r', encoding='utf-8') as f:
    for line in f:
        if 'weather_API' in line and '=' in line:
            service_key = line.split('=')[1].strip().split('#')[0].strip()
            if service_key:
                break

BASE_URL = 'http://apis.data.go.kr/1390802/AgriWeather/WeatherObsrInfo/V3/GnrlWeather'
test_point_code = '336812A001'

print("="*100)
print("농업기상 API 전수 조사 - XML 응답 파싱")
print("="*100)
print()

results = {}

# ============================================================================
# API 3: getWeatherMonDayList3 (월별 일 단위) - 가장 가능성 높음
# ============================================================================

print("API: getWeatherMonDayList3 (월별 일 기본 관측데이터)")
print("-" * 100)

endpoint = f"{BASE_URL}/getWeatherMonDayList3"
params = {
    'serviceKey': service_key,
    'Page_No': '1',
    'Page_Size': '31',
    'search_Year': '2025',
    'search_Month': '01',
    'obsr_Spot_Cd': test_point_code
}

try:
    response = requests.get(endpoint, params=params, timeout=10)
    print(f"상태 코드: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}\n")

    # XML 파싱
    root = ET.fromstring(response.content)

    # 결과 코드
    result_code = root.findtext('header/result_Code')
    result_msg = root.findtext('header/result_Msg')

    print(f"✅ XML 파싱 성공")
    print(f"  결과 코드: {result_code} ({result_msg})")

    # body 확인
    body = root.find('body')
    if body is not None:
        items_elem = body.find('items')
        if items_elem is not None:
            items = items_elem.findall('item')
            print(f"  항목 수: {len(items)}")

            if items:
                first_item = items[0]
                # 모든 필드 출력
                print(f"\n  첫 항목의 필드들:")
                for child in first_item:
                    text = child.text if child.text else "None"
                    print(f"    {child.tag}: {text}")

                # sun_Time 필드 확인
                sun_times = []
                for item in items:
                    sun_time_elem = item.find('sun_Time')
                    if sun_time_elem is not None and sun_time_elem.text:
                        sun_times.append((item.findtext('date'), sun_time_elem.text))

                if sun_times:
                    print(f"\n  ✅ sun_Time 필드 발견!")
                    print(f"     값 있는 항목: {len(sun_times)}/{len(items)}")
                    print(f"     샘플 (날짜, 일조시간):")
                    for date, sun_time in sun_times[:5]:
                        print(f"       {date}: {sun_time}시간")
                else:
                    print(f"\n  ❌ sun_Time 필드 없거나 값 없음")

                results['getWeatherMonDayList3'] = {
                    'status': 'success',
                    'items': len(items),
                    'has_sun_time': len(sun_times) > 0,
                    'sun_time_count': len(sun_times)
                }

        else:
            print("  ❌ items 요소 없음")
    else:
        print("  ❌ body 요소 없음")

except ET.ParseError as e:
    print(f"❌ XML 파싱 오류: {e}")
except Exception as e:
    print(f"❌ 오류: {e}")

# ============================================================================
# API 4: getWeatherYearDayList3 (연도별 일 단위)
# ============================================================================

print("\n" + "="*100)
print("API: getWeatherYearDayList3 (연도별 일 기본 관측데이터)")
print("-" * 100)

endpoint = f"{BASE_URL}/getWeatherYearDayList3"
params = {
    'serviceKey': service_key,
    'Page_No': '1',
    'Page_Size': '100',
    'search_Year': '2025',
    'obsr_Spot_Cd': test_point_code
}

try:
    response = requests.get(endpoint, params=params, timeout=10)

    root = ET.fromstring(response.content)
    result_code = root.findtext('header/result_Code')
    result_msg = root.findtext('header/result_Msg')

    print(f"✅ XML 파싱 성공")
    print(f"  결과 코드: {result_code} ({result_msg})")

    body = root.find('body')
    if body is not None:
        items_elem = body.find('items')
        if items_elem is not None:
            items = items_elem.findall('item')
            print(f"  항목 수: {len(items)}")

            if items:
                # sun_Time 필드 확인
                sun_times = []
                for item in items:
                    sun_time_elem = item.find('sun_Time')
                    if sun_time_elem is not None and sun_time_elem.text:
                        sun_times.append((item.findtext('date'), sun_time_elem.text))

                if sun_times:
                    print(f"\n  ✅ sun_Time 필드 발견!")
                    print(f"     값 있는 항목: {len(sun_times)}/{len(items)}")
                    print(f"     샘플 (날짜, 일조시간):")
                    for date, sun_time in sun_times[:10]:
                        print(f"       {date}: {sun_time}시간")

                    # 통계
                    try:
                        sun_time_values = [float(st) for _, st in sun_times]
                        avg_sun_time = sum(sun_time_values) / len(sun_time_values)
                        print(f"     평균: {avg_sun_time:.1f}시간")
                    except:
                        pass
                else:
                    print(f"\n  ❌ sun_Time 필드 없거나 값 없음")

                results['getWeatherYearDayList3'] = {
                    'status': 'success',
                    'items': len(items),
                    'has_sun_time': len(sun_times) > 0,
                    'sun_time_count': len(sun_times)
                }

except Exception as e:
    print(f"❌ 오류: {e}")

# ============================================================================
# API 5: getWeatherYearMonList3 (연도별 월 단위) - 평년치 계산에 가장 중요
# ============================================================================

print("\n" + "="*100)
print("API: getWeatherYearMonList3 (연도별 월 기본 관측데이터) ⭐ 평년치 계산 용")
print("-" * 100)

endpoint = f"{BASE_URL}/getWeatherYearMonList3"
params = {
    'serviceKey': service_key,
    'Page_No': '1',
    'Page_Size': '12',
    'search_Year': '2025',
    'obsr_Spot_Cd': test_point_code
}

try:
    response = requests.get(endpoint, params=params, timeout=10)

    root = ET.fromstring(response.content)
    result_code = root.findtext('header/result_Code')
    result_msg = root.findtext('header/result_Msg')

    print(f"✅ XML 파싱 성공")
    print(f"  결과 코드: {result_code} ({result_msg})")

    body = root.find('body')
    if body is not None:
        items_elem = body.find('items')
        if items_elem is not None:
            items = items_elem.findall('item')
            print(f"  항목 수: {len(items)} (12개월 기대)")

            if items:
                # 첫 항목의 필드 확인
                print(f"\n  첫 항목의 필드들:")
                first_item = items[0]
                for child in first_item:
                    text = child.text if child.text else "None"
                    print(f"    {child.tag}: {text}")

                # sun_Time 필드 확인
                print(f"\n  월별 sun_Time 데이터:")
                sun_times = []
                for item in items:
                    month = item.findtext('month', '?')
                    sun_time_elem = item.find('sun_Time')
                    if sun_time_elem is not None:
                        sun_time = sun_time_elem.text
                        if sun_time:
                            print(f"    월 {month}: {sun_time}시간")
                            sun_times.append((int(month), float(sun_time)))
                        else:
                            print(f"    월 {month}: (값 없음)")

                if sun_times:
                    print(f"\n  ✅ sun_Time 필드 발견! ({len(sun_times)}개월)")
                    avg_sun_time = sum(st for _, st in sun_times) / len(sun_times)
                    print(f"     연평균: {avg_sun_time:.1f}시간")
                    print(f"\n  💡 이것이 바로 우리가 필요한 데이터!")
                    print(f"     WeatherClimatology.sunlight_normal = 월별 일조시간 (예: 1월 160시간)")
                else:
                    print(f"\n  ❌ sun_Time 필드 없거나 값 없음")

                results['getWeatherYearMonList3'] = {
                    'status': 'success',
                    'items': len(items),
                    'has_sun_time': len(sun_times) > 0,
                    'sun_time_count': len(sun_times),
                    'is_monthly': True
                }

except Exception as e:
    print(f"❌ 오류: {e}")

# ============================================================================
# 최종 요약
# ============================================================================

print("\n" + "="*100)
print("🎯 결론")
print("="*100)

successful = {k: v for k, v in results.items() if v.get('status') == 'success'}

if successful:
    print(f"\n✅ 데이터를 제공하는 API 발견!")
    for api, result in successful.items():
        print(f"  ✅ {api}")
        if result.get('has_sun_time'):
            print(f"     └─ sun_Time 필드 있음 ({result.get('sun_time_count')}개 항목)")
            if result.get('is_monthly'):
                print(f"     └─ ⭐ 이것이 평년치 계산에 필요한 데이터!")
else:
    print("\n⚠️  현재 테스트 지점에서 sun_Time 데이터를 찾을 수 없음")
    print("가능한 원인:")
    print("  1. 지점 자체가 일조시간 데이터를 측정하지 않는 지점")
    print("  2. 연도/월 파라미터 문제")

with open('docs/data/api_xml_test.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\n📁 결과 저장: docs/data/api_xml_test.json")
