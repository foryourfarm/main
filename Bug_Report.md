# Bug Report — `feature/ui-ux` 백엔드 리뷰 대응

- **작성일**: 2026-07-26 (2차 갱신: 기술명세서 반영 + 일조시간 정확도 재구성)
- **대상 브랜치**: `feature/ui-ux` (커밋 `408f96e`, `7ef46fc`, `d771442` 범위)
- **범위**: 백엔드만. 프론트엔드 4건(`layout.tsx`, `globals.css`, `chat/page.tsx`, `chat.module.css`)은 해결된 것으로 확인돼 손대지 않았다.
- **검증 결과**: 테스트 **151 → 195개 통과** (실패 0), `alembic heads` 단일 head(`0016`), `import app.main` 정상, 실제 공공 API 호출 성공.
- **커밋 상태**: 스테이징만 완료, 커밋하지 않음.

> **표기 규칙**: 위키링크로 표시된 파일은 **사람이 확인/결정해야 하는 것**이다.
> 링크가 없는 항목은 수정과 검증이 끝나 추가 조치가 필요 없다.
> 남은 확인 필요 파일은 2개다 — §8에 모아 두었다(1차 4개 → 2개로 감소).

---

## 1. 요약

### 1차: 코드 리뷰 대응

| # | 심각도 | 대상 | 처리 | 상태 |
|---|--------|------|------|------|
| 1 | 🔴 | `0014_region_grid_seed.py` | 폐기·삭제 | 완료 |
| 2 | 🔴 | `0015_kma_observation_point_seed.py` | 시드 제거, 테이블 생성만 | 완료(시드는 별도 PR) |
| 3 | 🔴 | `weather_client.py` `AttributeError` | 되돌림 → **2차에서 V3 명세로 재작성** | 완료 |
| 4 | 🟠 | `suitability_service.py:275` TypeError | 루트 원인 수정(항상 dict) | 완료 |
| 5 | 🟠 | 일조 위도 하드코딩 `37.0` | 격자 역변환으로 대체 | 완료 |
| 6 | 🟠 | 월별 히트맵 일조 정합성 | `clim_source` 전달 | 완료 |
| 7 | 🟠 | `soil_chem_stat_client.py` 버그 3건 | 전부 수정 | 완료 |
| 8 | 🟡 | `.env.example` 삭제됨 | 복원 → **2차에서 루트로 통합** | 완료 |

### 2차: 기술명세서 반영 + 일조시간 정확도

| # | 심각도 | 대상 | 처리 | 상태 |
|---|--------|------|------|------|
| 9 | 🔴 | `base.py` 헤더 태그 대소문자 | **흙토람 통계 API가 100% 실패 중이었다** → 대소문자 무시 | 완료 |
| 10 | 🔴 | 개방구간 대표값 폭주 | 유효인산 2008 mg/kg → 309 (현실화) | 완료 |
| 11 | 🔴 | 일조시간 정확도 R²=0.25 | 일사량 기반으로 재구성 → **R²=0.903** | 완료 |
| 12 | 🔴 | 프로덕션에서 일조가 도달 불가 | 일사량 평년 컬럼 추가(`0016`) | 완료 |
| 13 | 🟠 | `weather_client.py` 명세 불일치 | V3 명세로 재작성 + 실호출 검증 | 완료 |
| 14 | 🟡 | env 위치 이원화 | 루트 `.env` 단일화 | 완료 |

**순 변화**: 30개 파일, +1,462 / −1,012.

---

## 2. env 단일화 (지시사항 ①)

리포 루트의 `.env`를 쓰도록 정리했다.

- `config.py`의 `env_file`을 `(루트/.env, backend/.env)` 2개 → **루트 `.env` 하나**로 축소. 두 곳을 읽으면 어느 값이 이겼는지 알 수 없고, 실제로 한쪽에만 키를 넣어 빈 문자열이 되는 사고가 있었다.
- `.env.example`을 `backend/` → **루트**로 이동(실제 `.env`와 같은 위치).
- `README.md`의 `backend/.env` 안내를 루트로 수정.

