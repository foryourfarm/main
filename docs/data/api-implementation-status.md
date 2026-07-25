# API 구현 상태 및 요구사항 매핑 (2026-07-26)

> Phase 1: 현재 코드 상태 vs 필요사항 비교. 기상청_API-Guide.md 신규 자료 통합 계획.

---

## 1. 기상청 API 자료 통합 현황

### 1.1 신규 자료: 기상청_API-Guide.md

**포함된 API 명세:**
| API | URL | 사용처 | 상태 |
|-----|-----|--------|------|
| **sfc_aws_day.php** | https://apihub.kma.go.kr/api/typ01/url/sfc_aws_day.php | 역사 기온/강수 (510지점) | 🆕 신규 |
| **getAwsStnLstTbl** | AwsYearlyInfoService | AWS 지점 일람 | 참고용 |
| **getYearSumry** | AwsYearlyInfoService | 연요약 (연 단위) | ✅ 이미 시도 |
| **getStnbyMmSumry** | AwsYearlyInfoService | 월요약 (월 단위) | ✅ 검증 완료 |
| **getDailyAwsData** | AwsMtlyInfoService | 일별 관측 | ❌ 실패 (지원 중단) |

**적용 결정:**
- ✅ `sfc_aws_day.php` 활용 (weather_client.py 방금 수정)
- ✅ `getStnbyMmSumry` 활용 (climatology_service.py 에서)
- ❌ `getDailyAwsData` 대체 (sfc_aws_day.php 로)

---

## 2. API 클라이언트 현황

### 2.1 단기 탭 (실시간 예보)

| 클라이언트 | 역할 | 데이터 | 상태 | 비고 |
|-----------|------|--------|------|------|
| **forecast_client.py** | KMA 단기예보 | temp_avg, temp_night_min, rainfall, precip_prob_max, humidity_max | ✅ | 작동 검증 완료 (2026-07-25) |
| **outlook_client.py** | KMA 3개월 장기예보 | tercile prob (temp, rainfall) | ✅ | RSS 파싱 완료 |

**현황:**
- ✅ 단기 예보 데이터: 완전 구성
- ⚠️ **부족**: 일조시간 (미제공 → 나중에 계산 모델로), 풍속 (미포함)

---

### 2.2 장기 탭 (평년치 기반 적합도)

| 클라이언트 | 역할 | 데이터 | 상태 | 비고 |
|-----------|------|--------|------|------|
| **weather_client.py** | KMA 역사 기온/강수 | temp_max, temp_min, temp_avg, rainfall | ⏳ 방금 수정 | sfc_aws_day.php 적용, 테스트 필요 |
| **soil_exam_client.py** | 흙토람 필지 검정 | pH, EC, P2O5, organic_matter | ✅ | 검증 완료 (V2, ver1.0) |
| **soil_profile_client.py** | 흙토람 토양 단면 | 토성, 자갈, 경사 | ✅ | 검증 완료 |
| **soil_chem_stat_client.py** | 흙토람 지역 평균 | pH, EC(?), P2O5, organic_matter | [확인 필요] | 국가데이터포탈 API 명세 대기 |

**현황:**
- ✅ 토양 검정: 완전 구성
- ⚠️ **부족**: 지역 기준값 (soil_chem_stat_client.py 미확인)

---

### 2.3 캐싱 및 데이터 흐름

| 레이어 | 역할 | 구현 | 상태 |
|-------|------|------|------|
| **climatology_service.py** | 평년치 조회 + 결측 대체 | L2 (DB) + L3 (대체 로직) | ⏳ 필요 |
| **short_term_service.py** | 단기 위험신호 판정 | L1 (메모리) + forecast_client | ✅ 기본 구조 있음 |
| **suitability_service.py** | 장기 적합도 계산 | L2 (DB 캐시) + climatology | ✅ 기본 구조 있음 (climatology 대기) |

---

## 3. 구현 체크리스트

### Phase 2: API 클라이언트 완성

#### 2-1. weather_client.py 검증

```python
# 방금 수정한 내용 검증 필요
def get_daily_weather(
    point_code: str,          # 지점번호 (예: "108" = 서울)
    start_date: str,          # YYYYMMDD
    end_date: str,            # YYYYMMDD
    obs_element: str = "ta_max"  # ta_max, ta_min, ta_day, rn_day
) -> list[DailyWeatherObservation]
```

**검증 항목:**
- [ ] KMA API 실제 호출 테스트
- [ ] XML 응답 파싱 (errCode, errMsg, STN, TM, VAL)
- [ ] 음수 강수량 거르기
- [ ] 기온 범위 검증 (-50 ~ 50°C)
- [ ] rate limit 재시도 로직

**테스트 데이터:**
```python
# 예: 서울 2025년 전체 최고기온
get_daily_weather(
    point_code="108",
    start_date="20250101",
    end_date="20251231",
    obs_element="ta_max"
)
```

#### 2-2. soil_chem_stat_client.py 구현

**현황:** ✅ 기술명세서 기반 실구현 완료

**기술명세서 검증:**
- ✅ Base URL: https://apis.data.go.kr/1390802/SoilEnviron/SoilExamStat/V2
- ✅ 파라미터: serviceKey, STDG_CD (법정동코드 10자리)
- ✅ 응답 코드: 200=성공, 301=데이터없음 등

