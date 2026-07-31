# 평년치 KNN 대체 — 검증 결과 + 구현 기록

> 작성 2026-07-30. `docs/ml/knn-imputation-backend-order.md`(지시서, 2026-07-29)의 **후속**이다.
> 지시서와 이 문서가 충돌하면 **이 문서가 우선**한다 — 지시서 작성 후 실측으로 정정된 항목이 있다.
>
> **현재 상태(2026-07-31 갱신): 검증 완료 + 본 구현 완료.**
> 남은 것은 §4-4 문서/화면 확인뿐이다. 구현 중 내린 판단 3건은 §4-6 참고.

---

## 1. 한 줄 요약

평년치가 없는 140개 지역이 **격자 최근접 1개 지역을 통째로 복사**받던 것을
**거리역수 가중 KNN(k=10)**으로 교체했다. 홀드아웃 검증에서 정규화 MAE **10.99% 개선**
(기온 +23.1%, 강수 +19.3%, 일사량 −0.8%), 예측 불가 189건 → 0건.

| | 커밋 |
|---|---|
| 검증 (`scripts/`, `docs/ml/`) | `b87f41a` |
| 구현 (`climatology_service.py`, 테스트 17종) | `0e3e34f` |

브랜치 `feat/climatology-knn` — **아직 푸시·PR 안 함.** PR 대상은 `dev`(CLAUDE.md §14).

**남은 일은 §4-4 화면 확인 하나뿐이다.**

---

## 2. 검증 결과 (완료 — 2026-07-30 실측)

산출물:
- `scripts/validate_climatology_knn.py` — 재실행 가능
- `docs/ml/climatology_knn_validation.json` — 전체 수치

**방법**: 12개월 평년치를 완비한 116개 지역을 leave-one-out 홀드아웃. 나머지 115개만으로
그 지역 값을 예측해 실측과 비교. 거리는 런타임과 동일한 `_grid_distance_km`을 import해서 사용
(다른 공식을 쓰면 검증이 런타임을 대변하지 못한다).

### 2-1. 방식별 비교

| 방식 | 정규화 MAE | 현행 대비 |
|---|---|---|
| **knn_spatial_k10** | **0.1692** | **+10.99%** ← 최선 |
| knn_spatial_k15 | 0.1699 | +10.63% |
| knn_spatial_k7 | 0.1701 | +10.52% |
| knn_spatial_k5 | 0.1715 | +9.78% |
| knn_spatial_k20 | 0.1729 | +9.05% |
| knn_spatial_k3 | 0.1754 | +7.73% |
| knn_spatial_k30 | 0.1756 | +7.63% |
| knn_spatial_k50 | 0.1795 | +5.58% |
| `nearest_1` (현행) | 0.1901 | +0.00% |
| knn_spatial_k1 | 0.1901 | +0.00% |
| knn_spatial_k115 (전체) | 0.1913 | **−0.63%** |
| sido_mean (시/도 평균) | 0.1967 | −3.47% |

**하네스를 믿을 근거 2개** — 수치보다 이게 먼저다.

1. `knn_k1`이 현행과 **소수점까지 동일**(0.1901, 필드별 MAE도 전부 일치). k=1 거리가중 KNN은
   정의상 최근접 1개 복사와 같아야 하고, 실제로 같게 나왔다 → 검증 코드가 런타임 로직을
   그대로 재현한다.
2. k를 115(전체 도너)까지 키우면 **현행보다 나빠진다**(−0.63%). 즉 k=10은 "전국 평균으로
   회귀해서 좋아 보이는" 게 아니라 실제 공간 신호가 있는 **내부 최적점**이다.
   지시서 탐색 범위(k≤10)에서는 최선이 끝단에 걸려 이 구분이 불가능했으므로 50·115까지 넓혔다.

**k=7~15가 평탄한 고원**(10.52 / 10.99 / 10.63%)이다. k=10과 k=7의 차이는 노이즈 수준이라
정밀 튜닝할 값이 아니다.

### 2-2. 필드별로는 갈린다 (중요)

| 필드 | n | 현행 MAE | k=10 MAE | 변화 |
|---|---|---|---|---|
| `temp_avg_normal` | 1200 | 0.961 ℃ | 0.739 ℃ | **+23.1%** |
| `rainfall_normal` | 1308 | 19.99 mm | 16.14 mm | **+19.3%** |
| `solar_radiation_normal` | 1342 | 1.1551 | 1.1646 | **−0.8%** |

