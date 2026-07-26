#!/usr/bin/env python3
"""
농업기상 API 전수 조사 - 모든 엔드포인트 테스트

목표: 일조시간(sun_Time) 데이터를 제공하는 엔드포인트 찾기
"""
import requests
import json
from datetime import datetime, timedelta

# .env에서 serviceKey 로드
service_key = None
with open('.env', 'r', encoding='utf-8') as f:
    for line in f:
        if 'weather_API' in line and '=' in line:
            service_key = line.split('=')[1].strip().split('#')[0].strip()
            if service_key:
                break

if service_key is None:
    print("❌ serviceKey 찾을 수 없음")
    exit(1)

print("="*100)
print("농업기상 API 전수 조사 - 모든 엔드포인트 테스트")
print("="*100)
print(f"\n✅ serviceKey 로드 성공\n")

# Base URL
BASE_URL = 'http://apis.data.go.kr/1390802/AgriWeather/WeatherObsrInfo/V3/GnrlWeather'

# 테스트 지점
test_point_code = '336812A001'  # 아산시 염치읍
test_region_code = '3'           # 충청남도
test_month = '01'
test_year = '2025'

# 날짜
begin_date = '20250101'
end_date = '20250131'

results = {}

# ============================================================================
# API 1: getWeatherTenMinList3 (10분 단위)
# ============================================================================

print("="*100)
print("API 1: getWeatherTenMinList3 (10분 기본 관측데이터)")
print("="*100)

endpoint = f"{BASE_URL}/getWeatherTenMinList3"
params = {
    'serviceKey': service_key,
    'Page_No': '1',
    'Page_Size': '10',
    'date': '20250115',
    'time': '1200',
    'obsr_Spot_Cd': test_point_code
}

try:
    response = requests.get(endpoint, params=params, timeout=10)
    data = response.json()
    result_code = data.get('resultCode')

    print(f"상태: {result_code} ({data.get('resultMsg', 'N/A')})")

    if result_code == '00':
        items = data.get('response', {}).get('body', {}).get('items', [])
        if items:
            first = items[0]
            has_sun = 'sun_Time' in first
            print(f"✅ 데이터 반환: {len(items)}개 항목")
            print(f"   sun_Time 필드: {'✅ 있음' if has_sun else '❌ 없음'}")
            print(f"   필드 수: {len(first)}")
            if has_sun:
                print(f"   sun_Time 샘플: {first.get('sun_Time')}")
        else:
            print("❌ 데이터 항목 없음")
    else:
        print(f"⚠️  오류: {data.get('resultMsg')}")

    results['getWeatherTenMinList3'] = {
        'code': result_code,
        'status': data.get('resultMsg')
    }
except Exception as e:
    print(f"❌ 오류: {e}")
    results['getWeatherTenMinList3'] = {'error': str(e)}

# ============================================================================
# API 2: getWeatherTimeList3 (시간 단위)
# ============================================================================

print("\n" + "="*100)
print("API 2: getWeatherTimeList3 (시간 기본 관측데이터)")
print("="*100)

endpoint = f"{BASE_URL}/getWeatherTimeList3"
params = {
    'serviceKey': service_key,
    'Page_No': '1',
    'Page_Size': '24',
    'date_Time': '20250115',
    'obsr_Spot_Cd': test_point_code
}

try:
    response = requests.get(endpoint, params=params, timeout=10)
    data = response.json()
    result_code = data.get('resultCode')

    print(f"상태: {result_code} ({data.get('resultMsg', 'N/A')})")

    if result_code == '00':
        items = data.get('response', {}).get('body', {}).get('items', [])
        if items:
            first = items[0]
            has_sun = 'sun_Time' in first
            print(f"✅ 데이터 반환: {len(items)}개 항목")
            print(f"   sun_Time 필드: {'✅ 있음' if has_sun else '❌ 없음'}")
            if has_sun:
                print(f"   sun_Time 샘플: {first.get('sun_Time')}")
        else:
            print("❌ 데이터 항목 없음")
    else:
        print(f"⚠️  오류: {data.get('resultMsg')}")

    results['getWeatherTimeList3'] = {
        'code': result_code,
        'status': data.get('resultMsg')
    }
