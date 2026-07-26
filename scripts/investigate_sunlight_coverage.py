#!/usr/bin/env python3
"""
농업기상 API를 이용한 일조시간 데이터 커버 범위 조사 (XML 파싱)

Phase A: 관측지점 목록 조회 (218개)
Phase B: 샘플 지점 일조시간 데이터 확인
Phase C: 커버 범위 분석
"""
import requests
import xml.etree.ElementTree as ET
import json
from datetime import datetime, timedelta
from collections import defaultdict

# .env 파일에서 serviceKey 로드
service_key = None
with open('.env', 'r', encoding='utf-8') as f:
    for line in f:
        if 'weather_API' in line and '=' in line:
            service_key = line.split('=')[1].strip().split('#')[0].strip()
            if service_key:
                break

if service_key is None:
    print("❌ .env에서 weather_API를 찾을 수 없습니다")
    exit(1)

print(f"✅ serviceKey 로드 성공 (앞 20자): {service_key[:20]}...")

# ============================================================================
# Phase A: 관측지점 목록 조회
# ============================================================================

print("\n" + "="*70)
print("Phase A: 관측지점 목록 조회")
print("="*70)

def get_all_observation_spots():
    """모든 관측지점 조회 (페이지네이션, XML 파싱)"""
    url = 'http://apis.data.go.kr/1390802/AgriWeather/getObsrSpotList'
    all_spots = []
    page_no = 1
    page_size = 100

    while True:
        params = {
            'serviceKey': service_key,
            'Page_No': str(page_no),
            'Page_Size': str(page_size)
        }

        try:
            response = requests.get(url, params=params, timeout=10)

            # XML 파싱
            root = ET.fromstring(response.content)

            # XML 네임스페이스 처리 (없음)
            items_elem = root.find('body/items')
            if items_elem is None:
                print(f"❌ API 응답에서 items을 찾을 수 없습니다")
                break

            items = items_elem.findall('item')

            if not items:
                print(f"✅ 관측지점 조회 완료: 총 {len(all_spots)}개")
                break

            for item in items:
                spot_code = item.findtext('Obsr_Spot_Code')
                spot_name = item.findtext('Obsr_Spot_Nm')
                do_se_name = item.findtext('Do_Se_Nm', 'Unknown')

                if spot_code and spot_name:
                    all_spots.append({
                        'code': spot_code,
                        'name': spot_name,
                        'region': do_se_name
                    })

            print(f"  페이지 {page_no}: {len(items)}개 지점 조회 (누계: {len(all_spots)}개)")
            page_no += 1

        except ET.ParseError as e:
            print(f"❌ XML 파싱 오류 (페이지 {page_no}): {e}")
            break
        except Exception as e:
            print(f"❌ 페이지 {page_no} 조회 오류: {e}")
            break

    return all_spots

observation_spots = get_all_observation_spots()
print(f"\n📊 총 {len(observation_spots)}개 관측지점 확인")

# ============================================================================
# Phase B: 일조시간 데이터 보유 확인
# ============================================================================

print("\n" + "="*70)
print("Phase B: 일조시간 데이터 보유 확인 (샘플)")
print("="*70)

def check_sunlight_data(spot_code):
    """특정 지점의 일조시간 데이터 확인"""
    url = 'http://apis.data.go.kr/1390802/AgriWeather/WeatherObsrInfo/V3/GnrlWeather/getWeatherTermDayList3'

    # 최근 30일 조회
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')

    params = {
        'serviceKey': service_key,
        'Page_No': '1',
        'Page_Size': '31',
        'begin_Date': start_date,
        'end_Date': end_date,
        'obsr_Spot_Cd': spot_code
    }

    try:
        response = requests.get(url, params=params, timeout=10)

        # JSON 응답이어야 함
        data = response.json()
        result_code = data.get('resultCode')

        if result_code == '00':  # 성공
            body = data.get('response', {}).get('body', {})
            items = body.get('items', [])

            if items:
                first_item = items[0]
                has_sunlight = 'sun_Time' in first_item and first_item['sun_Time'] is not None

                return {
                    'status': 'data_exists',
                    'has_sunlight': has_sunlight,
                    'days_count': len(items),
                    'fields': list(first_item.keys()) if first_item else []
                }
            else:
                return {
                    'status': 'no_data',
                    'has_sunlight': False,
                    'days_count': 0
                }

        elif result_code == '01':
            return {'status': 'not_provided', 'has_sunlight': False}
        else:
            return {'status': f'error_{result_code}', 'has_sunlight': False}

    except Exception as e:
        return {'status': f'exception', 'error': str(e)[:50]}

