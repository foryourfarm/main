# 데이터 파이프라인 마이그레이션 가이드

> Phase 4-5: DB 마이그레이션 적용 및 통합 테스트

---

## 📋 목차

1. [마이그레이션 적용](#마이그레이션-적용)
2. [데이터 준비](#데이터-준비)
3. [API 호출 테스트](#api-호출-테스트)
4. [End-to-End 통합 테스트](#end-to-end-통합-테스트)
5. [검증 및 배포](#검증-및-배포)

---

## 마이그레이션 적용

### 1단계: 마이그레이션 상태 확인

```bash
cd backend
alembic current
# 출력: 현재 적용된 마이그레이션 revision
```

### 2단계: 마이그레이션 적용

```bash
cd backend
alembic upgrade head
```

**예상 출력:**
```
INFO  [alembic.runtime.migration] Context impl PostgreSQLImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.migration] Running upgrade 0013 -> 0015, 기상청 관측지점 마스터 테이블
```

마이그레이션은 스키마만 만든다. 마스터 데이터는 스크립트로 적재한다:

```bash
python ../scripts/load_region_grid.py   # region_grid 256행 (기상청 격자 엑셀 산출 CSV)
python ../scripts/load_districts.py     # district 5,066행
```

> **폐기된 0014를 이미 적용한 DB라면** `alembic_version`이 존재하지 않는 리비전을 가리켜
> `upgrade`가 실패한다. `alembic stamp 0013` 후 `alembic upgrade head`, 또는 DB 재생성.
> 그리고 0014가 적재한 `region_grid` 행은 253개가 서울 격자라 반드시 지우고 다시 적재해야
> 한다: `DELETE FROM region_grid;` → `python ../scripts/load_region_grid.py`.

### 3단계: 마이그레이션 확인

```bash
# PostgreSQL 접속 또는 ORM으로 확인
python -c "
from app.db.session import SessionLocal
from app.models import RegionGrid, KmaObservationPoint

db = SessionLocal()
print(f'region_grid: {db.query(RegionGrid).count()} rows')
print(f'kma_observation_point: {db.query(KmaObservationPoint).count()} rows')
db.close()
"
```

**예상 결과:**
```
region_grid: 256 rows
kma_observation_point: 15 rows (샘플, 실제는 510)
```

---

## 데이터 준비

### region_grid 검증 (`scripts/load_region_grid.py` 적재 후)

```python
# 각 region의 격자좌표가 올바른지 확인
from app.models import Region, RegionGrid
from app.infra.public_api.kma_grid import latlon_to_grid

db = SessionLocal()
regions = db.query(Region).limit(5)
for region in regions:
    grid = db.query(RegionGrid).filter_by(region_id=region.id).first()
    if grid:
        print(f"{region.name}: nx={grid.nx}, ny={grid.ny}")
```

### 0015 마이그레이션: KMA 지점 시드 (미완)

**현재 상태:** 테이블만 존재, 0행. 샘플 15개를 마이그레이션에 박아 두던 것은 제거했다 —
부분 샘플을 마스터 데이터로 적재하면 미완성 데이터가 "완료"로 보인다(CLAUDE.md §10).

**실제 필요:** 510개 전체 지점. `district`처럼 CSV + `scripts/load_*.py` 패턴으로 적재한다.

**데이터 소싱 옵션:**

#### 옵션 A: 기상청 API (권장)
```python
# 기상청 getAwsStnLstTbl API에서 510개 지점 조회
# → CSV/JSON으로 저장 후 마이그레이션에서 로드
```

#### 옵션 B: 공개 데이터
```
국가데이터포탈 > 기상청 > AWS 지점 정보
또는 기상청 공식 문서에서 다운로드
```

#### 옵션 C: 직접 입력 (작은 규모)
```python
# 마이그레이션 파일의 sample_data를 510개로 확장
```

---

## API 호출 테스트

### 테스트 스크립트 실행

```bash
cd backend
python ../tests/test_api_clients.py
```

### TEST 1: weather_client.py 테스트

**테스트 내용:**
- 기상청 sfc_aws_day.php API 호출
- 서울(108) 2025년 1월 최고기온 조회
- XML 응답 파싱 및 데이터 검증

**예상 결과:**
```
✅ TEST 1: weather_client.py
[호출] 서울(108) 2025년 1월 최고기온
[결과] ✅ 성공!
  - 조회된 일 수: 31
  - 첫 번째 데이터:
    - 지점: 108
    - 날짜: 20250101
    - 값: 3.5
```

**실패 시 체크:**
```
- .env에 weather_data_APIkey 설정 확인
- 기상청 API 가용성 확인
- 네트워크 연결 확인
```

### TEST 2: soil_chem_stat_client.py 테스트

**테스트 내용:**
- 흙토람 화학성 통계 API 호출
- 고창군(5279000000) 화학성 통계 조회
- pH, 유기물, 유효인산 평균값 계산

**예상 결과:**
```
✅ TEST 2: soil_chem_stat_client.py
[호출] 고창군(5279000000) 화학성 통계
[결과] ✅ 성공!
  - 법정동코드: 5279000000
  - 법정동명: 전라북도 고창군
  - pH 평균: 6.2
  - 유기물 평균: 24.5%
  - 유효인산 평균: 95.3 mg/kg
```

**실패 시 체크:**
```
- .env에 chemical_status_api 설정 확인
- 국가데이터포탈 API 가용성 확인
- 흙토람 API 인증 상태 확인
```

---

## End-to-End 통합 테스트

### 테스트 시나리오: 사과 + 고창군

#### 1단계: 밭 등록

```bash
curl -X POST http://localhost:8000/api/v1/farms \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d '{
    "region_id": 1,  # 고창군 region_id (실제값 확인 필요)
    "bjd_code": "5279000000",
    "crop_id": 1,  # 사과
    "planting_date": "2025-03-15",
    "label": "고창군 사과밭"
  }'
```

**응답 예상:**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "region_id": 1,
    "crop_id": 1,
    "planting_date": "2025-03-15",
    "label": "고창군 사과밭",
    "soil_source": "흙토람 읍면동 기준"
  }
}
```

#### 2단계: 장기 탭 조회 (월별 적합도)

```bash
curl -X GET http://localhost:8000/api/v1/farms/1/monthly-outlook \
  -H "Authorization: Bearer {token}"
```

**응답 예상:**
```json
{
  "success": true,
  "data": {
    "farm_id": 1,
    "crop_id": 1,
    "region_id": 1,
    "year": 2025,
    "label": "문헌 기반 예상 적합도",
    "months": [
      {
        "month": 1,
        "growth_stage": "dormancy",
        "status": "dormant",
        "score": null,
        "grade": null,
        "risk_flags": []
      },
      {
        "month": 3,
        "growth_stage": "germination",
        "status": "ok",
        "score": 85.5,
        "grade": "A",
        "risk_flags": []
      }
      // ... 12개월
    ],
    "limitations": [
      "일 기온(temp_day)은 실측이 아니라 월평년(temp_avg_normal) 근사입니다.",
      "이 지역 평년치가 없어 가장 가까운 장성군(약 16km) 평년치로 대체했습니다 — 실제와 차이가 있을 수 있습니다.",
      "기온·강수는 평년치에 기상청 3개월전망(확률예보)을 반영해 보정했습니다. 전망이 없는 월·지표(야간최저기온·일조 등)는 평년치를 그대로 씁니다."
    ]
  }
}
```

#### 3단계: 단기 탭 조회 (당일 위험신호)

```bash
curl -X GET http://localhost:8000/api/v1/farms/1/short-term \
  -H "Authorization: Bearer {token}"
```

**응답 예상:**
```json
{
  "success": true,
  "data": {
    "farm_id": 1,
    "crop_id": 1,
    "region_id": 1,
    "target_date": "2026-07-26",
    "forecast": {
      "temp_avg": 27.5,
      "temp_night_min": 18.2,
      "rainfall": 0,
      "humidity_max": 85,
      "precip_prob_max": 10
    },
    "risk_flags": []
  }
}
```

---

## 검증 및 배포

### 최종 체크리스트

- [ ] 마이그레이션 적용 성공 (0014, 0015)
- [ ] region_grid: 256개 행 확인
- [ ] kma_observation_point: 510개 행 확인 (또는 샘플 15개)
- [ ] weather_client.py API 테스트 통과
- [ ] soil_chem_stat_client.py API 테스트 통과
- [ ] 밭 등록 API 동작
- [ ] 월별 적합도 조회 (평년치 대체 메시지 표시)
- [ ] 단기 위험신호 조회

### 배포 전 확인

```bash
# 1. 모든 테스트 실행
pytest backend/tests/

# 2. 타입 체크
mypy backend/app

# 3. 린트
ruff check backend/app

# 4. 커밋 확인
git log --oneline | head -10
```

---

## 📞 문제 해결

### 마이그레이션 오류

```
ERROR: "relation 'kma_observation_point' already exists"
→ 해결: 마이그레이션이 이미 적용됨. 다시 실행할 필요 없음.
```

```
ERROR: "INSERT ... ON CONFLICT ... does not work"
→ 해결: PostgreSQL 버전 확인 (9.5 이상 필요)
```

### API 호출 오류

```
ERROR: "resultCode: 101 - 서비스키 인증 실패"
→ 해결: .env의 API 키 확인 및 재발급
```

```
ERROR: "resultCode: 301 - 요청 데이터 없음"
→ 해결: 유효한 데이터가 없는 지역/기간. 다른 값으로 테스트
```

---

## 다음 단계

1. ✅ 마이그레이션 적용 완료
2. ✅ API 테스트 완료
3. ⏳ **FE 신뢰도 표기 구현** (provenance, is_stale)
4. ⏳ 통합 테스트 (모든 5종 작물)
5. ⏳ 배포 준비

---

**상태:** 📍 **마이그레이션 적용 및 테스트 단계**