except Exception as e:
    print(f"❌ 오류: {e}")
    results['getWeatherTimeList3'] = {'error': str(e)}

# ============================================================================
# API 3: getWeatherMonDayList3 (월별 일 단위)
# ============================================================================

print("\n" + "="*100)
print("API 3: getWeatherMonDayList3 (월별 일 기본 관측데이터)")
print("="*100)

endpoint = f"{BASE_URL}/getWeatherMonDayList3"
params = {
    'serviceKey': service_key,
    'Page_No': '1',
    'Page_Size': '31',
    'search_Year': test_year,
    'search_Month': test_month,
    'obsr_Spot_Cd': test_point_code
}

try:
    response = requests.get(endpoint, params=params, timeout=10)
    data = response.json()
    result_code = data.get('resultCode')

    print(f"상태: {result_code} ({data.get('resultMsg', 'N/A')})")

    if result_code == '00':
        items = data.get('response', {}).get('body', {}).get('items', [])
        if items:
            first = items[0]
            has_sun = 'sun_Time' in first
            print(f"✅ 데이터 반환: {len(items)}개 항목")
            print(f"   sun_Time 필드: {'✅ 있음' if has_sun else '❌ 없음'}")
            print(f"   필드 목록: {list(first.keys())[:10]}")
            if has_sun:
                sun_values = [item.get('sun_Time') for item in items if item.get('sun_Time') is not None]
                print(f"   sun_Time 값 있는 항목: {len(sun_values)}/{len(items)}")
                if sun_values:
                    print(f"   sun_Time 샘플: {sun_values[:3]}")
        else:
            print("❌ 데이터 항목 없음")
    else:
        print(f"⚠️  오류: {data.get('resultMsg')}")

    results['getWeatherMonDayList3'] = {
        'code': result_code,
        'status': data.get('resultMsg')
    }
except Exception as e:
    print(f"❌ 오류: {e}")
    results['getWeatherMonDayList3'] = {'error': str(e)}

# ============================================================================
# API 4: getWeatherYearDayList3 (연도별 일 단위)
# ============================================================================

print("\n" + "="*100)
print("API 4: getWeatherYearDayList3 (연도별 일 기본 관측데이터)")
print("="*100)

endpoint = f"{BASE_URL}/getWeatherYearDayList3"
params = {
    'serviceKey': service_key,
    'Page_No': '1',
    'Page_Size': '100',
    'search_Year': test_year,
    'obsr_Spot_Cd': test_point_code
}

try:
    response = requests.get(endpoint, params=params, timeout=10)
    data = response.json()
    result_code = data.get('resultCode')

    print(f"상태: {result_code} ({data.get('resultMsg', 'N/A')})")

    if result_code == '00':
        items = data.get('response', {}).get('body', {}).get('items', [])
        if items:
            first = items[0]
            has_sun = 'sun_Time' in first
            print(f"✅ 데이터 반환: {len(items)}개 항목")
            print(f"   sun_Time 필드: {'✅ 있음' if has_sun else '❌ 없음'}")
            if has_sun:
                sun_values = [item.get('sun_Time') for item in items if item.get('sun_Time') is not None]
                print(f"   sun_Time 값 있는 항목: {len(sun_values)}/{len(items)}")
                if sun_values:
                    print(f"   sun_Time 샘플: {sun_values[:3]}")
                    print(f"   sun_Time 평균: {sum(sun_values)/len(sun_values):.1f}")
        else:
            print("❌ 데이터 항목 없음")
    else:
        print(f"⚠️  오류: {data.get('resultMsg')}")

    results['getWeatherYearDayList3'] = {
        'code': result_code,
        'status': data.get('resultMsg')
    }
except Exception as e:
    print(f"❌ 오류: {e}")
    results['getWeatherYearDayList3'] = {'error': str(e)}

# ============================================================================
# API 5: getWeatherYearMonList3 (연도별 월 단위)
# ============================================================================

print("\n" + "="*100)
print("API 5: getWeatherYearMonList3 (연도별 월 기본 관측데이터)")
print("="*100)

endpoint = f"{BASE_URL}/getWeatherYearMonList3"
params = {
    'serviceKey': service_key,
    'Page_No': '1',
    'Page_Size': '12',
    'search_Year': test_year,
    'obsr_Spot_Cd': test_point_code
}