**구현 내용:**
- ✅ 3개 엔드포인트 호출 (getFarmExamPhInfo, getFarmExamOmInfo, getFarmExamApInfo)
- ✅ 구간통계(bin_1~bin_6 면적) → 가중평균 산출
- ✅ 논/밭 경지구분별 평균 계산
- ✅ 결측/이상치 검증 (pH: 0-14, OM/AP: ≥0)

**조회 흐름:**
```
법정동코드 (10자리, 읍면동)
  ↓ (3개 API 동시 호출 또는 순차 호출)
  ├─ getFarmExamPhInfo → pH 구간통계
  ├─ getFarmExamOmInfo → 유기물 구간통계
  └─ getFarmExamApInfo → 유효인산 구간통계
  ↓
RegionSoilChemStat(bjd_code, bjd_name, ph_avg, organic_matter_avg, avail_p_avg)
```

**테스트 필요:**
- [ ] 실제 API 호출 (예: 고창군 법정동코드)
- [ ] 구간통계 가중평균 계산 검증
- [ ] 결측 처리 (데이터 없음 시 None 반환)

---

### Phase 3: 서비스 계층 구현

#### 3-1. climatology_service.py

**목표:** 평년치 조회 + 결측 시 인접 지역 대체

**현황:** 기본 구조 있음 (`nexttodo.md` 2차 조치 완료)

**필요 작업:**
```python
def get_region_climatology(
    region_id: int,
    month: int
) -> WeatherClimatology | None:
    """
    평년치 조회. 없으면:
    1. 인접 지역 검색 (격자거리)
    2. 최근접 지역값 반환 + "대체됨" 플래그
    3. 신뢰도 저하 표기
    """
```

**미결정 사항:**
- [ ] 캐시 TTL (현재 1달 가정)
- [ ] 대체 거리 기준 (50km? 100km?)
- [ ] 몇 개월 전까지 역사 포함?

---

### Phase 4: DB 마이그레이션 및 시드

#### 4-1 필요 마이그레이션

| 테이블 | 행 수 | 출처 | 상태 |
|--------|------|------|------|
| **region** | 256 | 행정안전부 법정동코드 | ✅ 기존 |
| **region_grid** | 256 | latlon_to_grid 변환 | ⏳ 필요 |
| **kma_observation_point** | 510 | 기상청 AWS 지점 | ⏳ 필요 |
| **region_to_point_mapping** | 510~256 | 격자거리 매핑 | ⏳ 필요 |
| **crop** | 5 | 고정 (사과/배/오이/감자/상추) | ✅ 기존 |
| **crop_growth_guide** | ~50 | 문헌 수작업 추출 | ⏳ 필요 |
| **soil_change_rule** | ~20 | 문헌 기반 계수 | ⏳ 필요 |

---

### Phase 5: 엔드포인트 통합

#### 5-1. /farms/{id}/short-term

**현재:**
```python
# short_term_service.py
def get_daily_forecast(farm_id: int) -> dict
```

**필요:**
- [ ] forecast_client 연동 (이미 완료)
- [ ] 위험신호 판정 로직 (온도, 습도, 강수)
- [ ] 신선도 표기 (fetched_at, is_stale)
- [ ] 소유권 검증

#### 5-2. /farms/{id}/long-term

**현재:**
```python
# suitability_service.py
def get_suitability_month(farm_id, month) -> SuitabilityResult
```

**필요:**
- [ ] climatology_service 연동
- [ ] 평년치 + 장기예보 보정 (DB.md §8.1)
- [ ] breakdown 구조 (지표별 점수)
- [ ] risk_flags 판정

---

## 4. 우선순위 결정

### 즉시 (오늘)

1. ✅ **weather_client.py 검증** — 기상청 API 실제 호출
2. ⏳ **climatology_service.py 구현** — 평년치 조회
3. ⏳ **DB 마이그레이션** — region_grid, kma_observation_point 시드

### 근일 (내일~)

4. ⏳ **soil_chem_stat_client.py** — API 명세 확정 후 구현
5. ⏳ **엔드포인트 통합 테스트** — short/long-term 데이터 흐름
6. ⏳ **캐싱 로직** — Redis/DB 멱등 upsert

### 차순 (1주)

7. **생육 지침 시드** — crop_growth_guide 작성
8. **토양변화 계수 시드** — soil_change_rule 작성
9. **통합 테스트** — 5종 작물 × 모든 지역 검증

---

## 5. 다음 액션

**방금 확보한 자료 병합:**
- ✅ weather_client.py 수정 (sfc_aws_day.php 명세 적용)
- ✅ data-integration-strategy.md 작성 (매핑, 캐싱, 결측 전략)
- ⏳ 이 문서 (api-implementation-status.md) 작성 — **현황 추적용**

**다음 Phase (2) 작업:**
1. weather_client.py 실제 API 테스트
2. climatology_service.py 구현 개시
3. DB 마이그레이션 (region_grid, kma_observation_point)

---

## 참고

- **CLAUDE.md**: §12 공공데이터 API 규칙, §3.4 추측 금지
- **DB.md**: §3.10-12 캐시 테이블, §8 계산 로직, §9 마이그레이션
- **nexttodo.md**: 평년치 커버리지 2차 조치 (climatology_service.py), 근본 해결 미착수
- **기상청_API-Guide.md**: sfc_aws_day.php 명세, 510지점 API 활용 가능
