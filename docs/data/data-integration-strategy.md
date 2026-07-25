# 데이터 통합 전략 (Data Integration Strategy)

> 현재 확보된 데이터를 기반으로 510개 AWS 지점 → 256개 시/군 매핑, 캐싱, 결측 처리 방식을 정리한 문서.
> 작성: 2026-07-26

---

## 1. 데이터 계층 구조

```
┌─────────────────────────────────────────────────┐
│ 프론트엔드 (Next.js)                             │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│ FastAPI 백엔드 (라우터 + 서비스)                 │
│  - /api/v1/farms/{farm_id}/short-term (단기)   │
│  - /api/v1/farms/{farm_id}/long-term  (장기)   │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│ 데이터 서빙 계층 (서비스 + 캐시)                 │
│ - short_term_service.py  (실시간 + 예보)       │
│ - suitability_service.py (장기 적합도)          │
│ - climatology_service.py (평년치 + 대체)       │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│ 공공 API 클라이언트 계층                         │
│ ┌──────────────┬──────────────┬──────────────┐ │
│ │forecast      │outlook       │weather       │ │
│ │(단기예보)    │(장기예보)    │(역사 기온)   │ │
│ └──────────────┴──────────────┴──────────────┘ │
│ ┌──────────────┬──────────────┬──────────────┐ │
│ │soil_exam     │soil_profile  │soil_chem_stat│ │
│ │(필지 검정)   │(단면정보)    │(지역 평균)   │ │
│ └──────────────┴──────────────┴──────────────┘ │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│ 지점 매핑 계층 (kma_grid.py)                    │
│ - lat/lon → KMA 격자좌표 변환                   │
│ - AWS 510지점 → 시/군 256지역 매핑             │
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

### 2.1 현황

| 구분 | 수량 | 방식 |
|------|------|------|
| **AWS 지점** | 510 | KMA 자동기상관측소 |
| **시/군 행정구역** | 256 | 대한민국 시/군/구 |
| **매핑 방식** | - | lat/lon → KMA 격자좌표 → 시/군 코드 |

### 2.2 매핑 구현 (kma_grid.py)

**기존 구현:**
```python
def latlon_to_grid(lat: float, lon: float) -> tuple[int, int]:
    """위도/경도 → KMA 격자좌표 (LCC 투영)."""
    # Lambert Conformal Conic with KMA standard params
    # Return: (nx, ny) where 1 ≤ nx ≤ 149, 1 ≤ ny ≤ 253
```

**적용 흐름:**
1. 유저 밭 등록 시 lat/lon 입력
2. `latlon_to_grid()` → (nx, ny) 격자
3. 격자 → AWS 510지점 중 최근접점 선택 OR 복수 지점 평균
4. AWS 지점 → 시/군 코드로 역매핑 (기존 마스터 데이터 테이블 활용)

**우려사항:**
- 일부 지역(경계, 섬)은 가장 가까운 지점이 50km 이상일 수 있음 → 신뢰도 표기 필요
- 고산지역: 표고 차이로 인한 기온 편차 고려 필요 (구현: 추후)

### 2.3 현재 DB 설계 (models/)

| 테이블 | 역할 |
|--------|------|
| `region` | 시/군/구 (256) 마스터 |
| `kma_observation_point` | AWS 510지점 + lat/lon |
| `region_to_point_mapping` | 시/군 ↔ AWS 다대일 매핑 |
| `user_farm` | 유저 밭 (lat/lon 저장) |

**마이그레이션 필요:**
- `region_to_point_mapping` 테이블 생성 (seed 데이터: 510지점 → 256지역 조회)
- `kma_observation_point` seed 데이터 (기본 510지점)

---

## 3. 데이터 소싱 (Where to get what)

### 3.1 단기(당일 ~ 10일) 데이터

**소스:** KMA 단기예보 API (`forecast_client.py`)
```python
# ✅ 구현 완료
# 반환: DailyForecast(temp_avg, temp_night_min, rainfall, precip_prob_max, humidity_max)
# ❌ 미포함: 일조시간, 풍속
```

**특징:**
- 갱신: 하루 여러 회 (예: 06시, 12시, 18시, 00시)
- 신선도: 6시간 이내 권장
- 캐시: (lat, lon, 예보일) 단위 → 1시간 TTL

**결측 처리:**
- 강수확률 없음 → `precip_prob_max` = 0 추정
- 습도 없음 → 평년치 + 기온으로 추정 (추후)
- 단기는 일조 미제공 → `sunlight` = None 유지

---

### 3.2 장기(11일 ~ 3개월) 데이터

**소스 조합:**
1. KMA 3개월 장기예보 (`outlook_client.py`)
2. 평년치 (기온, 강수) (`climatology_service.py`)
3. 작년 실측 (선택적, 추가 신호)

```python
# ✅ outlook_client.py 구현 완료
# 반환: tercile probabilities (prob_above, prob_normal, prob_below) for temp/rainfall

