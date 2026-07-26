#!/usr/bin/env python3
"""일조시간 API 응답 구조 확인"""
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

print(f"serviceKey: {service_key[:30]}...\n")

# 테스트 지점: 서울 (구례군 구례읍 대신 첫 번째 지점 사용)
test_point_code = '336812A001'  # 아산시 염치읍
test_point_name = '아산시 염치읍'

# 최근 7일 데이터 조회
end_date = datetime.now().strftime('%Y%m%d')
start_date = (datetime.now() - timedelta(days=7)).strftime('%Y%m%d')

url = 'http://apis.data.go.kr/1390802/AgriWeather/WeatherObsrInfo/V3/GnrlWeather/getWeatherTermDayList3'

params = {
    'serviceKey': service_key,
    'Page_No': '1',
    'Page_Size': '7',
    'begin_Date': start_date,
    'end_Date': end_date,
    'obsr_Spot_Cd': test_point_code
}

print(f"📌 테스트 지점: {test_point_name} ({test_point_code})")
print(f"📌 기간: {start_date} ~ {end_date}")
print(f"📌 URL: {url}\n")

try:
    response = requests.get(url, params=params, timeout=10)

    print(f"✅ Status Code: {response.status_code}")
    print(f"✅ Content-Type: {response.headers.get('Content-Type')}\n")

    data = response.json()

    print("응답 구조:")
    print(json.dumps({
        'resultCode': data.get('resultCode'),
        'resultMsg': data.get('resultMsg'),
        'response': {
            'header': data.get('response', {}).get('header'),
            'body': {
                'rcdcnt': data.get('response', {}).get('body', {}).get('rcdcnt'),
                'totalCount': data.get('response', {}).get('body', {}).get('totalCount')
            }
        }
    }, indent=2, ensure_ascii=False))

    print("\n" + "="*70)
    print("첫 번째 항목의 필드:")
    print("="*70)

    items = data.get('response', {}).get('body', {}).get('items', [])

    if items:
        first_item = items[0]
        print(f"\n필드 목록 ({len(first_item)}개):")
        for key in sorted(first_item.keys()):
            value = first_item[key]
            print(f"  {key:<30} = {value}")

        # 일조 관련 필드 확인
        print("\n일조 관련 필드 검색:")
        sunlight_fields = [k for k in first_item.keys() if 'sun' in k.lower() or 'ss' in k.lower() or 'day' in k.lower()]
        if sunlight_fields:
            print(f"  ✅ 발견: {sunlight_fields}")
        else:
            print(f"  ❌ 일조 관련 필드 없음")

    else:
        print("❌ 응답 데이터 없음")

except json.JSONDecodeError as e:
    print(f"❌ JSON 파싱 오류: {e}")
    print(f"응답 텍스트:\n{response.text[:500]}")
except Exception as e:
    print(f"❌ 오류: {e}")
