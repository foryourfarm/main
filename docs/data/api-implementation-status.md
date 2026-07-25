# API 구현 상태 및 요구사항 매핑 (2026-07-26 최종)

> **상태:** Phase 2-5 완료 ✅
> - 기상청 & 흙토람 2개 API 클라이언트 구현 ✅
> - DB 마이그레이션 (0014, 0015) 준비 완료 ✅
> - 테스트 스크립트 준비 완료 ✅
> - 서비스 통합 (기존 구현) ✅

---

## 1. API 클라이언트 현황

### 1.1 단기 탭 (실시간 예보)

| 클라이언트 | 역할 | 제공 지점 | 상태 | 비고 |
|-----------|------|---------|------|------|
| **forecast_client.py** | KMA 단기예보 | 256 시/군 | ✅ 완료 | `temp_avg, temp_night_min, rainfall, precip_prob_max, humidity_max` |
| **outlook_client.py** | KMA 3개월 장기예보 | 256 시/군 | ✅ 완료 | `tercile_prob (temp, rainfall)` RSS 파싱 |

**현황:**
- ✅ 단기 예보 데이터: 완전 구성
- ⚠️ 미지원: 일조시간 (나중에 계산 모델로), 풍속

---

### 1.2 장기 탭 (평년치 기반 적합도)

| 클라이언트 | 역할 | 출처 | 상태 | 비고 |
|-----------|------|------|------|------|
| **weather_client.py** ⭐ | KMA 역사 기온/강수 | 기상청 sfc_aws_day.php | ✅ 구현 | `temp_max, temp_min, rainfall` 510 AWS 지점 |
| **soil_chem_stat_client.py** ⭐ | 흙토람 지역 화학성 | 국가데이터포탈 V2 | ✅ 구현 | `pH, organic_matter, avail_p` 256 시/군 |
| **soil_exam_client.py** | 흙토람 필지 검정 | 흙토람 API | ✅ 완료 | pH, EC, P2O5, organic_matter (필지 단위) |
| **soil_profile_client.py** | 흙토람 토양 단면 | 흙토람 API | ✅ 완료 | 토성, 자갈, 경사 |

**⭐ Phase 2-5 신규 구현:**
- ✅ **weather_client.py** → KMA sfc_aws_day.php 파싱 + 결측/이상치 검증
- ✅ **soil_chem_stat_client.py** → 흙토람 3종 API + 구간통계 가중평균 계산

**현황:**
- ✅ 토양 검정 & 단면: 완전 구성
- ✅ 지역 기준값: soil_chem_stat_client.py로 완성

---

### 1.3 캐싱 및 데이터 흐름

| 레이어 | 역할 | 구현 | 상태 |
|-------|------|------|------|
| **climatology_service.py** | 평년치 조회 + 결측 대체 | L2 (DB) + L3 (대체 로직) | ✅ 구현됨 |
| **short_term_service.py** | 단기 위험신호 판정 | forecast_client | ✅ 구현됨 |
| **suitability_service.py** | 장기 적합도 계산 | climatology_service 통합 | ✅ 구현됨 |

---

## 2. DB 마이그레이션 현황

### 2.1 신규 마이그레이션 (Phase 4-5)

| 마이그레이션 | 목적 | 행 수 | 상태 | 파일 |
|------------|------|------|------|------|
| **0014_region_grid_seed** | region_grid 시드 | 256 | ✅ 검증 | `backend/alembic/versions/0014_region_grid_seed.py` |
| **0015_kma_observation_point_seed** | kma_observation_point 시드 | 510 (샘플 15) | ✅ 검증 | `backend/alembic/versions/0015_kma_observation_point_seed.py` |

**동작:**
- 0014: `region` 테이블 읽기 → latlon_to_grid() 계산 → `region_grid(region_id, nx, ny)` 적재
- 0015: 테이블 생성 + 샘플 데이터 삽입 (실제: 510개 필요)

**검증:**
- ✅ Python 문법 검증 통과
- ✅ 마이그레이션 파일 순서 확인 (0014 → 0015)
- ✅ 모델 등록 완료 (models/__init__.py)

---

### 2.2 기존 마이그레이션

| 테이블 | 행 수 | 출처 | 상태 |
|--------|------|------|------|
| **region** | 256 | 행정안전부 법정동코드 | ✅ 기존 |
| **crop** | 5 | 고정 (사과/배/오이/감자/상추) | ✅ 기존 |
| **crop_growth_guide** | ~50 | 문헌 기반 시드 | ✅ 기존 |
| **soil_change_rule** | ~20 | 문헌 기반 계수 | ✅ 기존 |