# ✅ climatology_service.py 구현 필요
# 반환: WeatherClimatology(temp_avg, rainfall_total, ..., sunlight_normal)
```

**적합도 계산 (suitability_service.py):**
- 입력: 평년치(기온, 강수) + 장기예보(확률) + 작년실측
- 출력: 월별 적합도 점수 + 신뢰도

**캐시:**
- (지역, 작물, 생육단계) 단위
- TTL: 1주일 (장기예보는 갱신 빈도 낮음)

---

### 3.3 역사 데이터 (평년치 산출용, 장기적)

**소스:** KMA 기상청 일통계 API (`weather_client.py`)
```python
# ⚠️ 구현 진행중
# 호출: get_daily_weather(point_code, start_date, end_date, obs_element)
# 반환: list[DailyWeatherObservation] (기온, 강수)
```

**사용처:**
1. 평년치 갱신 (매년 1월, 과거 30년 데이터 집계)
2. 이상 신호 탐지 (예: 금년 기온이 평년 ±2σ)
3. 모델 학습 (예정)

**특징:**
- 느린 조회: 과거 연간 데이터는 API 호출 최소화
- 캐시: 연도별 (예: 2025년 전체) 테이블 저장 → 재사용
- 신뢰도: 고정값 (공식 관측망 데이터 = 가장 신뢰)

---

### 3.4 토양 데이터

#### 필지별 검정 결과 (토양_검정)
**소스:** 흙토람 `soil_exam_client.py` (필지 단위 실측)
```python
# ✅ 구현 완료 (V2, ver1.0)
# 반환: SoilExam(pH, EC, avail_p, organic_matter, ...)
# 갱신: 유저 수동 입력 또는 검정기관 연동
```

#### 지역 기준값 (평균)
**소스:** 흙토람 `soil_chem_stat_client.py` (지역 평균)
```python
# ⚠️ placeholder (실제 API 명세 대기)
# 의도: RegionSoilChemStat(bjd_code, survey_year, ph_avg, organic_matter_avg, avail_p_avg)
```

**사용 흐름:**
1. 유저 필지 → 행정구역(읍면동) 특정
2. 지역 평균값 조회 + 캐시
3. 필지 검정 결과 없으면 지역 평균 사용

**캐시:**
- (bjd_code, 최신조사연도) → 1개월 TTL
- 또는 DB 시드로 고정 (자주 갱신 안 됨)

---

### 3.5 생육 지침 (마스터 데이터)

**소스:** `docs/seed/` JSON/YAML
```python
# 예: crop_growth_guide_rice.json
{
  "crop_code": "rice",
  "stages": [
    {
      "stage_id": "germination",
      "day_range": [0, 7],
      "soil_optimal": {
        "ph_min": 5.5, "ph_max": 7.0,
        "ec_min": 0.0, "ec_max": 0.5,
        ...
      },
      "weather_ideal": {
        "temp_avg_min": 15,
        "rainfall_total_mm": 50,
        ...
      }
    },
    ...
  ]
}
```

**특징:**
- 고정값 (코드 내 하드코딩 금지 — CLAUDE.md §18)
- 마이그레이션으로 DB 적재 (alembic/versions/0001_init_seed.py 등)
- 변경 시 DB 마이그레이션 + 코드 버전 관리

---

## 4. 캐싱 전략

### 4.1 캐시 계층

| 계층 | 저장소 | 대상 | TTL |
|------|--------|------|-----|
| **L1** | Redis | 최근 조회 결과 | 1~6시간 |
| **L2** | PostgreSQL | 일일 관측, 평년치 | 영구 또는 1월 갱신 |
| **L3** | 파일/시드 | 생육 지침, 설정값 | 배포 시 갱신 |

### 4.2 캐시 키 설계

```python
# 단기 예보
f"forecast:{lat}:{lon}:{forecast_date}"

