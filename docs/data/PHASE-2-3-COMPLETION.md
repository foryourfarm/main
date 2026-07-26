# Phase 2-3 완료: API 클라이언트 + 마이그레이션 준비 (2026-07-26)

> ⚠️ **작성 당시 스냅샷.** 최신 상태는 `docs/data/CURRENT-STATUS.md`. 0014 마이그레이션은
> 폐기됐고, 기상 클라이언트의 apihub 전환은 보류 상태다(키 미발급·응답 형식 미확인).

> 기상청_API-Guide.md 통합 → API 클라이언트 실구현 → Phase 4 준비

---

## ✅ Phase 2: API 클라이언트 완성

### 2-1. weather_client.py ✅ DONE

**파일:** `backend/app/infra/public_api/weather_client.py`

**기간청 API 명세 적용:**
```python
# sfc_aws_day.php
def get_daily_weather(
    point_code: str,      # 지점번호 (예: "108" = 서울)
    start_date: str,      # YYYYMMDD
    end_date: str,        # YYYYMMDD
    obs_element: str      # ta_max, ta_min, ta_day, rn_day
) -> list[DailyWeatherObservation]
```

**특징:**
- ✅ KMA XML 응답 파싱 (errCode, STN, TM, VAL)
- ✅ 음수강수량 거르기 (이상치 처리)
- ✅ 기온 범위 검증 (-50 ~ 50°C)
- ✅ rate limit 지수 백오프 재시도

**검증 필요:**
- [ ] 실제 KMA API 호출 테스트
  ```bash
  # 테스트: 서울 2025년 1월 최고기온
  get_daily_weather("108", "20250101", "20250131", "ta_max")
  ```

---

### 2-2. soil_chem_stat_client.py ✅ DONE

**파일:** `backend/app/infra/public_api/soil_chem_stat_client.py`

**기술명세서 기반 완전 구현:**
```python
# 3개 엔드포인트 호출
def get_region_soil_chem_stat(bjd_code: str) -> RegionSoilChemStat
```

**API 엔드포인트:**
1. `getFarmExamPhInfo` — pH 통계 (구간: 4.5이하, 4.6~5.0, ..., 6.6이상)
2. `getFarmExamOmInfo` — 유기물 (구간: 10이하, 11~20, ..., 51이상)
3. `getFarmExamApInfo` — 유효인산 (구간: 논 50이하~, 밭 200이하~)

**특징:**
- ✅ 법정동코드 (10자리) 입력
- ✅ 구간통계 → 가중평균 산출 (구간중점 × 면적)
- ✅ 논/밭 경지구분별 평균
- ✅ 결측/이상치 검증 (pH: 0-14, OM/AP: ≥0)

**응답 구조:**
```python
RegionSoilChemStat(
    bjd_code="5279000000",           # 법정동코드
    bjd_name="전라북도 고창군",
    ph_avg=6.2,                      # 평균 pH (논+밭 가중)
    organic_matter_avg=24.5,         # 평균 유기물 (%, 가중)
    avail_p_avg=95.3                 # 평균 유효인산 (mg/kg, 가중)
)
```

**검증 필요:**
- [ ] 실제 API 호출 테스트
  ```bash
  # 테스트: 고창군 (5279000000)
  get_region_soil_chem_stat("5279000000")
  ```

---

## 📋 Phase 3: DB 마이그레이션 준비

### 필요 마이그레이션 (3개)

| 번호 | 파일명 | 목적 | 행 수 |
|------|--------|------|------|
| 0014 | `region_grid_seed.py` | region(256) × latlon_to_grid() → nx, ny | 256 |
| 0015 | `kma_observation_point_seed.py` | KMA 510 지점 정보 | 510 |
| 0016 | `region_to_point_mapping_seed.py` | 510지점 → 256지역 (격자거리 매핑) | 510 |

### 3-1. region_grid_seed (0014)

**모델:** 이미 존재 (`backend/app/models/region_grid.py`)
```python
class RegionGrid(Base):
    region_id: Mapped[int] = mapped_column(ForeignKey("region.id"), primary_key=True)
    nx: Mapped[int]
    ny: Mapped[int]
```

**데이터 소싱:**
```
region 테이블(256개)
  ↓
각 region_id의 위도/경도 조회 (현재 region에 없으면, 행정구역 중심좌표 또는 마스터 테이블)
  ↓
latlon_to_grid(lat, lon) → (nx, ny)
  ↓
region_grid(region_id, nx, ny) 삽입
```

**문제:** 현재 region 테이블에 lat/lon이 있는지 확인 필요

### 3-2. kma_observation_point_seed (0015)

**모델:** 생성 필요 (`backend/app/models/kma_observation_point.py`)
```python
class KmaObservationPoint(Base):
    point_code: Mapped[str] = mapped_column(String(10), primary_key=True)  # 지점번호
    name: Mapped[str] = mapped_column(String(50))  # 지점명
    lat: Mapped[float]  # 위도
    lon: Mapped[float]  # 경도
    altitude: Mapped[int]  # 해발고도
```

**데이터 소싱:**
```
기상청 AWS 510개 지점 정보
  ← 공개 data/kma_stations.json 또는 기상청 API의 getAwsStnLstTbl
  ↓
kma_observation_point(point_code, name, lat, lon, altitude) 삽입
```