**실측 확인**: 루트 `.env`가 `chemical_status_API = ...` 형식(공백·혼합 대소문자)인데도 pydantic이 정상 로드한다 — 7개 키 중 **6개 로드 성공**. `VWORLD_API`만 비어 있다.

> `.env`에는 `fertilizer_API`, `crop_code_API`도 있으나 `config.py`에 대응 필드가 없어 무시된다(`extra="ignore"`). 쓸 곳이 생기면 필드를 추가해야 한다.

---

## 3. 🔴 기술명세서 대조로 찾은 신규 버그 (지시사항 ②)

### ① `base.py` — 흙토람 통계 API가 **모든 호출에서 실패**하고 있었다

명세서(`농경지화학성-통계정보_V2_API기술명세서.md`)의 응답 헤더는 `result_Code`(소문자 r)인데, `fetch_items`의 기본값은 `Result_Code`(대문자 R)였다. `ElementTree`는 대소문자를 구분하므로 `findtext`가 `None`을 반환하고, `None != "200"`이라 **성공 응답이 전부 에러로 둔갑**했다.

실제 호출로 확인:

```
수정 전: RAISED PublicApiError [UNKNOWN] 알 수 없는 오류
수정 후: 전북특별자치도 고창군  pH=5.75  OM=19.6 g/kg  AP=308.9 mg/kg
```

같은 data.go.kr 안에서도 제공기관마다 케이스가 다르다 — 토양특성 단면정보·토양검정은 `Result_Code`, 농경지화학성 V2와 농업기상 V3은 `result_Code`다. 호출부마다 케이스를 외우게 하는 대신 `base.py`의 `_header_text()`가 **대소문자를 무시**하도록 한 곳에서 흡수했다.

> **왜 1차 리뷰와 제 유닛테스트가 둘 다 놓쳤나**: 테스트가 `fetch_items`를 모킹해서 계약 불일치가 보이지 않았다. 모킹 경계 바로 안쪽의 버그는 모킹으로 검증할 수 없다.

### ② 구간통계 개방구간 대표값이 비현실적

`(601, 9999)` 같은 이론 상한을 중점으로 쓰면 값이 폭주한다. 고창군 밭 유효인산 최상단 구간(601이상)이 6,765ha로 가장 넓은데 상한 9999를 쓰면 중점이 5300이 되어 지역 평균이 **2008 mg/kg**으로 나왔다(한국 밭 실제 평균 400~600).

→ 개방구간은 **직전 구간과 같은 폭**을 가정해 대표값을 잡는다(구간자료 평균 산출의 통상 관례).

실측 검증 — 값이 현실 범위로 들어왔고, **제주 유기물 43.6 g/kg**은 화산회토의 높은 유기물 특성과 일치하는 강한 검증 신호다:

| 지역 | pH | 유기물 | 유효인산 |
|---|---|---|---|
| 전북 고창군 | 5.75 | 19.6 g/kg | 308.9 mg/kg |
| 경북 고령군 | 5.83 | 19.0 g/kg | 363.2 mg/kg |
| 경북 경주시 | 5.87 | 26.5 g/kg | 316.3 mg/kg |
| 제주 서귀포시 | 5.75 | **43.6 g/kg** | 175.0 mg/kg |

### ③ `weather_client.py` — 명세와 전부 불일치 → V3로 재작성

| 항목 | 기존(placeholder) | 명세서 실제 |
|---|---|---|
| Base URL | `.../AgriWeather/WeatherObsrInfo/GnrlWeather/getWeatherDataList` | `.../WeatherObsrInfo/`**`V3`**`/GnrlWeather` |
| 지점 | `Site` | `obsr_Spot_Cd` |
| 필드 | `stnCode`, `obsDate`, `avgTemp`, `sumRn` | `stn_Cd`, `stn_Name`, `date`, `temp`, `hghst_Artmp`, `lowst_Artmp`, `hum`, `rn`, `sun_Time`, `srqty` |