# 장기 적합도
f"suitability:{farm_id}:{crop_code}:{month}"

# 평년치
f"climatology:{region_code}:{month}"

# 지역 토양 평균
f"soil_stat:{bjd_code}:{year}"
```

### 4.3 캐시 무효화 규칙

| 데이터 | 갱신 트리거 | TTL |
|--------|-----------|-----|
| **예보** | 기상청 발표 시 | 6시간 |
| **평년치** | 연 1회 (1월) 또는 수동 갱신 | 1년 |
| **토양지역평균** | 연 1회 또는 수동 갱신 | 1개월 |
| **생육지침** | 코드 배포 시 | 영구 |

---

## 5. 결측/이상치 처리 (CLAUDE.md §12)

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

#### weather_client.py (기상청 기온/강수)
```python
@field_validator("rainfall")
def reject_negative_rainfall(cls, v):
    return None if v is not None and v < 0 else v
```

#### soil_exam_client.py (토양 검정)
```python
@field_validator("ph")
def ph_in_range(cls, v):
    return None if v is not None and not (0 <= v <= 14) else v
```

### 5.3 대체 전략

| 결측 데이터 | 1차 대체 | 2차 대체 | 최종 | 표기 |
|-----------|---------|---------|------|------|
| 기온 (일) | 인접 2일 평균 | 평년치 | 평년치 | ⚠️ 대체됨 |
| 강수 (일) | 전월 평균 | 0mm | 0mm | ⚠️ 결측 |
| 토양 pH | - | 지역평균 | 지역평균 | ℹ️ 지역기준 |
| EC | - | 0.0 (추정) | 0.0 | ℹ️ 계산값 |

---

## 6. 프론트엔드 신선도 표기

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

**프론트 표시:**
- `is_stale=true` → "⚠️ 최신 데이터가 아닙니다"
- `provenance="평년치"` → "기준값 (실측 아님)"
- 모든 수치 옆에 출처 아이콘

---

## 7. 마이그레이션 체크리스트

### Phase 1: 기초 마스터 데이터

- [ ] `region` (256개 시/군) 시드
- [ ] `kma_observation_point` (510개 지점 + lat/lon) 시드
- [ ] `region_to_point_mapping` (다대일 매핑) 시드
- [ ] `crop_growth_guide` (5종 작물) 시드
- [ ] `weather_climatology` (모든 지역 × 월) 시드

### Phase 2: API 클라이언트

- [x] `forecast_client.py` ✅
- [x] `outlook_client.py` ✅
- [x] `kma_grid.py` ✅
- [ ] `weather_client.py` — 테스트 필요
- [ ] `soil_chem_stat_client.py` — API 명세 대기

### Phase 3: 서비스 계층

- [x] `short_term_service.py` ✅
- [x] `suitability_service.py` ✅
- [ ] `climatology_service.py` — 구현
- [ ] 캐싱 로직 (Redis/DB)

### Phase 4: 엔드포인트

- [ ] `/api/v1/farms/{id}/short-term` 연동
- [ ] `/api/v1/farms/{id}/long-term` 연동
- [ ] `/api/v1/weather-snapshot` 캐시 상태

---

## 8. 다음 단계 (로드맵)

### 우선순위 1: 즉시 필요
- [ ] weather_client.py 실제 API 테스트
- [ ] soil_chem_stat_client.py API 명세 확인 (국가데이터포탈)
- [ ] climatology_service.py 구현 (평년치 조회 + 결측 대체)
- [ ] DB 시드 데이터 준비 및 마이그레이션

### 우선순위 2: 통합 테스트
- [ ] 엔드투엔드 데이터 파이프라인 테스트
- [ ] 캐시 일관성 검증
- [ ] 결측/이상치 처리 테스트

### 우선순위 3: 최적화
- [ ] 지점 매핑 신뢰도 개선 (고산지, 도시 고려)
- [ ] 일조시간 데이터 수집 및 계산 모델 개발
- [ ] 운량(cloud cover) 데이터 통합

---

## 참고

- **CLAUDE.md** §12: 공공데이터 API 연동 규칙
- **PRD.md** §8, §9: 단기/장기 데이터 요구사항
- **DB.md**: 데이터 모델 상세