try:
    response = requests.get(endpoint, params=params, timeout=10)
    data = response.json()
    result_code = data.get('resultCode')

    print(f"상태: {result_code} ({data.get('resultMsg', 'N/A')})")

    if result_code == '00':
        items = data.get('response', {}).get('body', {}).get('items', [])
        if items:
            first = items[0]
            has_sun = 'sun_Time' in first
            print(f"✅ 데이터 반환: {len(items)}개 항목 (12개월)")
            print(f"   sun_Time 필드: {'✅ 있음' if has_sun else '❌ 없음'}")
            print(f"   필드 목록: {list(first.keys())}")
            if has_sun:
                sun_values = [item.get('sun_Time') for item in items if item.get('sun_Time') is not None]
                print(f"   sun_Time 값 있는 항목: {len(sun_values)}/{len(items)}")
                if sun_values:
                    print(f"   sun_Time 샘플 (월별): {sun_values}")
        else:
            print("❌ 데이터 항목 없음")
    else:
        print(f"⚠️  오류: {data.get('resultMsg')}")

    results['getWeatherYearMonList3'] = {
        'code': result_code,
        'status': data.get('resultMsg')
    }
except Exception as e:
    print(f"❌ 오류: {e}")
    results['getWeatherYearMonList3'] = {'error': str(e)}

# ============================================================================
# API 6: getWeatherTermDayList3 (기간별 일 단위) - 이전 실패한 것
# ============================================================================

print("\n" + "="*100)
print("API 6: getWeatherTermDayList3 (기간별 일 기본 관측데이터) - 이전 실패")
print("="*100)

endpoint = f"{BASE_URL}/getWeatherTermDayList3"

# 여러 조합 시도
test_cases = [
    {
        'name': '2025년 1월 (begin/end 사용)',
        'params': {
            'serviceKey': service_key,
            'Page_No': '1',
            'Page_Size': '31',
            'begin_Date': '20250101',
            'end_Date': '20250131',
            'obsr_Spot_Cd': test_point_code
        }
    },
    {
        'name': '2024년 1월 (작년)',
        'params': {
            'serviceKey': service_key,
            'Page_No': '1',
            'Page_Size': '31',
            'begin_Date': '20240101',
            'end_Date': '20240131',
            'obsr_Spot_Cd': test_point_code
        }
    }
]

for test_case in test_cases:
    print(f"\n테스트: {test_case['name']}")
    try:
        response = requests.get(endpoint, params=test_case['params'], timeout=10)
        data = response.json()
        result_code = data.get('resultCode')

        print(f"  상태: {result_code} ({data.get('resultMsg', 'N/A')})")

        if result_code == '00':
            items = data.get('response', {}).get('body', {}).get('items', [])
            if items:
                print(f"  ✅ 데이터: {len(items)}개 항목")
            else:
                print("  ⚠️  데이터 항목 없음 (resultCode 00이지만 items 빔)")
    except Exception as e:
        print(f"  ❌ 오류: {e}")

# ============================================================================
# 최종 요약
# ============================================================================

print("\n" + "="*100)
print("📊 최종 요약")
print("="*100)

print("\n✅ 성공한 API:")
for api, result in results.items():
    if result.get('code') == '00':
        print(f"  ✅ {api}")

print("\n❌ 실패한 API:")
for api, result in results.items():
    if result.get('code') != '00':
        print(f"  ❌ {api}: {result.get('status', result.get('error', 'Unknown'))}")

print("\n" + "="*100)
print("🎯 결론")
print("="*100)

success_apis = [api for api, result in results.items() if result.get('code') == '00']

if success_apis:
    print(f"\n✅ 데이터를 반환하는 API: {', '.join(success_apis)}")
    print("\n다음 단계: 이 API들에서 sun_Time 필드 존재 및 값 보유 여부 상세 확인")
else:
    print("\n⚠️  현재 테스트한 API들이 데이터를 반환하지 않음")
    print("가능한 원인:")
    print("  1. 관측지점 코드 오류")
    print("  2. 지점별로 데이터를 제공하지 않는 API")
    print("  3. 파라미터 형식 문제")

# 결과 저장
with open('docs/data/api_comprehensive_test.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\n📁 결과 저장: docs/data/api_comprehensive_test.json")