실제 호출로 응답을 확인하고 재작성했다. 명세서에 **단위 표기가 없던 `sun_Time`을 실측 분포로 확정**했다: 최대 793 → 시간 단위면 불가능하고 **분으로 보면 13.2h**로 국내 최대 가조시간과 맞는다. `condens_Time` 757(=12.6h)도 분 단위로 정합.

```
포천시 영북면  2024-07-01 temp=24.4 max=29.6 min=21.3 hum=80.6 rn=0.0 rad=16.44
일조 보유 13/50  최대 일조시간=11.22h   ← 7월 맑은 날로 타당
```

apihub(`기상청_API-Guide.md`) 전환은 **하지 않았다** — `sfc_aws_day.php`의 `obs` 요소에 일조·일사가 없어 우리 목적에 맞지 않고, 별도 인증키도 필요하다. 다만 `getAwsStnLstTbl`이 510개 지점의 `lat`/`lon`/`ht`를 주므로 §8-3의 지점 시드에 쓸 수 있다.

---

## 4. 🔴 일조시간 정확도 재구성 (지시사항 ③)

### 문제: 기존 구현은 정확도가 R²=0.25였고, 애초에 프로덕션에서 실행될 수 없었다

두 개의 독립적인 결함이 겹쳐 있었다.

1. **정확도**: 기존 계수(`a=0.16, b=0.10`)를 실측 검증하니 **MAE 2.99시간 / R²=0.252**. 선언된 `confidence=0.70`은 근거가 없었다.
2. **도달 불가**: ETL(`scripts/load_weather_climatology.py`)이 `sunlight_normal`과 `temp_night_min_normal`을 **둘 다 NULL**로 넣는다. 실측 경로도 기온 경로도 발동할 수 없어 `sunlight_by_month`는 항상 비어 있었다.

### 해결: 일사량(`srqty`) 기반 역 Ångström–Prescott

농업기상 V3가 **일사량을 준다**. 일사량은 물리적으로 일조시간과 직결되므로(구름이 가리면 둘이 함께 준다) 기온 추정보다 압도적으로 정확하다.

```
Rs/Ra = a + b·(n/N)   →   n = N·((Rs/Ra) − a)/b
```

`Ra`(지구외 일사량)와 `N`(가조시간)은 위도·연중일자만으로 **정확히** 계산된다(FAO-56 Eq.21/34). 따라서 오차는 계수와 일사량 실측 오차에서만 온다.

### 정확도를 끌어올린 결정적 요인은 계수가 아니라 **경계 검증**이었다

처음 회귀했을 때 R²는 0.742에 그쳤다. 원인을 진단하니 데이터 품질 문제였다:

- `Rs/Ra > 0.85`인 행이 224개 — 물리적으로 불가능하다(청천 상한 ≈0.78). 최대값이 **2.46**이었다.
- 지점별로 회귀해 보니 **65개 중 5개가 센서 고장**(R² 0.01~0.16, 기울기가 음수이거나 0). 정상 60개는 R²≥0.7이고 최상위 5개는 **0.95~0.96, 기울기 0.56~0.58**로 FAO 이론값과 정확히 일치했다.

두 필터를 진입 지점에 넣자 R²가 **0.742 → 0.904**로 올랐다(§12 "경계에서 방어"가 정확도 그 자체였다).

### 반복 검증 결과