기온·강수는 20%대로 개선되지만 **일사량은 이득이 없다**(미미하게 나쁨). 전체가 +11%로
희석된 원인이 이것이다.

→ **결정: 필드별로 k를 다르게 쓰지 않는다.** 0.8%를 얻으려고 분기 3개를 넣을 값이 아니다.
단일 k=10으로 가고, 이 트레이드오프를 여기 기록해 둔다.

### 2-3. 부수 이득 — 예측 불가 189건이 0건이 된다

현행은 도너의 **그 필드**가 NULL이면 예측 자체를 못 한다(홀드아웃 실측:
`temp_avg` 108건, `rainfall` 60건, `solar_radiation` 21건 = **189건**).
KNN은 필드별로 독립 재정규화하므로 이 값이 **0건**이 된다. 정확도와 별개인 결측 감소 효과다.

### 2-4. 한계 (숨기지 않는다)

결측이 무작위가 아니다. 평년치가 없는 140개 지역은 **농업기상 관측지점이 아예 없는 곳**이라
산간·도서 비중이 다를 수 있다. 홀드아웃은 "관측된 지역을 가려 맞히는" 오차이므로
**실제 오차는 이 수치보다 클 수 있다** `[확인 필요]`.
(`outcomes/scripts/ml/imputation.py` docstring이 같은 문제를 같은 방식으로 기록해 뒀다.)

---

## 3. 지시서에서 정정할 항목 3개

지시서(`knn-imputation-backend-order.md`)를 그대로 따르면 안 되는 부분이다.

### 3-1. 대체 대상 지역 수: 154개 → **140개**

지시서 §1은 "256개 중 154개"라 썼다. 실측(2026-07-30 DB): 평년치 보유 **116개**,
따라서 대체 경로 **140개**. 지시서 작성 후 평년치 커버리지 확장이 들어가 숫자가 변했다.

### 3-2. 실제로 옮겨지는 필드: 5개 → **3개**

지시서 §3-2는 5개 필드를 대상으로 지정했으나 DB 실측 결과:

| 필드 | 1392행 중 non-NULL |
|---|---|
| `temp_avg_normal` | 1308 |
| `rainfall_normal` | 1368 |
| `solar_radiation_normal` | 1363 |
| `temp_night_min_normal` | **0** |
| `sunlight_normal` | **0** |

뒤 2개는 **전 행 NULL**이다. 코드는 5개 필드 전부 처리해야 하지만(나중에 채워질 수 있으므로),
지금 검증할 실측이 없고 실질 효과도 없다. 검증 스크립트는 이 둘을 채점에서 제외하고
그 사실을 stdout·JSON 양쪽에 명시한다.

`sunlight_normal`이 비어 있어도 일조는 산출된다 — `_add_sunlight_to_climatology`가
`solar_radiation_normal`에서 환산한다.

### 3-3. `climatology_donor` 테이블·시드·마이그레이션은 **만들지 않는다**

지시서 §3-1·§3-2는 오프라인 시드 스크립트 + CSV + 새 테이블 + 마이그레이션 + 모델을 요구했다.
**전부 불필요하다.**

근거: 지시서 §2의 "런타임 numpy/sklearn 금지, 오프라인 계산 후 시드 적재" 제약은
다변량 KNN(sklearn 거리행렬)을 상정한 것이다. 그런데 백엔드 케이스는 **공간 거리만** 쓴다.
그리고 런타임이 **이미 그 계산을 하고 있다** — `climatology_service.py:82~96`의 `candidates`
쿼리가 평년치 보유 지역 격자를 전부 메모리에 올리고 `_grid_distance_km`으로 `min()`을 뜬다.
`min()` → `sorted()[:k]` + `1/max(d, 0.001)` 가중평균은 같은 자료로 하는 사칙연산이다.

테이블로 굳히면 오히려 손해다: 도너는 격자좌표의 결정론적 함수이므로 `region_grid`가 갱신되면
시드가 조용히 썩는다. **런타임 계산이 항상 일관된다.**

→ 파일 6개 → **파일 2개 수정 + 테스트 1개 추가**로 축소된다.

---

## 4. 작업 내역 (2026-07-31 완료)

