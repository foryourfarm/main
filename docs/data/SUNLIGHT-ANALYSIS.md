# 일조시간(Sunlight) 데이터 현황 분석 (2026-07-26)

> 목적: 현재 로직의 일조시간 필수성 확인 → 가용 API 조사 → 전국 커버 여부 판정 → 처리 방안 수립

---

## 1. 현재 로직에서 일조시간의 역할

### 1.1 적합도 계산에서의 위치

**파일:** `backend/app/services/suitability_service.py`

| 항목 | 내용 | 필수도 |
|------|------|--------|
| INDICATOR_SOURCE_FIELDS (라인 51) | `"sunlight": "sunlight_normal"` | ✅ 지표로 등록 |
| WEATHER_INDICATORS (라인 195) | 기상 판정 지표 포함 | ✅ 포함 |
| gather_indicator_values() (라인 184) | `WeatherClimatology.sunlight_normal` | ✅ 필수 |
| calculate_suitability() | 지표값으로 점수 계산 | ✅ 가중치 적용 |

### 1.2 결론

**현재 로직은 일조시간이 필수 지표로 정의됨:**
- 월별 적합도 계산에서 일조시간은 필수 입력 지표
- 없으면 `gather_indicator_values()`에서 `None`으로 채워짐
- `None` 값은 `calculate_suitability()`에서 제외됨 (점수 가중도 감소)
- 모든 기상 지표가 결측이면 해당 월은 "dormant" 상태로 점수 비표시

**온전함 정도:**
- ❌ **온전하지 못함**: 현재 일조시간 데이터가 없으면 평가 가중치 감소
- ⚠️ **부분적 동작**: 다른 기상 지표(기온, 강수)가 있으면 그 기반으로만 점수 산출

---

## 2. 가용 API 조사

### 2.1 기상청 API (기상청_API-Guide.md)

#### ✅ 일조 데이터 제공 API

**kma_sfcdd.php** (일자료 조회)
```
URL: https://apihub.kma.go.kr/api/typ01/url/kma_sfcdd.php
파라미터: tm(날짜), stn(지점번호), authKey
응답 필드: SS_DAY(일조합, hr), SS_DUR(가조시간, hr), SS_CMB(캄벨 일조, hr)
```

**주요 특성:**
- **지점:** 모든 AWS 510개 지점에서 측정
- **시간 단위:** 일(day) 단위
- **데이터 종류:**
  - `SS_DAY`: 일조합(시간, hr) — **우리가 원하는 것**
  - `SS_DUR`: 가조시간(일조 가능 시간)
  - `SS_CMB`: 캄벨 일조(대체 측정)

**가용성:**
- ✅ 역사 데이터: 과거 장기간 조회 가능
- ✅ 인증: .env의 `weather_data_APIkey` 사용 가능
- ⚠️ 제약: 지점 단위(510개) → 시/군(256개)으로 집계 필요

---

#### ⚠️ 제약 확인

**kma_sfcdd.php 사용 제약 (Sunlight-Calculation_API-Guide.md 1-2절):**
```
"이 문서는 [[기상청_API-Guide]]와 달리, AWS가 아닌 AAOS에서 측정한 데이터이므로 
모든 지역의 데이터를 가지고 있지 않음. 이를 미리 알아둘 것"
```

⚠️ **문제:** AAOS(자동기상관측소) 측정 데이터이므로 **모든 지역에서 가용하지 않을 가능성**

---

### 2.2 농촌진흥청 API (농업기상-기본-관측데이터_API기술명세서.md)

**getWeatherTermDayList3** (기간별 일 기본 관측데이터)
```
URL: apis.data.go.kr/1390802/AgriWeather/WeatherObsrInfo/V3/GnrlWeather/getWeatherTermDayList3
파라미터: serviceKey, begin_Date, end_Date, obsr_Spot_Cd(관측지점코드)
응답 필드: (라인 9에 정의됨)
```

**공통 응답 모델 (라인 9):**
```
sun_Time(일조시간) — 응답 필드명
```

**주요 특성:**
- ✅ 일조시간 포함 명시
- ✅ 기간별(begin_Date ~ end_Date) 조회 가능
- ⚠️ 관측지점 코드 필요 (AAOS 기반)
- ⚠️ 모든 지점에서 일조시간 측정 여부 불명

---

### 2.3 데이터 가용성 정리

| API | 제공 | 지점 수 | 시간 단위 | 커버 범위 |
|-----|------|--------|---------|----------|
| **kma_sfcdd.php** | SS_DAY | 510 AWS | 일 | ⚠️ 불명 |
| **getWeatherTermDayList3** | sun_Time | AAOS | 일 | ⚠️ 불명 |

---

## 3. 전국 커버 여부 실태 조사 (필요 작업)

### 3.1 조사 계획

**Step 1: 510 AWS 지점별 일조시간 데이터 존재 확인**
```python
# weather_client.py 확장: 일조시간 조회 함수
get_sunlight_data(
    point_code: str,
    start_date: str,      # YYYYMMDD
    end_date: str,        # YYYYMMDD
    obs_element: str = "SS_DAY"
)
```

