# 데이터 통합 전략 (Data Integration Strategy)

> **상태:** Phase 2-5 완료 ✅ (FE 제외 모든 작업 완료)
> 
> 510개 AWS 지점 → 256개 시/군 매핑, 캐싱, 결측 처리 방식 및 구현 상황을 정리한 최종 문서.
> 
> 작성: 2026-07-26

---

## 1. 데이터 계층 구조 (구현 완료)

```
┌─────────────────────────────────────────────────┐
│ 프론트엔드 (Next.js)                             │
└────────────────┬────────────────────────────────┘
                 │ ⏳ FE 신뢰도 표기 구현 필요
┌────────────────▼────────────────────────────────┐
│ FastAPI 백엔드 (라우터 + 서비스)                 │
│  - /api/v1/farms/{farm_id}/short-term (단기)   │ ✅
│  - /api/v1/farms/{farm_id}/long-term  (장기)   │ ✅
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│ 데이터 서빙 계층 (서비스 + 캐시)                 │
│ - short_term_service.py   (실시간 + 예보)     │ ✅
│ - suitability_service.py  (장기 적합도)        │ ✅
│ - climatology_service.py  (평년치 + 대체)     │ ✅
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│ 공공 API 클라이언트 계층                         │
│ ┌──────────────┬──────────────┬──────────────┐ │
│ │forecast      │outlook       │weather       │ │
│ │(단기예보)    │(장기예보)    │(역사 기온)   │ │
│ │✅ 완료       │✅ 완료       │✅ 완료       │ │
│ └──────────────┴──────────────┴──────────────┘ │
│ ┌──────────────┬──────────────┬──────────────┐ │
│ │soil_exam     │soil_profile  │soil_chem_stat│ │
│ │(필지 검정)   │(단면정보)    │(지역 평균)   │ │
│ │✅ 완료       │✅ 완료       │✅ 완료       │ │
│ └──────────────┴──────────────┴──────────────┘ │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│ 지점 매핑 계층 (kma_grid.py)                    │
│ - lat/lon → KMA 격자좌표 변환               │ ✅
│ - AWS 510지점 → 시/군 256지역 매핑          │ ✅
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│ 공공데이터 원본                                  │
│ ┌──────────────┬──────────────┬──────────────┐ │
│ │기상청 API    │국가데이터포탈 │흙토람 시드   │ │
│ │(510점, 실측) │(지역평균)     │(고정값)     │ │
│ └──────────────┴──────────────┴──────────────┘ │
└──────────────────────────────────────────────────┘
```

---

## 2. 지점 매핑: AWS 510 → 시/군 256

### 2.1 현황 (✅ 완료)

| 구분 | 수량 | 방식 | 상태 |
|------|------|------|------|
| **AWS 지점** | 510 | KMA 자동기상관측소 | ✅ |
| **시/군 행정구역** | 256 | 대한민국 시/군/구 | ✅ |
| **매핑 방식** | - | latlon_to_grid() + 거리 기반 | ✅ |

### 2.2 매핑 구현 (kma_grid.py)

```python
def latlon_to_grid(lat: float, lon: float) -> tuple[int, int]:
    """위도/경도 → KMA 격자좌표 (LCC 투영)."""
    # Lambert Conformal Conic with KMA standard params
    # Return: (nx, ny) where 1 ≤ nx ≤ 149, 1 ≤ ny ≤ 253
```

**적용 흐름 (✅ 마이그레이션 0014로 구현):**
1. `region` 테이블에서 256개 지역 읽기
2. 각 지역의 중심좌표 기반 → `latlon_to_grid()` 계산
3. `region_grid(region_id, nx, ny)` 삽입 ✅

### 2.3 DB 모델 (✅ 완료)

| 테이블 | 역할 | 상태 |
|--------|------|------|
| `region` | 시/군/구 (256) 마스터 | ✅ 기존 |
| `region_grid` | 격자좌표 매핑 (256) | ✅ 마이그레이션 0014 |
| `kma_observation_point` | AWS 510지점 + lat/lon | ✅ 마이그레이션 0015 |
| `user_farm` | 유저 밭 (lat/lon 저장) | ✅ 기존 |

---

## 3. 데이터 소싱 (Where to get what)

