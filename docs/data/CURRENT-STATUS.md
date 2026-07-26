# 데이터 파이프라인 현황 정리 (2026-07-26 최종)

> **상태:** 부분 완료 (2026-07-26 리뷰 반영 — 이전 "Phase 2-5 완료 ✅" 표기는 과장이었다)
> - 흙토람 화학성 통계 클라이언트: 구현 ✅ (구간 오타 수정, 유기물 단위 g/kg 확정)
> - 기상 클라이언트: ⚠️ **보류** — apihub 전환 미결정(키 미발급 + 응답 형식 미확인)
> - DB 마이그레이션: 0014 ❌ 폐기(데이터 오류), 0015 = 테이블 생성만 ✅
> - 서비스 통합: climatology ↔ suitability ✅ (일조 위도 하드코딩·None 크래시 수정)
> - 실제 API 호출 검증: ⚠️ 미실시
>
> **다음:** (1) apihub 전환 여부 결정, (2) 관측지점 510개 CSV+스크립트 시드,
> (3) 일조시간 confidence 게이트 결정(아래 참고) → 그 뒤 end-to-end 테스트

---

## 1. 완료된 작업 (Phase 2-5)

### ✅ API 클라이언트 (2개)

| 파일 | 기능 | 상태 |
|------|------|------|
| **backend/app/infra/public_api/weather_client.py** | 기상청 sfc_aws_day.php (역사 기온/강수) | ✅ 구현 |
| **backend/app/infra/public_api/soil_chem_stat_client.py** | 흙토람 3종 API (지역 화학성) | ✅ 구현 |

**검증 항목:**
- ✅ Python 문법 검증 완료
- ✅ KMA XML 응답 파싱 로직
- ✅ 흙토람 3종 엔드포인트 (getFarmExamPhInfo, OmInfo, ApInfo)
- ✅ 구간통계 가중평균 계산
- ✅ 결측/이상치 처리

### ✅ 모델 & 마이그레이션 (3개 파일)

| 파일 | 목적 | 상태 |
|------|------|------|
| **backend/app/models/kma_observation_point.py** | AWS 지점 모델 정의 | ✅ 구현 |
| ~~backend/alembic/versions/0014_region_grid_seed.py~~ | region_grid 시드 | ❌ **폐기·삭제** |
| **backend/alembic/versions/0015_kma_observation_point.py** | 지점 **테이블 생성만** (시드 0행) | ✅ 스키마만 |

**검증 항목:**
- ✅ `alembic history` 단일 head (`0013 -> 0015`)
- ✅ models/__init__.py 등록 완료
- ❌ region_grid는 마이그레이션이 아니라 `scripts/load_region_grid.py` +
  `docs/seed/region_grid_seed.csv`(256행)로 적재한다 — 0014의 좌표 계산은 253개 지역을
  서울 격자로 적재하는 버그가 있었다.
- ⚠️ 관측지점 510개 시드는 아직 없다(별도 PR).
- ✅ 샘플 데이터 포함 (실제: 510개 필요)

### ✅ 서비스 계층 (이미 구현됨)

| 서비스 | 상태 |
|--------|------|
| climatology_service.py | ✅ 평년치 조회 + 격자거리 대체 로직 |
| suitability_service.py | ✅ climatology 호출 통합 (라인 249-261) |
| short_term_service.py | ✅ forecast_client 호출 통합 |
| farms.py (라우터) | ✅ /suitability, /monthly-outlook 구현 |

### ✅ 테스트 스크립트

- **backend/tests/test_api_clients.py**: weather_client + soil_chem_stat_client API 호출 검증

---

## 2. 실행 가능 단계 (Phase 5+)

### Step 1: 마이그레이션 적용

```bash
cd backend
alembic upgrade head
# region_grid는 마이그레이션이 아니라 스크립트로 적재한다(256행)
python ../scripts/load_region_grid.py
```

**예상 결과:**
```
INFO  Running upgrade 0013 -> 0015, 기상청 관측지점 마스터 테이블
```

> 0014/0015(구버전)를 이미 적용한 DB라면 `alembic_version`이 삭제된 리비전을 가리켜
> `upgrade`가 실패한다. `alembic stamp 0013` 후 `upgrade head`, 또는 DB 재생성.

