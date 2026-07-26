#!/usr/bin/env python3
"""농업기상 API 테스트 - 관측지점 목록 조회"""
import requests
import json

# .env에서 serviceKey 로드
service_key = None
with open('.env', 'r', encoding='utf-8') as f:
    for line in f:
        if 'weather_API' in line and '=' in line:
            service_key = line.split('=')[1].strip().split('#')[0].strip()
            if service_key:
                break

print(f"serviceKey (앞 20자): {service_key[:20]}...\n")

# API 호출
url = 'http://apis.data.go.kr/1390802/AgriWeather/getObsrSpotList'
params = {
    'serviceKey': service_key,
    'Page_No': '1',
    'Page_Size': '5'
}

print(f"URL: {url}")
print(f"Params: {params}\n")

response = requests.get(url, params=params)
print(f"Status Code: {response.status_code}")
print(f"Response Text (처음 500자):\n{response.text[:500]}\n")

# JSON 파싱 시도
try:
    data = response.json()
    print("✅ JSON 파싱 성공")
    print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
except Exception as e:
    print(f"❌ JSON 파싱 실패: {e}")
    print(f"Response headers: {dict(response.headers)}")