**Step 2: 256 시/군별 커버 범위 판정**
- 각 시/군에 속한 AWS 지점들의 일조시간 데이터 여부 확인
- 일조 데이터 있는 지점 / 없는 지점 비율

**Step 3: 실제 테스트**
```bash
# 예: 서울(108) 2025년 1월 일조시간
https://apihub.kma.go.kr/api/typ01/url/kma_sfcdd.php?
  tm1=20250101&tm2=20250131&stn=108&obs=SS_DAY&authKey=...
```

---

## 4. 일조시간 데이터 부분 커버 시 처리 방안

### 4.1 현실: 일부 지역에만 데이터 존재

**가정:** 510개 AWS 중 M개 지점만 일조시간 측정

### 4.2 처리 전략 (권장안)

#### **안 A: 하이브리드 처리 (권장)**

```
if 지역의 일조 데이터 존재:
    사용: 실측값
    신뢰도: "실측값"
    
elif 지역의 일조 데이터 없음:
    - 계산값 선택지 1: Angstrom 공식 (기온·강수 기반)
    - 계산값 선택지 2: 운량(CA_TOT) 기반 추정
    신뢰도: "계산값 (실측 없음)"
    
else 계산도 불가능:
    사용: 평년치
    신뢰도: "평년치 (추정값 아님)"
```

**우위:**
- ✅ 가용 데이터 최대 활용
- ✅ 투명한 신뢰도 표기
- ✅ 실측과 추정의 명확한 구분

---

#### **안 B: 모두에 계산값 적용**

```
모든 지역: 계산값 (Angstrom 또는 클라우드 기반)
신뢰도: "계산값"
```

**우위:** 
- ✅ 로직 단순
- ❌ 실측값이 있어도 버림
- ❌ 정확도 하락

---

#### **안 C: 평년치로 통일**

```
모든 지역: 평년치만 사용 (일조시간 지표 제외)
```

**우위:**
- ✅ 로직 가장 단순
- ❌ 일조시간의 중요도 무시
- ❌ 적합도 판정 정확도 저하

---

### 4.3 권장: 안 A (하이브리드) + 단계적 구현

**Phase 1 (현재 — Phase 2-5 완료):**
- 일조시간 실측 데이터: 조사 완료
- 지역별 커버 범위 파악

**Phase 2 (다음):**
- 실측값 가용 지역: API로 일조시간 조회 + DB 적재
- 미실측 지역: Angstrom 공식 + 기본값 제공

**Phase 3 (향후):**
- 클라우드 커버(CA_TOT) 기반 정교한 계산 모델 추가

---

## 5. 즉시 실행 액션

### 5.1 필요한 조사 (이번 주)

```python
# 1. weather_client.py 확장
def get_sunlight_data(point_code: str, start_date: str, end_date: str) -> list[DailySunlight]:
    """일조시간 데이터 조회 (SS_DAY)"""
    pass

# 2. 테스트 & 샘플 수집
point_codes = ["108", "131", "143", ...]  # AWS 510개 지점 일부
for point_code in point_codes:
    result = get_sunlight_data(point_code, "20250101", "20250131")
    print(f"{point_code}: {len(result)} days")  # 데이터 존재 여부 판정
```

### 5.2 기술 명세

**API 호출 예시:**
```
GET https://apihub.kma.go.kr/api/typ01/url/kma_sfcdd3.php?
  tm1=20250101&tm2=20250131&stn=108&help=1&authKey={weather_data_APIkey}
```

**응답 필드:**
- `SS_DAY`: 일조합 (시간)
- `SS_DUR`: 가조시간 (가능했던 시간)
- `SS_CMB`: 캄벨 일조 (대체 측정)

---

## 6. 기술 구현 로드맵

### 현재 상황 (Phase 2-5)
- ✅ API 클라이언트 2개 (weather_client, soil_chem_stat_client) 완료
- ✅ DB 마이그레이션 준비 완료
- ⏳ 일조시간: **조사 대기 중**

### 다음 우선순위
1. **즉시:** 510 AWS 지점별 일조시간 데이터 가용성 조사 (샘플 테스트)
2. **근일:** 지역별(시/군) 커버 범위 판정
3. **실행:** 하이브리드 처리 로직 구현 (실측/계산/평년치)

---

## 참고

- **weather_client.py**: 기상청 API 클라이언트 (기온/강수 구현 완료)
- **기상청_API-Guide.md**: kma_sfcdd.php 명세
- **농업기상-기본-관측데이터_API기술명세서.md**: 농촌진흥청 API 명세
- **Sunlight-Calculation_API-Guide.md**: 일조 관련 API 상세
- **.env**: weather_data_APIkey 보관

---

**상태:** 📍 **일조시간 가용성 조사 필요** — 실측 커버 여부에 따라 구현 전략 결정