견적 2~3시간이었고 실제도 그 범위였다. 백엔드 테스트 **254 passed + 2117 subtests**
(종전 237 + 신규 17).

### 4-1. `backend/app/services/climatology_service.py` (핵심, ~40줄)

- [x] 월별 평년치 값 객체 추가 — `WeatherClimatology` ORM 대신 담을 frozen dataclass.
      필드 5개(`temp_avg_normal`, `temp_night_min_normal`, `rainfall_normal`,
      `sunlight_normal`, `solar_radiation_normal`).
      **타입은 `Decimal | None`으로 맞춘다** — 호출부(`suitability_service.py:244~246`)가
      값을 그대로 통과시키므로 float로 바꾸면 하류 산술·직렬화 거동이 달라진다.
      가중평균은 float로 계산하고 마지막에 `Decimal`로 되돌린다.
      `SimpleNamespace` 금지(지시서 §3-2), ORM 인스턴스 조립 금지(세션에 붙으면 안 된다).
- [x] `load_climatology` 대체 분기 교체: `min(candidates)` → `sorted(...)[:k]` 후
      **월별·필드별** 가중평균. 가중치 `1/max(distance_km, 0.001)`, 그 필드를 가진 도너만
      대상으로 **재정규화**(도너 행 전체를 버리지 않는다).
- [x] 어떤 필드의 모든 도너가 결측이면 그 필드는 `None` — 값을 지어내지 않는다.
- [x] `0.0`을 결측으로 보지 않도록 `is None`으로만 판정(`_as_float` 주석의 기존 버그
      — 강원 산간 1월 평년기온 0.0℃ — 을 되살리지 말 것).
- [x] 동거리 도너는 `region_id` 작은 쪽 — 결정론(CLAUDE.md §2).
- [x] `ClimatologySource`에 `donors: tuple[tuple[str, float], ...] = ()` 추가.
      `substituted_from`/`distance_km`은 1순위 도너 값으로 **유지**(하위호환).
      frozen dataclass이므로 새 필드에 기본값 필수.
- [x] `substitution_limitation()` 문구를 k개 기준으로 갱신 — §18-4(대체 사실 표기 의무).
      "가장 가까운 {X}(약 {N}km)" → "가까운 10곳(A·B·C 외 7곳, 약 N~M km) 거리 가중 평균"
      (전부 나열하면 너무 길어 §4-6-1대로 조정).
- [x] 폴백(§18-5): 도너가 1개뿐이면 자동으로 현행과 동일한 동작이 된다(k=1). 도너가 0개면
      지금처럼 빈 `ClimatologySource`. **별도 폴백 분기를 만들 필요가 없다** — 시드가 없으니
      "시드 부재 폴백"(지시서 §2)도 해당 없음.

### 4-2. 타입힌트 갱신 — 영향 범위는 좁다 (전수 확인 완료)

`by_month`를 소비하는 곳은 **3군데뿐**이다:

| 위치 | 무엇 |
|---|---|
| `climatology_service.py:154` | 내부 — 일조 환산이 `solar_radiation_normal`·`sunlight_normal` 읽음 |
| `suitability_service.py:313` | 단일월 경로 → `gather_indicator_values(clim, ...)` |
| `suitability_service.py:462` | 시즌 커리큘럼 경로 → `:416` → 같은 함수 |

읽히는 속성은 `suitability_service.py:241,244,245,246`의 4개 + 일조 환산의 `solar_radiation_normal`.
즉 **값 객체가 이 5개 속성만 가지면 호출부 수정이 필요 없다.**

- [x] 타입힌트 3곳: `climatology_service.py:44`, `suitability_service.py:225`, `:394`.
      Protocol을 새로 만들지 말고 **유니온 별칭 한 줄**로 끝낸다
      (`ClimatologyMonth = WeatherClimatology | MonthlyNormals`).
      기존 테스트(`test_farm_suitability.py:14`, `test_monthly_outlook.py:35`)는 실제
      `WeatherClimatology`를 넘기므로 유니온이면 그대로 통과한다.

### 4-3. `backend/tests/test_climatology_knn.py` (신규, ~150줄)

지시서 §3-4의 7종. 순수 계산부는 DB 없이(기존 `test_climatology_service.py` 스타일).

