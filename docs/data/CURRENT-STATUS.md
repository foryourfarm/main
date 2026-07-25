# 데이터 파이프라인 현황 정리 (2026-07-26)

> 기상청_API-Guide.md 신규 자료 병합 완료. 현재 상태를 정리한 워킹 문서.
> 다음: weather_client.py 테스트 → soil_chem_stat_client.py 실구현 → end-to-end 테스트

---

## 1. 완료된 작업

### 1.1 신규 자료 병합

**기상청_API-Guide.md 자료:**
- ✅ sfc_aws_day.php API 명세 (510 AWS 지점, 역사 기온/강수)
- ✅ weather_client.py 수정 (명세 적용, TM/STN/VAL 파싱 준비)
- ✅ data-integration-strategy.md 작성 (매핑·캐싱·결측 처리)

### 1.2 서비스 계층 통합 확인

| 계층 | 구현 | 상태 |
|------|------|------|
| **climatology_service.py** | 평년치 조회 + 격자 거리 대체 | ✅ 작동 (2차 조치 완료) |
| **suitability_service.py** | 지침 + 기상/토양 점수 계산 | ✅ climatology 호출 통합 |
| **short_term_service.py** | 단기 위험신호 판정 | ✅ forecast_client 호출 |
| **API 라우터** | /suitability, /monthly-outlook | ✅ farms.py 69, 80 구현 |

### 1.3 마이그레이션 준비 현황

**적재된 마이그레이션 (13개):**
```
0001_init_schema.py          # 기초 스키마
0002_weather_climatology_outlook.py
0003_knowledge_chunk.py      # RAG (pgvector)
0004_crop_growth_guide_seed.py
0005_chat_message.py
0006_soil_delta_shadow.py
0007_crop_growth_stage_seed.py
0008_region_seed.py          # 256개 시/군
0009_outlook_zone_and_range.py
0010_district_and_soil_cache.py
0011_guide_provenance_and_rainfall_unit.py
0012_guide_literature_values.py
0013_drop_monthly_rainfall_guide.py
```

**추가 필요 마이그레이션:**
- [ ] region_grid 시드 (256개 지역 × 기상청 격자 매핑)
- [ ] kma_observation_point 시드 (510 AWS 지점)
- [ ] region_to_point_mapping (지점 → 시/군 대체 매핑)

---

## 2. 다음 작업 (우선순위)

### Phase 2A: 실제 API 호출 검증

#### 2A-1. weather_client.py 테스트

**목표:** 기상청 sfc_aws_day.php 실제 호출 및 응답 파싱 검증

**테스트 케이스:**
```python
# 서울 2025년 1월 최고기온
get_daily_weather(
    point_code="108",          # 서울 지점번호
    start_date="20250101",
    end_date="20250131",
    obs_element="ta_max"
)
# 예상: list[DailyWeatherObservation] with 31개 행
```

**검증 항목:**
- [ ] HTTP 200 응답 및 XML 파싱
- [ ] errCode="00" 또는 성공 코드 확인
- [ ] STN (지점), TM (날짜), VAL (값) 필드 추출
- [ ] 음수값 및 극단값 필터링
- [ ] rate limit 재시도 동작

**실행 방법:**
```bash
cd backend
python -m pytest tests/test_weather_client.py -v
```

#### 2A-2. soil_chem_stat_client.py API 명세 확인

**현황:** [확인 필요] placeholder

**필요 정보:**
1. 정확한 엔드포인트 (현재: `getFarmExamOmInfo` 추정)
   - 흙토람 데이터셋 ID: 15144685
   - 국가데이터포탈 기술명세서 필요
2. 파라미터명 (현재: `BJD_Code` 추정)
3. 응답 필드명 (현재: `Acid_Avg`, `Om_Avg`, `Vldpha_Avg` 추정)

**액션:**
```
흙토람 데이터셋 https://www.data.go.kr/?page=15144685
  → 상세기능 목록 확인 (pH, 유기물, 유효인산 별 엔드포인트)
  → 기술명세서(HWP) 다운로드 → 파라미터/응답 필드명 확인
  → soil_chem_stat_client.py 파라미터 교체
  → 실제 호출 테스트
```

**테스트 데이터:** (읍면동 법정동코드)
```python
get_region_soil_chem_stat("1100000000")  # 서울시 강남구
# 예상: list[RegionSoilChemStat] with pH, EC, P2O5, OM
```

### Phase 2B: DB 마이그레이션 준비

#### 필요 시드 데이터

| 테이블 | 행 수 | 출처 | 상태 |
|--------|------|------|------|
| **region_grid** | 256 | latlon_to_grid 변환 | ⏳ 필요 |
| **kma_observation_point** | 510 | 기상청 AWS 지점 정보 | ⏳ 필요 |
| **region_to_point_mapping** | 510 | 지점 → 시/군 매핑 | ⏳ 필요 |

#### 마이그레이션 작성 순서