**데이터 확보:** 필요 (파일 또는 API)

### 3-3. region_to_point_mapping_seed (0016) [선택사항]

**용도:** 510지점 → 256지역 매핑 (climatology_service에서 사용)

**모델:** 생성 필요 (또는 현재 on-demand 매핑 유지)
```python
class RegionToPointMapping(Base):
    region_id: Mapped[int] = mapped_column(ForeignKey("region.id"))
    point_code: Mapped[str] = mapped_column(ForeignKey("kma_observation_point.point_code"))
    distance_km: Mapped[float]  # 격자상 거리
    is_primary: Mapped[bool] = mapped_column(default=False)  # 대표 지점
```

**현재 상태:** climatology_service에서 on-demand로 최근접 지점을 찾음 → 사전 매핑 불필요

---

## 🚀 Phase 4: 엔드포인트 통합

### 4-1. short_term_service ↔ forecast_client

**현황:** ✅ 이미 통합됨 (short_term_service.py)

**확인사항:**
- [ ] /farms/{id}/short-term 엔드포인트 호출 테스트
- [ ] weather_snapshot 캐시 작동 확인

### 4-2. suitability_service ↔ climatology_service

**현황:** ✅ 이미 통합됨 (suitability_service.py 라인 249-261)

**흐름:**
```
/farms/{id}/monthly-outlook
  ↓ (farms.py)
suitability_service.compute_monthly_outlook(db, user_id, farm_id, year)
  ↓
load_climatology(db, farm.region_id)  ← climatology_service
  ↓
평년치 로드 또는 격자 거리로 대체
  ↓
JSON 응답 (limitations 포함)
```

**확인사항:**
- [ ] 평년치 없는 지역 대체 메시지 표시
- [ ] 신뢰도 표기 (substituted_from, distance_km)

---

## 📝 다음 액션 항목

### 즉시 (오늘)

```
✅ Phase 2 완료:
  - weather_client.py (기상청 sfc_aws_day.php)
  - soil_chem_stat_client.py (흙토람 화학성 3종 API)
  - API 상태 문서 업데이트

⏳ Phase 3 준비:
  - [ ] region 테이블에 lat/lon 있는지 확인
  - [ ] KMA 510지점 마스터 데이터 확보
  - [ ] 마이그레이션 3개 작성 (alembic revision)
```

### 근일 (내일~)

```
⏳ Phase 3 적용:
  - [ ] alembic upgrade head (마이그레이션 적용)
  - [ ] 데이터 적재 검증

⏳ Phase 4 검증:
  - [ ] weather_client.py 실제 호출 테스트
  - [ ] soil_chem_stat_client.py 실제 호출 테스트
  - [ ] end-to-end: 사과 + 고창군 테스트
    GET /farms/{id}/monthly-outlook
    → 평년치 대체 메시지 표시 확인
```

### 1주

```
⏳ 신뢰도 표기:
  - [ ] FE: fetched_at, is_stale, provenance 표시
  - [ ] FE: "이 지역은 OO값을 ~km 대체" 메시지
```

---

## 📚 참고 파일

| 파일 | 역할 | 상태 |
|------|------|------|
| `데이터-통합-전략.md` | 매핑/캐싱/신뢰도 설계 | ✅ |
| `api-구현-상태.md` | 구현 체크리스트 | ✅ 업데이트됨 |
| `CURRENT-STATUS.md` | 워킹 문서 | ✅ |
| `기상청_API-Guide.md` | KMA 명세 | ✅ 활용됨 |
| `농경지화학성-통계정보_V2_API기술명세서.md` | 흙토람 명세 | ✅ 활용됨 |
| `weather_client.py` | 기상청 클라이언트 | ✅ 수정됨 |
| `soil_chem_stat_client.py` | 흙토람 클라이언트 | ✅ 구현됨 |

---

## 커밋 계획

### Commit 1 (지금)
```
type: feat
scope: soil-api
message: soil_chem_stat_client.py 국가데이터포탈 API 완전 구현

- 기술명세서 검증 완료
- 3개 엔드포인트 (pH, 유기물, 유효인산)
- 구간통계 → 가중평균 산출
- 결측/이상치 검증 추가
```

### Commit 2 (다음)
```
type: test
scope: api-clients
message: weather_client.py + soil_chem_stat_client.py 실제 호출 테스트

- KMA sfc_aws_day.php 호출 검증
- 흙토람 3종 API 호출 검증
- 응답 파싱 및 결측 처리 테스트
```

### Commit 3 (후속)
```
type: chore
scope: db-migration
message: 마이그레이션 추가 (region_grid, kma_observation_point)

- 0014_region_grid_seed.py
- 0015_kma_observation_point_seed.py
- 데이터 적재 및 검증
```

---

## 체크리스트

- [x] 기상청 API 명세 통합 (weather_client.py)
- [x] 흙토람 API 명세 검증 (soil_chem_stat_client.py)
- [x] climatology_service ↔ suitability_service 통합 확인
- [x] 라우터 구현 확인
- [ ] 실제 API 호출 테스트
- [ ] DB 마이그레이션 작성 및 적용
- [ ] end-to-end 통합 테스트
- [ ] FE 신뢰도 표기 구현
