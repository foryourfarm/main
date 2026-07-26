# 일조시간 데이터 조사 계획 (2026-07-26)

> 농업기상-기본-관측데이터 API를 이용한 실제 데이터 커버 범위 조사

---

## 1. 현황 재정리

### 제공 가능한 일조시간 데이터 소스

| 소스 | 관측소 | 커버 | 상태 | 비고 |
|------|--------|------|------|------|
| **AWS (kma_sfcdd.php)** | 510개 | 전국 | ❌ 일조시간 미제공 | 온도, 강수만 |
| **ASOS (kma_sfcdd3.php)** | 105개 | 일부 | ✅ 일조시간 제공 | 전국 커버 불가 |
| **농업기상 API** | ❓ | ❓ | ⏳ **조사 중** | **이 과제** |

---

## 2. 조사 목표

**3가지를 파악:**
1. 농업기상 API의 관측지점 수
2. 각 지점의 일조시간 데이터 보유 여부
3. 256 시/군 중 몇 %를 커버하는가

---

## 3. 조사 단계

### Phase A: 관측지점 목록 조회

**목표:** 농업기상 API가 제공하는 모든 관측지점 파악

**API:** `getObsrSpotList`
```
URL: http://apis.data.go.kr/1390802/AgriWeather/getObsrSpotList
파라미터: serviceKey, Page_Size, Page_No
```

**작업:**
```python
# 1. 샘플 코드 기반으로 전체 관측지점 조회
# 2. 페이지네이션으로 모든 지점 수집
# 3. 지점별 code, name, 위도, 경도 저장
# 4. 결과: 관측지점 목록 (CSV/JSON)

예상 결과:
- 관측지점 총 수: ? 개
- 지역별 분포: {지역명: 지점수, ...}
```

---

### Phase B: 일조시간 데이터 보유 확인

**목표:** 각 관측지점에서 실제 일조시간 데이터가 있는지 확인

**API:** `getWeatherTermDayList3` (기간별 일 기본 관측데이터)
```
URL: apis.data.go.kr/.../getWeatherTermDayList3
파라미터: 
  - serviceKey
  - begin_Date, end_Date (1~365일 범위)
  - obsr_Spot_Cd (관측지점코드)
```

**작업:**
```python
# 1. Phase A에서 얻은 지점 중 샘플 선택 (20~30개)
# 2. 각 지점별로 최근 30일 데이터 조회
# 3. 응답 필드에서 'sun_Time' 또는 유사 필드 확인
# 4. 값의 존재 여부 판정

예상 결과:
- 일조시간 데이터 있음: X개 지점
- 일조시간 데이터 없음: Y개 지점
- 커버율: X / (X+Y) %
```

**샘플 코드:**
```python
import requests
from datetime import datetime, timedelta

service_key = '...'  # .env에서 로드

# 최근 30일 조회
end_date = datetime.now().strftime('%Y%m%d')
start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')

test_points = ['101', '108', '131', '201', '231']  # 샘플 지점

for point_code in test_points:
    url = 'http://apis.data.go.kr/1390802/AgriWeather/WeatherObsrInfo/V3/GnrlWeather/getWeatherTermDayList3'
    params = {
        'serviceKey': service_key,
        'Page_No': '1',
        'Page_Size': '31',
        'begin_Date': start_date,
        'end_Date': end_date,
        'obsr_Spot_Cd': point_code
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    # 응답 구조 분석
    print(f"Point {point_code}:")
    print(f"  - Response code: {data.get('resultCode')}")
    print(f"  - Item count: {len(data.get('response', {}).get('body', {}).get('items', []))}")
    
    # 첫 항목의 필드명 확인
    if data.get('response', {}).get('body', {}).get('items'):
        first_item = data['response']['body']['items'][0]
        print(f"  - Fields: {list(first_item.keys())}")
        print(f"  - sun_Time present: {'sun_Time' in first_item}")
```

---

### Phase C: 지역별 커버 범위 분석

**목표:** 256 시/군 중 얼마나 많이 커버되는지 판정

**작업:**
```python
# 1. Phase B의 결과를 지역(시/군)별로 집계
# 2. 각 시/군의 관측지점 수
# 3. 일조시간 데이터 가능 지점 수
# 4. 커버율 산출

예상 결과 예시:
┌─────────┬──────────┬──────────┬────────┐
│ 지역    │ 총 지점  │ 일조 있음 │ 커버율 │
├─────────┼──────────┼──────────┼────────┤
│ 서울    │ 3        │ 3        │ 100%   │
│ 인천    │ 2        │ 2        │ 100%   │
│ 경기    │ 25       │ 18       │ 72%    │
│ ...     │ ...      │ ...      │ ...    │
│ 합계    │ 150      │ 110      │ 73%    │
└─────────┴──────────┴──────────┴────────┘
```

---

## 4. 기대 결과 시나리오

### 시나리오 A: 높은 커버율 (≥70%)
```
✅ 대부분 지역에서 일조시간 실측 데이터 가용
→ 실측값 기반 처리 (신뢰도 높음)
→ 미커버 지역만 계산값 사용
```

### 시나리오 B: 중간 커버율 (30~70%)
```
⚠️ 일부 지역만 일조시간 데이터 가용
→ 하이브리드 처리 (실측 + 계산)
→ 신뢰도 명시 필수
```