```python
# 0014_region_grid_seed.py
# region 테이블에서 region_id를 읽고, latlon_to_grid() 호출해 nx/ny 계산
# region_grid(region_id, nx, ny) 적재

# 0015_kma_observation_point_seed.py
# 기상청 510개 지점 정보 (지점번호, 이름, 위도, 경도, 해발고도)
# kma_observation_point(point_code, name, lat, lon, altitude) 적재

# 0016_region_to_point_mapping_seed.py
# 510 지점을 256 시/군으로 매핑 (대체 거리 기반)
# 또는 현재 climatology_service가 읽는 방식 유지 (on-demand)
```

---

## 3. 구체적 다음 단계

### 즉시 (오늘)

```
현재: 기상청 API 명세 병합, weather_client.py 수정
↓
[할 일]
1. weather_client.py 실제 API 호출 테스트
   - .env 의 weather_data_APIkey 사용
   - 기상청 sfc_aws_day.php 단일 호출 테스트
   - 응답 XML 파싱 검증

2. soil_chem_stat_client.py 스펙 확인
   - 국가데이터포탈 기술명세서 다운로드
   - API 파라미터/응답 필드명 확정
   - placeholder → 실제 구현
```

### 근일 (내일)

```
3. DB 마이그레이션 3개 작성
   - 0014_region_grid_seed.py
   - 0015_kma_observation_point_seed.py
   - 0016_region_to_point_mapping_seed.py

4. 마이그레이션 적용 테스트
   - alembic upgrade head
   - 데이터 적재 확인
```

### 1주

```
5. end-to-end 테스트
   - 사과 + 고창군 밭 등록
   - /farms/{id}/suitability 호출
   - 평년치 대체 메시지 확인
   - 위험신호 판정 검증

6. FE 데이터 신뢰도 표기
   - fetched_at, is_stale, provenance 스키마 추가
   - 대체 메시지 UI 표시
```

---

## 4. 파일 맵

**작성/수정된 파일:**
- ✅ `backend/app/infra/public_api/weather_client.py` (수정됨)
- ✅ `docs/data/data-integration-strategy.md` (신규)
- ✅ `docs/data/api-implementation-status.md` (신규)
- ✅ `docs/data/CURRENT-STATUS.md` (본 파일, 신규)

**기존 파일 (확인):**
- ✅ `backend/app/services/climatology_service.py` (작동함)
- ✅ `backend/app/services/suitability_service.py` (통합됨)
- ✅ `backend/app/api/farms.py` (라우터 구현됨)
- ✅ `backend/alembic/versions/` (13개 준비됨)

**다음 생성 예정:**
- [ ] `backend/alembic/versions/0014_region_grid_seed.py`
- [ ] `backend/alembic/versions/0015_kma_observation_point_seed.py`
- [ ] `backend/alembic/versions/0016_region_to_point_mapping_seed.py`

---

## 5. 커밋 계획

### Commit 1 (지금)
```
type: docs
scope: data-integration
message: 기상청 API 명세 통합 및 데이터 파이프라인 현황 정리

- weather_client.py 수정 (sfc_aws_day.php 적용)
- data-integration-strategy.md 작성 (매핑·캐싱·결측)
- api-implementation-status.md 작성 (구현 상태 추적)
- CURRENT-STATUS.md 작성 (다음 작업 명확화)
```

### Commit 2 (다음)
```
type: test
scope: weather-api
message: weather_client.py 기상청 API 호출 테스트 추가

- sfc_aws_day.php 실제 호출 검증
- XML 응답 파싱 테스트
- 결측/이상치 필터링 테스트
```

### Commit 3 (후속)
```
type: feat
scope: soil-api
message: soil_chem_stat_client.py 국가데이터포탈 API 구현

- 기술명세서 기반 파라미터/응답 구현
- 지역 토양 화학성 조회
- 결측/이상치 검증
```

---

## 6. 참고 문서

- `기상청_API-Guide.md` — sfc_aws_day.php 명세
- `CLAUDE.md` — §12 공공데이터 API 규칙, §3.4 추측 금지
- `DB.md` — §3.10-12 캐시/마이그레이션, §8 계산 로직
- `nexttodo.md` — 평년치 2차 조치, 미착수 항목
- `data-integration-strategy.md` — 매핑·캐싱·신뢰도 전략
- `api-implementation-status.md` — 현재 구현 상태 vs 필요사항 매핑

---

## 7. 의존성 체크

```
✅ weather_client.py (sfc_aws_day.php 명세)
  ↓
⏳ soil_chem_stat_client.py (국가데이터포탈 명세 필요)
  ↓
⏳ DB 마이그레이션 (region_grid, kma_observation_point, region_to_point_mapping)
  ↓
⏳ end-to-end 테스트 (단기/장기 탭 데이터 흐름)
  ↓
⏳ FE 신뢰도 표기 (provenance, is_stale)
```

---

**다음 진행:** weather_client.py 실제 호출 테스트 (기상청 API 호출 검증)