- [x] 1. 가중평균 손계산 일치 (도너 2개, 10km·20km → 가중 2:1)
- [x] 2. 도너 하나가 특정 필드만 결측 → 그 필드만 재정규화, 다른 필드는 두 도너 다 사용
- [x] 3. 모든 도너가 결측인 필드는 `None`이고 예외 없음
- [x] 4. `0.0` 평년기온이 결측으로 떨어지지 않음 (회귀 테스트)
- [x] 5. 도너가 1개뿐이면 현행과 동일 결과 (k=1 축퇴)
- [x] 6. 같은 입력 2회 호출 결과 동일 (결정론)
- [x] 7. `substitution_limitation()` 문구가 도너를 밝힘 — 3곳 이하면 전부, 그 이상이면
     상위 3곳 + 개수 + 거리 범위(§4-6-1). 문구 길이 상한도 함께 고정.

### 4-4. 문서

- [x] FE 인계 문서 — **갱신 불필요로 판정**. API 계약은 `limitations: string[]` 그대로이고
      `donors`를 응답에 싣지 않았다(§4-6-3). `docs/long-term-tab-api.md`는 문구 내용을
      인용하지 않고 "`limitations`를 반드시 병기하라"만 규정하므로 계약 변화가 없다.
      **바뀐 것은 배열 안 문자열의 내용뿐이다.**
- [ ] **남은 것**: 한계 문구가 화면에 실제로 노출되는지 눈으로 확인.
      텍스트만 바꾸고 화면 확인을 빠뜨리면 §18-4 위반이다.
      확인 대상: 장기 탭 + 대시보드 밭 카드(`docs/long-term-tab-api.md:105` — 접어두지 말 것).

### 4-5. 착수하지 않을 것 (범위 밖)

- `station_service.py` 최근접 관측소 매핑 — 관측소는 "값"이 아니라 "지점 식별자"를 고르는
  문제라 가중평균이 성립하지 않는다. 관측소에서 가져온 **값**을 섞을지는 별도 결정 사항
  `[확인 필요]`, **사용자 확인 전 착수 금지**(지시서 §4).
- 적합도 채점 곡선 `suitability_service.py` — 2026-07-27에 이미 개정됨.
- `outcomes/` 전체 — ML 팀원(`dotoe1234-pixel`) 담당.

### 4-6. 구현 중 내린 판단 3건 (계획과 다름)

**1. 한계 문구는 도너를 3곳만 이름으로 밝힌다** — 계획 §4-3 테스트 7은 "도너 지역명이 전부"를
요구했으나, k=10 실측 문구가 이렇게 나왔다:

```
이 지역 평년치가 없어 가까운 10곳(고양시덕양구·양주시·시흥시·김포시·파주시·광주시·
옹진군·포천시·용인시처인구·양평군, 약 16~46km)의 평년치를 거리 가중 평균했습니다 — ...
```

200자가 넘어 화면에서 읽히지 않는다. 지시서가 이 요구를 쓸 땐 k=5를 상정했다.
가중치가 거리역수라 가까운 곳이 가장 크게 기여하므로 **상위 3곳만 이름으로 밝히고
나머지는 "외 N곳"으로 요약**하되, **섞은 곳의 수와 거리 범위는 반드시 남긴다**(92자).
근사 규모를 감추지 않으므로 §18-4를 만족한다. 상수 `LIMITATION_NAMED_DONORS = 3`.
문구 길이 상한(<130자)을 테스트로 고정했다.

**2. 일조 환산 위도가 도너 → 대체받는 지역 자신으로 바뀌었다** — 종전 코드는
`_add_sunlight_to_climatology(db, source, best_grid.region_id)`로 **도너의** 위도를 썼다.
k개를 섞는 지금은 "그 도너"가 존재하지 않으므로 선택이 강제됐고, 가조시간은 값이 아니라
**위치**의 함수이므로 대체받는 지역 자신의 위도가 맞다.
→ 140개 지역의 일조 추정치가 이 변경으로도 함께 움직인다. 의도된 정정이다.

**3. `donors`를 API 응답에 싣지 않았다** — 내부 `ClimatologySource`에는 전체 목록이 있지만
노출하지 않는다. 현재 계약은 `limitations: string[]`뿐이고 FE가 펼치기 UI를 요구한 적이
없다(YAGNI). 필요해지면 `source.donors`에서 꺼내면 되고, 그때 FE 계약 문서를 갱신한다.