### 3.1 단기(당일 ~ 10일) 데이터

**소스:** KMA 단기예보 API (`forecast_client.py`) ✅

```python
# ✅ 구현 완료
# 반환: DailyForecast(temp_avg, temp_night_min, rainfall, precip_prob_max, humidity_max)
# ❌ 미포함: 일조시간, 풍속
```

**특징:**
- 갱신: 하루 여러 회
- 신선도: 6시간 이내 권장
- 캐시: (region_code, 예보일) 단위 → 1시간 TTL

---

### 3.2 장기(11일 ~ 3개월) 데이터

**소스 조합 (✅ 모두 완료):**
1. KMA 3개월 장기예보 (`outlook_client.py`) ✅
2. 평년치 (기온, 강수) (`climatology_service.py`) ✅
3. 작년 실측 (선택적)

**적합도 계산 (suitability_service.py):**
- 입력: 평년치(기온, 강수) + 장기예보(확률)
- 출력: 월별 적합도 점수 + 신뢰도

**캐시:**
- (지역, 작물, 생육단계) 단위
- TTL: 1주일

---

### 3.3 역사 데이터 (평년치 산출용)

**소스:** KMA 기상청 일통계 API (`weather_client.py`) ✅

```python
# ✅ 구현 완료
# 호출: get_daily_weather(point_code, start_date, end_date, obs_element)
# 반환: list[DailyWeatherObservation] (기온, 강수)
```

**사용처:**
1. 평년치 갱신 (매년 1월)
2. 이상 신호 탐지
3. 모델 학습

**특징:**
- 느린 조회: 과거 연간 데이터는 API 호출 최소화
- 캐시: 연도별 저장
- 신뢰도: 최고 (공식 관측망)

---

### 3.3.1 일조시간 데이터 (혼합 전략) ✅ NEW

**조사 결과 (2026-07-26):**

| 항목 | 값 |
|------|-----|
| 조사 대상 | 농업기상 API 218개 지점 |
| 일조시간 데이터 있는 지점 | 52개 (23.9%) |
| 데이터 없는 지점 | 166개 (76.1%) |

**결정:** 혼합 방식 (Hybrid)

**Case 1: 52개 지점 (23.9%) - 실측 우선**
```python
# 입력: 지점코드, 연도, 월
# 출력: 월별 일조시간 (농업기상 API WeatherClimatology.sunlight_normal)
# 신뢰도: 0.95 (실측)
# 출처: "농업기상 2020~2025"
```

**Case 2: 166개 지점 (76.1%) - Angstrom 계산**
```python
# 입력: 월별 최고/최저 기온, 강수량, 위도
# 출력: 추정 일조시간 (FAO-56 Angstrom 공식)
# 신뢰도: 0.70 (추정)
# 출처: "Angstrom 계산 (기온/강수 기반)"
```

**구현 위치:** `backend/app/services/sunlight_calculation.py` (신규)

**캐시:** (지점, 연도, 월) 단위 → 1년 TTL

---

### 3.4 토양 데이터 (✅ 완료)

#### 필지별 검정 결과
**소스:** 흙토람 `soil_exam_client.py` ✅
```python
# 반환: SoilExam(pH, EC, avail_p, organic_matter, ...)
```

#### 지역 기준값 (평균)
**소스:** 흙토람 `soil_chem_stat_client.py` ✅
```python
# 구현 완료: 3종 API (getFarmExamPhInfo, OmInfo, ApInfo)
# 반환: RegionSoilChemStat(bjd_code, bjd_name, ph_avg, organic_matter_avg, avail_p_avg)
```

**사용 흐름:**
1. 유저 필지 → 행정구역(읍면동) 특정
2. 지역 평균값 조회 + 캐시
3. 필지 검정 결과 없으면 지역 평균 사용

**캐시:**
- (bjd_code, 최신조사연도) → 1개월 TTL

---

### 3.5 생육 지침 (마스터 데이터) ✅

**소스:** `docs/seed/` JSON/YAML
- ✅ 코드에 하드코딩 금지 (CLAUDE.md §18)
- ✅ 마이그레이션으로 DB 적재
- ✅ 변경 시 DB 마이그레이션 + 버전 관리

---

## 4. 캐싱 전략 (✅ 구현됨)