| 경로 | 계수 | R² | MAE | ±1h |
|---|---|---|---|---|
| **일사량(채택)** | a=0.181 b=0.586 | **0.9034** | 0.845h | 66.8% |
| 일사량(FAO 기본) | 0.25 / 0.50 | 0.8952 | 0.850h | 68.1% |
| 기온(보정 후) | −0.484 / 0.300 | 0.496 | 2.219h | 26.9% |
| 기온(**기존 코드**) | 0.16 / 0.10 | **0.252** | **2.991h** | 13.8% |

월평균(실제 서비스 단위, 230건): **MAE 0.583h, bias −0.062h, ±1h 84.3%**.

**기각한 대안** — 복잡도만 늘고 이득이 없었다:
- 월별 계수 12쌍: R² +0.003(0.9037→0.9069)뿐
- 습도 잔차보정: MAE를 0.845→0.861h로 **악화**(일사량이 이미 흐림 정보를 담고 있다)

### 검증이 자기 자신을 속이지 않도록 한 장치

- **홀짝 분할**: 계수는 train 절반으로만 뽑고 정확도는 test 절반으로만 보고한다.
- **fixture도 홀드아웃만**: `backend/tests/fixtures/sunlight_validation.json`(230건)에 보정에 쓰지 않은 절반만 담았다.
- **테스트가 매번 재계산**: `test_sunlight_calculation.py`가 MAE·편향·상관을 실행마다 다시 재서 확인한다. 계수를 만지거나 필터를 빼면 즉시 깨진다.
- **독립 재현**: `scripts/calibrate_sunlight.py`가 API 재조회부터 전 과정을 돌려 같은 결과를 낸다(재실행 시 R²=0.9034, a=0.1815, b=0.5843).
- **순환 검증 배제**: 천문량은 우리 출력끼리 비교하지 않고 태양적위 하지 +23.44°/동지 −23.44°(천문 상수)와 대조하고, `Ra`는 실측 230건이 물리 상한을 넘지 않는지로 검증한다.

> 검증 중 제가 "FAO 표 40°N 1월 Ra = 13.0"으로 잘못 기억해 테스트를 틀리게 짰다. 직접 계산하니 **15.01**이 공식의 정답이었고, 코드가 아니라 제 기대치가 틀렸다. 그래서 반쯤 기억한 표 대신 위와 같이 독립 검증 가능한 기준으로 바꿨다.

### 신뢰도는 이제 선언이 아니라 측정치다

계수·신뢰도·오차범위를 **`docs/seed/sunlight_calibration.json`** 으로 분리했다(§18-2 농업 기준값 하드코딩 금지).

| method | confidence | 근거 | 0.90 게이트 |
|---|---|---|---|
| `measurement` | 0.95 | 실측 | 통과 |
| `radiation` | 0.90 | R²=0.903 / MAE 0.845h | 통과 |
| `temperature` | 0.50 | R²=0.496 / MAE 2.219h | **탈락(의도)** |

기온 경로는 산출은 되지만 게이트에서 걸러진다 — 부정확한 추정치를 확정값처럼 채점에 쓰지 않는다(§18-4).

### 프로덕션에서 실제로 도달하게 만든 조치

마이그레이션 **`0016`**: `weather_climatology.solar_radiation_normal` 추가.

일조시간을 미리 환산해 저장하지 않고 **원자료(일사량)를 저장하고 read-time에 환산**한다 — 계수를 재보정하면 저장값이 낡기 때문이다.

> ⚠️ 컬럼만 추가했고 **적재 ETL은 아직 없다**(§8-1). 그때까지 일조 지표는 계속 비어 있다.

부수적으로 발견해 함께 고친 것: `climatology_service`가 `if clim.temp_avg_normal else None`로 값을 읽어 **평년 기온 0.0℃인 달을 결측으로 떨어뜨리고** 있었다(강원 산간에서 실제 가능한 값). `_as_float()`가 `is None`으로만 판정하게 바꿨다.

---

## 5. 1차 리뷰 지적 사항 처리 (요약)

세부 근거는 이전 판과 동일하며, 결론만 남긴다.