### 시나리오 C: 낮은 커버율 (<30%)
```
❌ 대부분 지역에서 일조시간 미제공
→ 모든 지역에 계산값 적용 (Angstrom/운량 기반)
→ 실측값 있는 극소수 지역만 활용
```

---

## 5. 일조시간 미제공 지역의 처리 방안

### 안 1: Angstrom 공식 (추천)

```python
# 기온과 강수를 이용한 일조시간 추정
# 공식: n = n_max × (a + b × (Rs / Rso))
# 여기서:
#   n: 추정 일조시간
#   n_max: 이론 일조 가능시간 (위도 기반)
#   Rs: 실제 일사량 (또는 기온으로 근사)
#   Rso: 대기 상한 일사량
#   a, b: 경험 계수 (a≈0.25, b≈0.50)

def estimate_sunlight_angstrom(
    temp_max: float,
    temp_min: float,
    rainfall: float,
    latitude: float
) -> float:
    """
    기온과 강수 기반 일조시간 추정
    반환: 추정 일조시간 (시간)
    """
    # 이론 일조 가능시간 (위도 기반 계산)
    n_max = calculate_daylight_hours(latitude, date)
    
    # 기온 일사량 변환 (Hargreaves 방정식 간편형)
    delta_temp = temp_max - temp_min
    Rs_estimated = 0.16 * delta_temp**0.5
    
    # 대기 상한 일사량
    Rso = calculate_extraterrestrial_radiation(latitude, date)
    
    # Angstrom 공식
    a, b = 0.25, 0.50
    n = n_max * (a + b * (Rs_estimated / Rso))
    
    # 강수가 있으면 감소 (구름 기반)
    if rainfall > 0:
        n *= max(0.5, 1 - 0.1 * rainfall)  # 강수 mm당 10% 감소
    
    return max(0, min(n, n_max))  # 0 ~ n_max 범위
```

**장점:**
- ✅ 공식 기반 (학술적 근거)
- ✅ 기존 기온/강수 데이터만 필요
- ✅ 전국 모든 지역 적용 가능

**단점:**
- ❌ 근사치 (실측 아님)
- ❌ 위도/계절 단순화

---

### 안 2: 운량 기반 추정 (대안)

```python
def estimate_sunlight_from_cloud_cover(
    cloud_cover: float,  # 0~10 (1/10 단위)
    latitude: float,
    date: date
) -> float:
    """
    전운량(CA_TOT)을 이용한 일조시간 추정
    """
    n_max = calculate_daylight_hours(latitude, date)
    
    # 운량 → 운량계수 변환
    # 운량 0: 계수 1.0 (맑음)
    # 운량 10: 계수 0.1 (흐림)
    cloud_factor = 1 - 0.09 * cloud_cover
    
    n = n_max * cloud_factor
    return max(0, min(n, n_max))
```

**장점:**
- ✅ 기상청 API에서 CA_TOT 제공
- ✅ 더 정확한 근사 (구름 직접 반영)

**단점:**
- ❌ CA_TOT도 모든 지점에서 제공되는지 불명

---

### 안 3: 평년치 사용 (최후의 수단)

```python
# 평년값만 사용
sunlight_value = WeatherClimatology.sunlight_normal
신뢰도_표기 = "평년치"
```

**장점:**
- ✅ 가장 간단

**단점:**
- ❌ 실시간 변동 반영 불가
- ❌ 계절 편차 무시

---

## 6. 권장 하이브리드 전략

```python
def get_sunlight(region_id: int, date: date) -> dict:
    """
    지역 · 날짜별 일조시간 조회 (우선순위대로)
    """
    
    # 1순위: 농업기상 API 실측값
    if region_has_observation(region_id):
        actual = fetch_from_agri_weather_api(region_id, date)
        if actual is not None:
            return {
                "value": actual,
                "source": "실측 (농업기상 API)",
                "confidence": "high"
            }
    
    # 2순위: Angstrom 공식 추정
    soil_clim = get_soil_climatology(region_id, date.month)
    if soil_clim.temp_max and soil_clim.rainfall is not None:
        estimated = estimate_sunlight_angstrom(
            soil_clim.temp_max,
            soil_clim.temp_min,
            soil_clim.rainfall,
            region_latitude(region_id)
        )
        return {
            "value": estimated,
            "source": "계산값 (Angstrom 공식)",
            "confidence": "medium"
        }
    
    # 3순위: 평년치
    climatology = WeatherClimatology.query(
        region_id=region_id,
        month=date.month
    ).first()
    if climatology and climatology.sunlight_normal:
        return {
            "value": climatology.sunlight_normal,
            "source": "평년치",
            "confidence": "low"
        }
    
    # 최후: 없음
    return {
        "value": None,
        "source": "미제공",
        "confidence": None
    }
```

---

## 7. 조사 일정

| 단계 | 작업 | 예상 시간 |
|------|------|---------|
| A | 관측지점 목록 조회 + 분석 | 30분 |
| B | 샘플 지점 일조시간 테스트 | 1시간 |
| C | 지역별 커버 범위 집계 | 30분 |
| 처리방안 | 결과에 따른 전략 수립 | 30분 |

**소요 시간: 약 2.5시간**

---

## 참고 파일

- `.env`: serviceKey 보관
- `Sample-code.py`: 기본 API 호출 샘플
- `농업기상-기본-관측데이터_API기술명세서.md`: API 명세
- `backend/app/infra/public_api/weather_client.py`: 기상청 클라이언트 참고

---

**상태:** 📍 **조사 준비 완료** — 즉시 실행 가능