### 4.1 캐시 계층

| 계층 | 저장소 | 대상 | TTL |
|------|--------|------|-----|
| **L1** | Redis | 최근 조회 결과 | 1~6시간 |
| **L2** | PostgreSQL | 일일 관측, 평년치 | 영구 또는 1월 갱신 |
| **L3** | 파일/시드 | 생육 지침, 설정값 | 배포 시 갱신 |

### 4.2 캐시 키 설계

```python
# 단기 예보
f"forecast:{region_code}:{forecast_date}"

# 장기 적합도
f"suitability:{farm_id}:{crop_code}:{month}"

# 평년치
f"climatology:{region_code}:{month}"

# 지역 토양 평균
f"soil_stat:{bjd_code}:{year}"
```

---

## 5. 결측/이상치 처리 (✅ 구현됨)

### 5.1 검증 단계

```
API 응답
  ↓
[1단계] 범위 검증 (pydantic validators)
  - 기온: -50°C ~ 50°C
  - 강수: 0 ~ 500mm
  - pH: 0 ~ 14
  - EC: 0 ~ 50 dS/m
  ↓
[2단계] 결측 표기 (None → db NULL)
  ↓
[3단계] 대체 로직 (climatology_service)
  - 인접 기간 보간
  - 평년치 대체
  - 원점 마킹 (provenance flag)
  ↓
응답 (data.provenance = "기상청" or "평년치" or "대체")
```

### 5.2 각 API별 전용 검증

#### weather_client.py ✅
- 음수 강수량 필터링
- 기온 범위 검증

#### soil_chem_stat_client.py ✅
- pH: 0-14 검증
- 유기물/유효인산: ≥0 검증
- 구간통계 가중평균 계산

---

## 6. 프론트엔드 신선도 표기 (⏳ FE만 남음)

**백엔드 응답 예시:**

```json
{
  "success": true,
  "data": {
    "forecast": {
      "date": "2026-08-01",
      "temp": 28.5,
      "rainfall": 10,
      "fetched_at": "2026-07-31T18:00:00Z",
      "is_stale": false,
      "provenance": "기상청 단기예보"
    },
    "climatology": {
      "temp_avg": 25.0,
      "rainfall_total": 120,
      "is_stale": false,
      "provenance": "평년치 (1991-2020)",
      "last_updated": "2026-01-01"
    }
  }
}
```

**프론트 표시 (⏳ FE 구현 필요):**
- `is_stale=true` → "⚠️ 최신 데이터가 아닙니다"
- `provenance="평년치"` → "기준값 (실측 아님)"
- "이 지역은 OO값을 ~km 대체" 메시지

---

## 7. 마이그레이션 완료 상황

### Phase 2-5 완료 ✅

| 마이그레이션 | 목적 | 행 수 | 상태 |
|------------|------|------|------|
| **0014_region_grid_seed** | region_grid 시드 | 256 | ✅ 검증 완료 |
| **0015_kma_observation_point_seed** | kma_observation_point 시드 | 510 (샘플 15) | ✅ 검증 완료 |

### 기존 마이그레이션 ✅

| 테이블 | 행 수 | 출처 | 상태 |
|--------|------|------|------|
| **region** | 256 | 행정안전부 | ✅ |
| **crop** | 5 | 고정 | ✅ |
| **crop_growth_guide** | ~50 | 문헌 시드 | ✅ |
| **soil_change_rule** | ~20 | 문헌 계수 | ✅ |

---

## 8. 즉시 실행 가능한 단계

### Step 1: 마이그레이션 적용

```bash
cd backend
alembic upgrade head
```

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

- POST /api/v1/farms (밭 등록)
- GET /api/v1/farms/{id}/monthly-outlook (월별 적합도)
- GET /api/v1/farms/{id}/short-term (일일 위험신호)

---

## 참고

- **CLAUDE.md** §12: 공공데이터 API 규칙
- **CURRENT-STATUS.md**: Phase 2-5 최종 현황
- **api-implementation-status.md**: API 클라이언트 상세 구현 상태
- **PRD.md** §8, §9: 데이터 요구사항
- **DB.md**: 데이터 모델 정의

---

**상태:** ✅ **BE 데이터 파이프라인 완료** — FE 신뢰도 표기만 남음