- **`0014` 삭제** — 좌표 256개 중 3개만 있고 2개는 값도 틀렸으며 253개가 전부 서울 격자로 적재됐다. `OLAT=37.0`(정답 38.0), `int()` 괄호 오류로 y가 float, `re = RE/GRID` 정규화 누락. `docs/seed/region_grid_seed.csv` + `scripts/load_region_grid.py`가 이미 256/256 정확하다.
- **`0015`** — 샘플 15행 제거, `create_table`만. `down_revision`→`0013`, 리비전 ID를 관례(`"0015"`)에 맞춤, 파일명에서 `_seed` 제거.
- **`suitability_service.py:275`** — `sunlight_by_month`를 `| None` → **항상 dict**로 바꿔 호출부 2곳이 가드 없이 안전해졌다.
- **위도 하드코딩** — `kma_grid.grid_to_latlon()` 역변환 추가. roundtrip 격자 일치, 위도 오차 ≤0.014°.
- **월별 히트맵** — `build_monthly_rows`에 `clim_source` 전달로 일별/월별 일조 채점 일치.
- **`soil_chem_stat_client.py`** — 죽은 `_weighted_avg_from_bins`를 되살려 중복 6블록 대체, `(251,250)`→`(201,250)` 오타 수정(명세서 자체 오타), 유기물 단위 `%`→`g/kg` 확정.

### 리뷰 지적 중 실행 불가 1건

**`survey_year` 복원 불가.** V2 응답 항목이 `stdg_Cd`, `bjd_Nm`, 구간별 면적뿐으로 조사연도 필드가 없다. 없는 값을 채우지 않고 `RegionSoilChemStat` docstring에 한계로 명시했다 — 이 값을 쓰는 화면은 **"조사연도 미상 · 읍면동 평균"** 을 병기해야 한다.

---

## 6. 리뷰에 없던 발견 (누적 5건)

1. **`test_public_api_base.py` ImportError** — head가 `WeatherObservation`을 `DailyWeatherObservation`으로 개명해 수집 단계에서 실패. 해소.
2. **`test_sunlight_calculation.py` 359줄이 한 번도 실행된 적 없음** — pytest 스타일 클래스인데 pytest가 `requirements.txt`에 없다. `unittest.TestCase` 상속으로 살렸고(이후 2차에서 전면 재작성), 데모 `print` 74줄은 Windows cp949에서 `✅` 때문에 터져 제거.
3. **일조 계산이 자기 게이트를 통과 못 함** — 계산 경로 최대 confidence 0.87 < 게이트 0.90. §4에서 근본 해결.
4. **흙토람 통계 API 100% 실패** — §3-① (헤더 대소문자).
5. **개방구간 대표값 폭주** — §3-② (유효인산 2008 mg/kg).

---

## 7. 문서 정정

`0014`/`0015`를 "✅ 검증 완료 / 256행 / 510행"으로 적어둔 문서들이 사실과 달랐다(§18-4).

| 파일 | 정정 |
|---|---|
| `docs/data/CURRENT-STATUS.md` | "Phase 2-5 완료 ✅" → 부분 완료, 실행 로그 예시 현실화 |
| `docs/data/api-implementation-status.md` | 0014 폐기·0015 시드 제거 사유 + DB 재적용 주의 |
| `docs/data/data-integration-strategy.md` | region_grid 적재를 "계산"→"기상청 엑셀 CSV"로 정정 |
| `MIGRATION-GUIDE.md` | 마스터 데이터는 스크립트로 적재함을 명시 |
| `PHASE-2-3-COMPLETION.md`, `PHASE-4-STATUS.md` | 스냅샷 문서라 "일부 폐기됨" 배너만 추가 |

---

## 8. 후속 조치 (사람이 해야 할 것)