# 샘플 지점 선택
if len(observation_spots) > 0:
    # 고르게 분포된 샘플 선택
    sample_indices = [i * len(observation_spots) // 15 for i in range(15)]
    sample_spots = [observation_spots[i] for i in sample_indices if i < len(observation_spots)]

    sunlight_available = 0
    sunlight_missing = 0

    print(f"\n샘플 지점 {len(sample_spots)}개 테스트:")
    print("-" * 80)
    print(f"{'지역':<15} {'지점명':<25} {'상태':<15} {'일조':<10}")
    print("-" * 80)

    for spot in sample_spots:
        spot_code = spot['code']
        spot_name = spot['name']
        region = spot['region']

        result = check_sunlight_data(spot_code)
        status = result.get('status', 'unknown')
        has_sunlight = result.get('has_sunlight', False)

        if has_sunlight:
            sunlight_available += 1
            mark = "✅"
        else:
            sunlight_missing += 1
            mark = "❌"

        print(f"{region:<15} {spot_name:<25} {status:<15} {mark}")

    print("-" * 80)
    total_sample = len(sample_spots)
    coverage_sample = 100 * sunlight_available / total_sample if total_sample > 0 else 0

    print(f"\n📊 샘플 결과 ({total_sample}개 지점):")
    print(f"  일조 있음: {sunlight_available}개 ({coverage_sample:.1f}%)")
    print(f"  일조 없음: {sunlight_missing}개")

# ============================================================================
# Phase C: 모든 지점 확인 (전체 커버 범위 분석)
# ============================================================================

print("\n" + "="*70)
print("Phase C: 전체 커버 범위 분석 (모든 218개 지점)")
print("="*70)

region_stats = defaultdict(lambda: {'total': 0, 'with_sunlight': 0})
total_with_sunlight = 0
checked_count = 0

print(f"\n진행 중입니다. (총 {len(observation_spots)}개 지점)...")

for idx, spot in enumerate(observation_spots):
    spot_code = spot['code']
    region = spot['region']

    result = check_sunlight_data(spot_code)
    has_sunlight = result.get('has_sunlight', False)

    region_stats[region]['total'] += 1
    if has_sunlight:
        region_stats[region]['with_sunlight'] += 1
        total_with_sunlight += 1

    checked_count += 1
    if (idx + 1) % 20 == 0:
        print(f"  진행률: {idx+1}/{len(observation_spots)}")

# ============================================================================
# 결과 출력
# ============================================================================

print("\n" + "="*70)
print("📊 최종 결과")
print("="*70)

print(f"\n{'지역':<20} {'총 지점':<10} {'일조 있음':<10} {'커버율':<10}")
print("-" * 50)

total_points = 0
for region in sorted(region_stats.keys()):
    stats = region_stats[region]
    total = stats['total']
    with_sunlight = stats['with_sunlight']
    coverage = 100 * with_sunlight / total if total > 0 else 0

    total_points += total

    coverage_mark = "✅" if coverage >= 80 else "⚠️" if coverage >= 50 else "❌"
    print(f"{region:<20} {total:<10} {with_sunlight:<10} {coverage_mark} {coverage:>6.1f}%")

overall_coverage = 100 * total_with_sunlight / total_points if total_points > 0 else 0

print("-" * 50)
print(f"{'합계':<20} {total_points:<10} {total_with_sunlight:<10} {overall_coverage:>6.1f}%")

# ============================================================================
# 권장 처리 방안
# ============================================================================

print("\n" + "="*70)
print("🎯 권장 처리 방안")
print("="*70)

if overall_coverage >= 80:
    recommendation = "높은 커버율 (≥80%) → 하이브리드 (실측 우선)"
elif overall_coverage >= 50:
    recommendation = "중간 커버율 (50~80%) → 하이브리드 (실측 + 계산)"
else:
    recommendation = "낮은 커버율 (<50%) → 계산값 우선 (Angstrom)"

print(f"\n{recommendation}")

print(f"\n상세 권장사항:")
if overall_coverage >= 50:
    print("✅ 1. 실측 데이터 가용 지역: API에서 직접 조회")
    print("✅ 2. 미실측 지역: Angstrom 공식으로 계산")
    print("✅ 3. UI에서 출처 명시: '실측' vs '계산'")
else:
    print("✅ 1. 모든 지역에 Angstrom 공식 적용")
    print("✅ 2. 실측값 있는 극소수 지역만 우선 사용")
    print("✅ 3. 향후 계산 모델 고도화 검토")

print("\n" + "="*70)
print(f"✅ 조사 완료 (총 {checked_count}개 지점 확인)")
print("="*70)

# 결과 저장
output = {
    'timestamp': datetime.now().isoformat(),
    'total_observation_spots': len(observation_spots),
    'total_checked': checked_count,
    'total_with_sunlight': total_with_sunlight,
    'total_without_sunlight': total_points - total_with_sunlight,
    'overall_coverage_percent': round(overall_coverage, 1),
    'recommendation': recommendation,
    'region_stats': {
        region: {
            'total': stats['total'],
            'with_sunlight': stats['with_sunlight'],
            'coverage_percent': round(100 * stats['with_sunlight'] / stats['total'], 1) if stats['total'] > 0 else 0
        }
        for region, stats in sorted(region_stats.items())
    }
}

output_file = 'docs/data/sunlight_coverage_result.json'
try:
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n📁 결과 저장: {output_file}")
except Exception as e:
    print(f"\n❌ 결과 저장 오류: {e}")
