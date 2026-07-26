#!/usr/bin/env python3
"""
농업기상 API 상세 조사 (일조시간 데이터 실제 존재 확인)

전제: 농업기상 API 응답 모델에 sun_Time(일조시간)이 명시되어 있음
목표:
1. 과거 데이터로 조회하여 일조시간 필드 존재 확인
2. 218개 지점 중 일조시간 데이터 보유 지점 파악
3. 지역별 커버 범위 정확히 측정
"""
import requests
import xml.etree.ElementTree as ET
import json
from datetime import datetime, timedelta
from collections import defaultdict

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

print(f"✅ serviceKey 로드 성공\n")

# ============================================================================
# 1단계: 관측지점 목록 재조회
# ============================================================================

print("="*80)
print("Step 1: 관측지점 목록 조회 (218개)")
print("="*80)

def get_all_observation_spots():
    """모든 관측지점 조회"""
    url = 'http://apis.data.go.kr/1390802/AgriWeather/getObsrSpotList'
    all_spots = []
    page_no = 1

    while page_no <= 3:  # 최대 3페이지
        params = {
            'serviceKey': service_key,
            'Page_No': str(page_no),
            'Page_Size': '100'
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            root = ET.fromstring(response.content)
            items = root.findall('body/items/item')

            if not items:
                break

            for item in items:
                spot_code = item.findtext('Obsr_Spot_Code')
                spot_name = item.findtext('Obsr_Spot_Nm')
                do_se_code = item.findtext('Do_Se_Code')
                do_se_name = item.findtext('Do_Se_Nm', 'Unknown')

                if spot_code:
                    all_spots.append({
                        'code': spot_code,
                        'name': spot_name,
                        'region': do_se_name,
                        'region_code': do_se_code
                    })

            print(f"  페이지 {page_no}: {len(items)}개 (누계: {len(all_spots)}개)")
            page_no += 1

        except Exception as e:
            print(f"  ❌ 페이지 {page_no} 오류: {e}")
            break

    return all_spots

spots = get_all_observation_spots()
print(f"\n✅ 총 {len(spots)}개 관측지점 확인\n")

# ============================================================================
# 2단계: 과거 기간(작년)으로 일조시간 데이터 조회 테스트
# ============================================================================

print("="*80)
print("Step 2: 과거 기간(2025년) 일조시간 데이터 존재 확인")
print("="*80)

# 2025년 1월 데이터 조회 (1년 전 과거 데이터)
begin_date = '20250101'
end_date = '20250131'

def check_sunlight_data_detailed(spot_code, begin_date, end_date):
    """일조시간 데이터 상세 조회"""
    url = 'http://apis.data.go.kr/1390802/AgriWeather/WeatherObsrInfo/V3/GnrlWeather/getWeatherTermDayList3'

    params = {
        'serviceKey': service_key,
        'Page_No': '1',
        'Page_Size': '31',
        'begin_Date': begin_date,
        'end_Date': end_date,
        'obsr_Spot_Cd': spot_code
    }

    try:
        response = requests.get(url, params=params, timeout=10)

        # JSON 파싱 시도
        try:
            data = response.json()
        except:
            # XML 응답일 경우
            try:
                root = ET.fromstring(response.content)
                result_code = root.findtext('header/result_Code')
                result_msg = root.findtext('header/result_Msg')
                return {
                    'status': f'error_{result_code}',
                    'message': result_msg,
                    'has_sunlight': False
                }
            except:
                return {'status': 'parse_error', 'has_sunlight': False}

        result_code = data.get('resultCode')

        if result_code == '00':  # 성공
            items = data.get('response', {}).get('body', {}).get('items', [])

            if items:
                first_item = items[0]
                # 응답 모델 명시: sun_Time(일조시간)
                has_sunlight = 'sun_Time' in first_item

                # sun_Time이 실제 값을 가지고 있는지 확인
                sun_time_values = []
                for item in items:
                    sun_time = item.get('sun_Time')
                    if sun_time is not None:
                        sun_time_values.append(float(sun_time) if isinstance(sun_time, (int, float, str)) else 0)

                return {
                    'status': 'data_found',
                    'has_sunlight': has_sunlight,
                    'sun_time_count': len(sun_time_values),  # 일조시간 값이 있는 항목 수
                    'items_total': len(items),
                    'sun_time_values': sun_time_values[:5]  # 첫 5개 샘플
                }
            else:
                return {'status': 'no_items', 'has_sunlight': False}

        elif result_code == '301':
            return {'status': 'no_data', 'has_sunlight': False}
        else:
            return {'status': f'error_{result_code}', 'has_sunlight': False}

    except Exception as e:
        return {'status': 'exception', 'error': str(e)[:50], 'has_sunlight': False}

# 샘플 지점 30개로 테스트
print(f"\n과거 기간 테스트: {begin_date} ~ {end_date}")
print(f"샘플 지점 {min(30, len(spots))}개 조회\n")
print("-" * 100)
print(f"{'지역':<15} {'지점명':<25} {'상태':<20} {'일조':<10} {'샘플값':<20}")
print("-" * 100)

sample_indices = [i * len(spots) // 30 for i in range(min(30, len(spots)))]
sample_spots = [spots[i] for i in sample_indices if i < len(spots)]

sunlight_count = 0
test_count = 0

for spot in sample_spots:
    result = check_sunlight_data_detailed(spot['code'], begin_date, end_date)
    test_count += 1

    status = result['status']
    has_sunlight = result['has_sunlight']
    sun_time_count = result.get('sun_time_count', 0)
    items_total = result.get('items_total', 0)
    sample_values = result.get('sun_time_values', [])

    if has_sunlight and sun_time_count > 0:
        sunlight_count += 1
        mark = "✅"
    else:
        mark = "❌"

    sample_str = str(sample_values[:2]) if sample_values else "N/A"
    print(f"{spot['region']:<15} {spot['name']:<25} {status:<20} {mark} {sample_str:<20}")

print("-" * 100)
print(f"\n📊 샘플 결과 ({test_count}개 지점):")
print(f"  일조 데이터 있음: {sunlight_count}개 ({100*sunlight_count/test_count:.1f}%)")
print(f"  일조 데이터 없음: {test_count-sunlight_count}개")

# ============================================================================
# 3단계: 전체 지점 상세 조사
# ============================================================================

print("\n" + "="*80)
print("Step 3: 전체 218개 지점 상세 조사 (약 3-5분 소요)")
print("="*80)

region_stats = defaultdict(lambda: {
    'total': 0,
    'with_data': 0,
    'with_sunlight': 0,
    'error': 0
})

total_with_sunlight = 0
checked = 0

print("\n진행 중...")

for idx, spot in enumerate(spots):
    spot_code = spot['code']
    region = spot['region']

    result = check_sunlight_data_detailed(spot_code, begin_date, end_date)

    status = result['status']
    has_sunlight = result['has_sunlight']

    region_stats[region]['total'] += 1

    if status == 'data_found':
        region_stats[region]['with_data'] += 1
        if has_sunlight and result.get('sun_time_count', 0) > 0:
            region_stats[region]['with_sunlight'] += 1
            total_with_sunlight += 1
    elif 'error' in status or status == 'exception':
        region_stats[region]['error'] += 1

    checked += 1
    if (idx + 1) % 30 == 0:
        print(f"  진행률: {idx+1}/{len(spots)}")

# ============================================================================
# 최종 결과
# ============================================================================

print("\n" + "="*80)
print("📊 최종 결과 (과거 기간: 2025년 1월)")
print("="*80)

print(f"\n{'지역':<20} {'총':<6} {'데이터':<8} {'일조':<8} {'에러':<8} {'커버율':<10}")
print("-" * 60)

total_all = 0
total_data = 0
total_error = 0

for region in sorted(region_stats.keys()):
    stats = region_stats[region]
    total = stats['total']
    with_data = stats['with_data']
    with_sun = stats['with_sunlight']
    error = stats['error']

    total_all += total
    total_data += with_data
    total_error += error

    coverage = 100 * with_sun / total if total > 0 else 0
    mark = "✅" if coverage >= 50 else "⚠️" if coverage >= 20 else "❌"

    print(f"{region:<20} {total:<6} {with_data:<8} {with_sun:<8} {error:<8} {mark} {coverage:>6.1f}%")

overall_coverage = 100 * total_with_sunlight / total_all if total_all > 0 else 0

print("-" * 60)
print(f"{'합계':<20} {total_all:<6} {total_data:<8} {total_with_sunlight:<8} {total_error:<8} {overall_coverage:>6.1f}%")

print("\n" + "="*80)
print("🎯 결론")
print("="*80)

print(f"\n✅ 농업기상 API 일조시간 데이터 커버율: {overall_coverage:.1f}%")

if overall_coverage >= 70:
    print("\n📌 상황: **높은 커버율**")
    print("→ 실측 기반 하이브리드 처리 가능")
    print("→ 일조시간이 있는 지점 우선, 없는 지점은 Angstrom 계산")

elif overall_coverage >= 30:
    print("\n📌 상황: **부분 커버**")
    print("→ 혼합 처리 필요")
    print("→ 실측 + 계산 병행")
    print("→ 신뢰도 명시 필수")

else:
    print("\n📌 상황: **낮은 커버율**")
    print("→ Angstrom 계산 기반 필수")
    print("→ 실측 극소수만 활용")

# 결과 저장
output = {
    'timestamp': datetime.now().isoformat(),
    'investigation_period': f'{begin_date} ~ {end_date}',
    'total_spots': len(spots),
    'total_with_sunlight': total_with_sunlight,
    'overall_coverage_percent': round(overall_coverage, 1),
    'region_stats': {
        region: {
            'total': stats['total'],
            'with_data': stats['with_data'],
            'with_sunlight': stats['with_sunlight'],
            'error': stats['error'],
            'coverage_percent': round(100 * stats['with_sunlight'] / stats['total'], 1) if stats['total'] > 0 else 0
        }
        for region, stats in sorted(region_stats.items())
    }
}

output_file = 'docs/data/sunlight_detailed_investigation.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"\n📁 상세 결과 저장: {output_file}")