### 작업 필요
1. **[[backend/alembic/versions/0016_climatology_solar_radiation.py]]** — 컬럼만 추가됐고 **일사량 평년값 적재 ETL이 없다.** 이게 없으면 일조 지표는 계속 비어 있다. `scripts/calibrate_sunlight.py`가 이미 전국 일별 데이터를 받아오므로, 같은 방식으로 (지역, 월) 평균을 구해 `solar_radiation_normal`에 넣는 ETL을 만들면 된다.
2. **`VWORLD_API` 키가 비어 있다**(주소 → PNU 변환용). 나머지 6개는 로드 확인.
3. **[[backend/alembic/versions/0015_kma_observation_point.py]]** — 관측지점 510개 시드. `기상청_API-Guide.md`의 `getAwsStnLstTbl`이 `stn_id`/`lat`/`lon`/`ht`를 주므로 이걸 CSV로 떠서 `scripts/load_*.py` 패턴으로 적재.

### DB 마이그레이션 주의
4. **폐기된 `0014`를 이미 적용한 DB**는 `alembic_version`이 없는 리비전을 가리켜 `upgrade`가 실패한다:
   ```bash
   alembic stamp 0013 && alembic upgrade head
   psql -c "DELETE FROM region_grid;"          # 253개가 서울 격자
   python scripts/load_region_grid.py
   ```

### 유의
5. **API 호출 쿼터** — 검증 중 `getWeatherYearMonList3`에서 `HTTP 429 API token quota exceeded`를 만났다. `calibrate_sunlight.py`는 월 1콜(전국 일괄)로 4콜만 쓰지만, 지점별 반복 호출은 금물이다(§18-1).
6. **명세서 오타 2건** — 되돌리지 말 것. ① 유효인산 논 5구간 "251~250이하"는 실제 201~250. ② 헤더 태그 케이스가 API별로 다름. 둘 다 코드 주석에 근거를 남겼다.

### 프로세스
7. 리뷰의 마지막 제안(**프론트 UI 셸만 먼저 머지, 백엔드는 별도 PR**)은 반영하지 않았다. 2차 작업으로 백엔드 변경이 더 늘었으니 분리가 더 타당해졌다 — 원하면 브랜치를 뜨겠다.

---

## 9. 동시 편집 경고

1차 작업 중 **15:00:37 / 15:01:04에 제3자가 `0014`/`0015`를 편집**했다(리비전 ID 단축, `op.execute` → `connection.execute`). 커밋되지 않은 상태였고 사용자 승인을 받아 진행했다. 다른 세션·에디터가 동시에 작업 중이라면 확인이 필요하다.

---

## 10. 변경 파일 목록

**삭제 (3)**
- `.env.example`(구 루트 사본 → 새 내용으로 재작성), `backend/alembic/versions/0014_region_grid_seed.py`, `backend/tests/test_api_clients.py`(하드코딩 절대경로 + 라이브 키 필요 + print 기반)

**신규 (5)**
- `docs/seed/sunlight_calibration.json` — 보정계수·신뢰도·검증 결과
- `scripts/calibrate_sunlight.py` — 재현 가능한 보정·검증
- `backend/alembic/versions/0016_climatology_solar_radiation.py`
- `backend/tests/fixtures/sunlight_validation.json` — 실측 홀드아웃 230건
- `backend/tests/test_soil_chem_stat.py` (11 tests)

**전면 재작성 (3)**
- `backend/app/infra/public_api/weather_client.py` — V3 명세 기준
- `backend/app/services/sunlight_calculation.py` — 일사량 기반
- `backend/tests/test_sunlight_calculation.py` (26 tests)

**수정 (13)** — `base.py`, `kma_grid.py`, `soil_chem_stat_client.py`, `climatology_service.py`, `suitability_service.py`, `config.py`, `weather_climatology.py`, `0015_kma_observation_point.py`(개명), `test_kma_grid.py`, `test_public_api_base.py`, `README.md`, `MIGRATION-GUIDE.md`, 데이터 문서 5종
