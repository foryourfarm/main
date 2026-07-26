#!/usr/bin/env python3
"""
ASOS API (kma_sfcdd3.php)로 일조시간 데이터 직접 확인
Sunlight-Calculation_API-Guide.md 참고 (105개 ASOS 지점)
"""
import requests
from datetime import datetime, timedelta

# .env에서 authKey 로드
auth_key = None
with open('.env', 'r', encoding='utf-8') as f:
    for line in f:
        if 'weather_data_APIkey' in line and '=' in line:
            auth_key = line.split('=')[1].strip().split('#')[0].strip()
            if auth_key:
                break

if auth_key is None:
    print("❌ .env에서 weather_data_APIkey를 찾을 수 없습니다")
    exit(1)

print(f"✅ authKey 로드 성공 (앞 20자): {auth_key[:20]}...")
print("\n" + "="*70)
print("ASOS API 테스트 (kma_sfcdd3.php)")
print("="*70)

# 테스트 지점들
test_points = [
    ('108', '서울'),
    ('131', '인천'),
    ('143', '파주'),
    ('201', '춘천'),
    ('202', '강릉'),
    ('226', '태백'),
]

# 기간
tm1 = (datetime.now() - timedelta(days=10)).strftime('%Y%m%d')
tm2 = datetime.now().strftime('%Y%m%d')

print(f"\n기간: {tm1} ~ {tm2}")
print(f"API: https://apihub.kma.go.kr/api/typ01/url/kma_sfcdd3.php")
print("\n테스트 결과:")
print("-" * 70)

for point_code, point_name in test_points:
    url = 'https://apihub.kma.go.kr/api/typ01/url/kma_sfcdd3.php'

    params = {
        'tm1': tm1,
        'tm2': tm2,
        'stn': point_code,
        'help': '1',
        'authKey': auth_key
    }

    try:
        response = requests.get(url, params=params, timeout=10)

        # CSV 응답이므로 텍스트로 처리
        lines = response.text.strip().split('\n')

        if len(lines) > 1:
            # 첫 줄은 도움말, 두 번째 줄은 필드명
            header_line = lines[1]
            fields = header_line.split('|') if '|' in header_line else header_line.split(',')

            # SS_DAY (일조합) 필드 검색
            has_ss_day = 'SS_DAY' in header_line

            # 데이터 행 확인
            data_rows = len(lines) - 2  # 도움말, 필드명 제외

            status = "✅" if has_ss_day else "❌"
            print(f"{status} {point_name:10s} ({point_code}): {data_rows} 행, SS_DAY: {has_ss_day}")

            # 첫 데이터 행 샘플 출력
            if len(lines) > 2:
                first_data = lines[2][:80]
                print(f"   샘플: {first_data}...")

        else:
            print(f"❌ {point_name:10s} ({point_code}): 데이터 없음")

    except Exception as e:
        print(f"❌ {point_name:10s} ({point_code}): {str(e)[:50]}")

print("\n" + "="*70)
print("✅ ASOS 테스트 완료")
print("="*70)

print("\n📊 분석:")
print("- ASOS (105개 지점): 전국 일부 커버 가능")
print("- 농업기상 API (218개 지점): 일조시간 미제공 (현재까지 확인)")
print("- ASOS → 전국 커버 기대 불가")
print("\n결론: Angstrom 공식 기반 계산 필수")
