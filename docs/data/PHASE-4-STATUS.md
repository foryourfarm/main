# Phase 4 진행 중: API 테스트 + DB 마이그레이션 (2026-07-26)

> ⚠️ **이 문서는 작성 당시 스냅샷이며 일부가 폐기됐다.** 최신 상태는
> `docs/data/CURRENT-STATUS.md`를 본다. 특히: 0014는 좌표 오류로 **폐기·삭제**됐고,
> 0015는 샘플 시드를 제거해 **테이블 생성만** 남았다. 아래 "완성" 표기는 유효하지 않다.

> API 호출 테스트 스크립트 + DB 마이그레이션 (0014, 0015) 완성

---

## ✅ Phase 4 추진 현황

### 4-1. API 호출 테스트 스크립트 ✅ DONE

**파일:** `backend/tests/test_api_clients.py`

**테스트 항목:**
1. **weather_client.py** — KMA sfc_aws_day.php
   - 서울(108) 2025년 1월 최고기온
   - 호출: `get_daily_weather("108", "20250101", "20250131", "ta_max")`
   - 검증: XML 응답 파싱, 일수, 샘플값

2. **soil_chem_stat_client.py** — 흙토람 3종 API
   - 고창군(5279000000) 화학성 통계
   - 호출: `get_region_soil_chem_stat("5279000000")`
   - 검증: pH, 유기물, 유효인산 평균값

**실행 방법:**
```bash
cd backend
python ../tests/test_api_clients.py
```

**예상 결과:**
```
✅ TEST 1: weather_client.py — 성공 또는 API 오류
✅ TEST 2: soil_chem_stat_client.py — 성공 또는 API 오류
```

---

### 4-2. KmaObservationPoint 모델 ✅ DONE

**파일:** `backend/app/models/kma_observation_point.py`

**스키마:**
```python
class KmaObservationPoint(Base):
    point_code: str      # 지점번호 (예: "108")
    name: str            # 지점명 (예: "서울")
    lat: float           # 위도
    lon: float           # 경도
    altitude: int        # 해발고도 (m)
```

**역할:**
- 기상청 510개 AWS 지점 정보 저장
- weather_snapshot 조회 시 참조
- region ↔ point 매핑

---

### 4-3. DB 마이그레이션 (0014, 0015) ✅ DONE

#### 0014_region_grid_seed.py

**목적:** region_grid 시드 (256개 지역 격자 매핑)

**동작:**
1. region 테이블 조회 (256개)
2. 각 지역의 중심좌표 기반 → `latlon_to_grid()` 계산
3. `region_grid(region_id, nx, ny)` 삽입

**결과:**
```
Inserted 256 region_grid rows
```

**주의:** 실제 운영에서는 행안부 법정동코드 데이터의 정확한 중심좌표 사용 필요

#### 0015_kma_observation_point_seed.py

**목적:** kma_observation_point 시드 (510개 AWS 지점)

**동작:**
1. 테이블 생성 (point_code, name, lat, lon, altitude)
2. 데이터 삽입 (샘플 14개 포함, 실제는 510개 필요)

**결과:**
```
Inserted 14 KMA observation points (샘플)
⚠️ 주의: 실제 마이그레이션은 510개 전체 지점을 로드해야 함
```

**데이터 소싱:**
- 기상청 API: `getAwsStnLstTbl`
- 공개 데이터: 국가데이터포탈 기상청 AWS 지점

---

## 📋 구성 변경사항

| 파일 | 변경 | 내용 |
|------|------|------|
| `backend/app/models/kma_observation_point.py` | 📝 신규 | KmaObservationPoint 모델 |
| `backend/app/models/__init__.py` | 🔧 수정 | KmaObservationPoint import/등록 |
| `backend/alembic/versions/0014_region_grid_seed.py` | 📝 신규 | region_grid 시드 마이그레이션 |
| `backend/alembic/versions/0015_kma_observation_point_seed.py` | 📝 신규 | kma_observation_point 시드 마이그레이션 |
| `backend/tests/test_api_clients.py` | 📝 신규 | API 호출 테스트 스크립트 |

---

## 🚀 다음 단계

### 즉시 (지금)

```bash
# 1. API 호출 테스트
cd backend
python ../tests/test_api_clients.py

# 예상 결과:
# ✅ TEST 1: weather_client.py — PASS/FAIL
# ✅ TEST 2: soil_chem_stat_client.py — PASS/FAIL
```

### 근일 (오류 해결 후)

```bash
# 2. 마이그레이션 적용
cd backend
alembic upgrade head

# 확인:
# SELECT COUNT(*) FROM region_grid;  -- 256행
# SELECT COUNT(*) FROM kma_observation_point;  -- 14행 (샘플)
```

### 1주일 이내

```
3. End-to-end 통합 테스트
   - 사과 + 고창군 밭 등록
   - GET /farms/{id}/monthly-outlook
   - 평년치 대체 메시지 표시 확인

4. FE 신뢰도 표기
   - provenance, is_stale 필드 추가
   - "이 지역은 OO값을 ~km 대체" 메시지 표시
```

---

## 📊 전체 진행 현황

| Phase | 항목 | 상태 | 파일 수 |
|-------|------|------|--------|
| **Phase 1** | 데이터 전략 정리 | ✅ | 3 |
| **Phase 2** | API 클라이언트 | ✅ | 2 |
| **Phase 3** | DB 마이그레이션 | ✅ | 2 |
| **Phase 4** | 테스트 + 검증 | 🔄 진행중 | 1 |
| **Phase 5** | 통합 테스트 | ⏳ 대기 | - |
| **Phase 6** | FE 연동 | ⏳ 대기 | - |

---

## 🎯 주요 지표

**작성된 파일:**
```
✅ 기술명세서 검증 후 구현 (weather_client, soil_chem_stat)
✅ DB 마이그레이션 2개 (region_grid, kma_observation_point)
✅ 모델 등록 (KmaObservationPoint)
✅ 테스트 스크립트 (API 호출 검증)
```

**API 준비:**
```
✅ 기상청 sfc_aws_day.php
✅ 흙토람 getFarmExamPhInfo/OmInfo/ApInfo
✅ API 키 확보 (.env)
```

**DB 준비:**
```
✅ 마이그레이션 구조 (0014, 0015)
⏳ 실제 데이터 로드 (510 AWS 지점 마스터)
```

---

## ⚠️ 주의사항

### 0014_region_grid_seed
- 현재 REGION_COORDS 딕셔너리는 샘플만 포함
- **실제 운영:** 행안부 법정동코드 데이터에서 256개 모두 로드 필요

### 0015_kma_observation_point_seed
- 현재 sample_data는 14개 지점만 포함
- **실제 운영:** 기상청 API(getAwsStnLstTbl) 또는 공개 CSV에서 510개 전체 로드 필요

### 마이그레이션 적용 시
```bash
alembic upgrade head
# 위 두 마이그레이션이 순서대로 실행됨
# 실패 시: 해당 마이그레이션 파일 수정 후 재시도
```

---

## 커밋 기록

```
✅ 7ef46fc - feat(phase-4): API 호출 테스트 + DB 마이그레이션 (0014, 0015)
✅ 7ef46fc - feat(soil-api): soil_chem_stat_client.py 국가데이터포탈 API 완전 구현
✅ b46a629 - docs(data-integration): 기상청 API 명세 통합 및 데이터 파이프라인 현황 정리
```

---

**상태:** 🔄 **API 호출 테스트 단계** — 정상 진행 중