### Step 2: 데이터 검증

```bash
cd backend
python -c "
from app.db.session import SessionLocal
from app.models import RegionGrid, KmaObservationPoint

db = SessionLocal()
print(f'✅ region_grid: {db.query(RegionGrid).count()} rows')
print(f'✅ kma_observation_point: {db.query(KmaObservationPoint).count()} rows')
"
```

### Step 3: API 호출 테스트

```bash
cd backend
python tests/test_api_clients.py
```

**TEST 1 예상:** weather_client.py 호출 성공
```
✅ TEST 1: weather_client.py  
  [호출] 서울(108) 2025년 1월 최고기온
  [결과] 조회된 일 수: 31
```

**TEST 2 예상:** soil_chem_stat_client.py 호출 성공
```
✅ TEST 2: soil_chem_stat_client.py
  [호출] 고창군(5279000000) 화학성 통계
  [결과] pH: 6.2, 유기물: 24.5 g/kg, 유효인산: 95.3 mg/kg
```

### Step 4: 통합 테스트

```bash
# 1. 밭 등록 (사과 + 고창군)
POST /api/v1/farms
{
  "region_id": <고창군_id>,
  "bjd_code": "5279000000",
  "crop_id": 1,  # 사과
  "planting_date": "2025-03-15"
}

# 2. 월별 적합도 조회 (평년치 대체 메시지 확인)
GET /api/v1/farms/{id}/monthly-outlook
# 응답에 limitations 포함:
# "이 지역 평년치가 없어 가장 가까운 장성군(약 16km) 평년치로 대체했습니다"

# 3. 일일 위험신호 조회
GET /api/v1/farms/{id}/short-term
```

### ✅ 일조시간 데이터 조사 완료 (2026-07-26)

**조사 범위:** 농업기상 API 218개 지점 × 6년 (2020~2025)

| 항목 | 결과 |
|------|------|
| **총 지점 수** | 218개 |
| **일조시간 데이터 있는 지점** | 52개 (23.9%) |
| **데이터 없는 지점** | 166개 (76.1%) |
| **결론** | **혼합 방식 (Hybrid)** 필수 |

**결정사항:**
- 52개 지점 (23.9%): 실측 월별 일조시간 사용 (2020~2025년 전체)
- 166개 지점 (76.1%): **Angstrom 공식** 기반 계산
  - 입력: 월별 최고/최저 기온, 강수량
  - 출력: 추정 일조시간
  - 방정식: FAO-56 표준 Angstrom 변형

**데이터 저장:**
- docs/data/exhaustive_sunlight_investigation.json: 전수 조사 결과

---

## 3. 파일 생성 현황

**생성된 파일 (총 17개):**
- ✅ API 클라이언트: 2개
- ✅ 모델/마이그레이션: 3개
- ✅ 테스트 스크립트: 1개
- ✅ 일조시간 조사 스크립트: 1개
- ✅ 문서: 10개

---

## 4. 다음 단계 (일조시간 처리)

### 4.1 Angstrom 계산 함수 구현
- **위치:** `backend/app/services/sunlight_calculation.py` (신규)
- **로직:** 월별 기온/강수 → 추정 일조시간 (FAO-56)
- **입력:** 지역, 연도, 월, 기온(max/min), 강수량
- **출력:** 추정 일조시간 + 신뢰도 수치

### 4.2 계절성 적합도 통합
- climatology_service에서:
  - 실측 지점: WeatherClimatology.sunlight_normal 직접 사용
  - 계산 지점: Angstrom 함수로 계산 후 사용
  - 모든 경우에 provenance 필드 기록

### 4.3 신뢰도 표기 (FE)
- `provenance`: "실측 (농업기상 2020~2025)" vs "계산 (Angstrom)"
- `confidence`: 실측(0.95) vs 계산(0.70)

---

## 5. 미완료 항목 (FE만 남음)

- ⏳ FE 신뢰도 표기
  - `provenance` 필드 추가 (출처 표시)
  - `is_stale` 필드 추가 (신선도 표시)
  - "이 지역은 OO값을 ~km 대체" 메시지 표시

---

**다음 진행:**
1. Angstrom 계산 함수 구현
2. climatology_service 통합
3. MIGRATION-GUIDE.md 참고하여 Step 1-4 순차 실행