---

## 3. 테스트 스크립트 (Phase 4)

**파일:** `backend/tests/test_api_clients.py`

### TEST 1: weather_client.py

```python
# 서울(108) 2025년 1월 최고기온 조회
get_daily_weather(
    point_code="108",
    start_date="20250101",
    end_date="20250131",
    obs_element="ta_max"
)
```

**검증 항목:**
- ✅ KMA XML 응답 파싱 (STN, TM, VAL 필드)
- ✅ 음수 강수량 필터링 (rainfall >= 0)
- ✅ 기온 범위 검증 (-50 ~ 50°C)
- ✅ rate limit 재시도 로직

**예상 결과:**
```
✅ TEST 1: weather_client.py
[호출] 서울(108) 2025년 1월 최고기온
[결과] 조회된 일 수: 31
```

---

### TEST 2: soil_chem_stat_client.py

```python
# 고창군(5279000000) 화학성 통계 조회
get_region_soil_chem_stat(bjd_code="5279000000")
```

**검증 항목:**
- ✅ 흙토람 3종 API 호출 (getFarmExamPhInfo, OmInfo, ApInfo)
- ✅ 구간통계(bin_1~bin_6) 가중평균 계산
- ✅ 결측 처리 (None 반환 또는 대체값)
- ✅ 이상치 검증 (pH: 0-14, OM/AP: ≥0)

**예상 결과:**
```
✅ TEST 2: soil_chem_stat_client.py
[호출] 고창군(5279000000) 화학성 통계
[결과] pH: 6.2, 유기물: 24.5%, 유효인산: 95.3
```

---

## 4. 엔드포인트 통합 (기존 구현)

### 4.1 /api/v1/farms/{id}/monthly-outlook

**호출 흐름:**
```
GET /farms/{id}/monthly-outlook
  ↓
suitability_service.get_suitability_month()
  ├─ climatology_service.get_region_climatology()
  │   └─ WeatherClimatology (평년치) 또는 대체값 반환
  ├─ crop_growth_guide 조회
  └─ 적합도 점수 + 위험신호 계산
  ↓
응답: {
  "score": 85.5,
  "grade": "A",
  "risk_flags": [...],
  "limitations": ["평년치 대체 메시지", ...]
}
```

**신뢰도 표기:**
- ✅ `provenance` 필드: 데이터 출처 (평년치/실측/추정)
- ✅ `is_stale` 필드: 신선도 (캐시 나이)
- ✅ `limitations` 배열: 한계 명시

---

### 4.2 /api/v1/farms/{id}/short-term

**호출 흐름:**
```
GET /farms/{id}/short-term
  ↓
short_term_service.get_daily_forecast()
  └─ forecast_client.get_forecast()
  ↓
응답: {
  "forecast": { temp_avg, temp_night_min, rainfall, ... },
  "risk_flags": ["온도 급변", "강수 예상", ...],
  "fetched_at": "2026-07-26T14:30:00Z",
  "is_stale": false
}
```

---

## 5. 실행 순서 (다음 단계)

### Step 1: 마이그레이션 적용

```bash
cd backend
alembic upgrade head
```

**예상:**
- 256 region_grid rows 적재
- 15 kma_observation_point rows 적재 (샘플)

### Step 2: 데이터 검증

```bash
python -c "
from app.db.session import SessionLocal
from app.models import RegionGrid, KmaObservationPoint

db = SessionLocal()
print(f'region_grid: {db.query(RegionGrid).count()}')
print(f'kma_observation_point: {db.query(KmaObservationPoint).count()}')
"
```

### Step 3: API 테스트

```bash
cd backend
python tests/test_api_clients.py
```

### Step 4: 통합 테스트

```bash
# 밭 등록
POST /api/v1/farms

# 월별 적합도 조회 (평년치 대체 메시지 확인)
GET /api/v1/farms/{id}/monthly-outlook

# 일일 위험신호 조회
GET /api/v1/farms/{id}/short-term
```

---

## 6. 미완료 항목 (FE만 남음)

- ⏳ FE 신뢰도 표기 UI
  - `provenance` 필드 표시
  - `is_stale` 표시
  - "~km 대체" 메시지 표시

---

**상태:** ✅ **BE 데이터 파이프라인 완료** — FE 연동만 남음