부수로 `_rank_donors()`를 함수로 분리했다 — 동거리 tie-break가 결정론 주장(§2)인데
`load_climatology` 안에 인라인이라 DB 없이 검증할 방법이 없었다. CI에 Postgres가 없으므로
(§6) 테스트 가능성이 곧 검증 가능성이다.

---

## 5. 담당자 판단

**이 작업은 ML 작업이 아니다.** 백엔드 작업이다.

- `climatology_service.py` 작성자는 `kwon dohyun`(2026-07-25 대체 로직 도입) + `kkugit2`(2026-07-26 결함 수정).
  ML 팀원은 이 파일을 건드린 적이 없다.
- 런타임에 numpy/sklearn을 쓰지 않는다. 하는 일은 거리 정렬 + 가중평균, 사칙연산이다.
- ML다운 부분(다변량 상관, sklearn 거리행렬)은 `outcomes/`에서 이미 끝났고
  **백엔드로 넘어오지 않는다** — 예측인자가 공간뿐이라 성립하지 않는다.
- ML 팀원이 필요한 지점은 k 선택 방식 **리뷰** 뿐이다. 구현은 아니다.

### outcomes/ 결과를 받아오면 되는 게 아닌 이유

`backend/app`에서 `outcomes`를 참조하는 코드는 **0건**이다(주석 1줄뿐).
outcomes 결과가 백엔드로 오는 경로는 사람이 손으로 옮기는 것이다 — 직전 사례(`7f28875`, 산포도)는
`outcomes/memory/indicator_dispersion.json` → 마이그레이션 `0020` → 룰 엔진 순으로 들어왔다.

게다가 **대체 대상이 다르다**: outcomes는 시군구 150지역의 토양 화학성 원시 피처(다변량),
백엔드는 256지역의 12개월 평년치 3~5필드(공간 전용). 도너 목록을 복사해도 백엔드가 채워야 하는
월별 필드를 못 채운다. 지시서 §5가 outcomes를 "참고 구현"으로만 지정한 이유다.

---

## 6. 재현 방법

DB는 로컬 docker다(`docker-compose.yml`, `pgvector/pgvector:pg16`).
2026-07-30 시점 볼륨에 데이터가 들어 있고 마이그레이션은 `0021`(최신)까지 적용돼 있다.

```bash
docker compose up -d                              # foryourfarm-db
pip install "psycopg[binary]"                     # 로컬에 드라이버가 없으면
python scripts/validate_climatology_knn.py        # → docs/ml/climatology_knn_validation.json
```

백엔드 테스트: `cd backend && python -m pytest tests -q`
→ **254 passed + 2117 subtests** (교체 전 237 + 신규 17).
CI가 PR·머지마다 같은 명령을 돈다(`.github/workflows/ci.yml`).

신규 테스트만: `python -m pytest tests/test_climatology_knn.py -q` — DB 없이 돈다.

대체 결과를 눈으로 보려면(DB 필요):

```python
from app.db.session import SessionLocal
from app.services.climatology_service import load_climatology, substitution_limitation
db = SessionLocal()
s = load_climatology(db, 1)           # region.id=1 종로구 — 자기 평년치 없는 지역
print(substitution_limitation(s))     # 도너 10곳, 약 16~46km
print(s.donors)                       # 전체 목록(이름, 거리km)
```

---

## 7. 다음에 할 일

이 작업은 끝났다(화면 확인 §4-4 제외). 이어서 할 가치 순서 — `CI_report.md` §8과 일부 중복:

0. **이 브랜치 화면 확인 후 `dev`로 PR.** 140개 지역의 장기 탭 점수가 실제로 움직이므로
   머지 전에 한 지역이라도 화면에서 보는 게 맞다.
1. **`dev` 브랜치 보호 규칙** — CI가 있어도 빨간불 PR을 머지할 수 있다. 저장소 admin 권한 보유 확인됨.
2. **HTTP 엔드포인트 테스트** — TestClient 기반 테스트가 **0건**이다. 배선 회귀를 아무도 못 잡는다.
3. `temp_night_min_normal`·`sunlight_normal` 적재 — 지금 DB 전 행 NULL이라(§3-2) 대체 코드가
   다루긴 해도 실질 효과가 없다. 채워지면 KNN 이득이 그 두 필드로도 확장된다.
