# ML 종합 결과 및 백엔드 구현 인계

> 기준일: 2026-07-24
> 대상: FastAPI/SQLAlchemy 백엔드 개발자
> 근거: `docs/ml/`, `scripts/ml/`, `data/ml/`, `ML-Plan.md`의 현재 산출물

## 0. 한 줄 결론

- **토양 변화 ML**: pH·유기물은 `Ridge + 90% split-conformal`이 최종 선택됐다. 초기 백엔드 연동은 **사용자 미노출 shadow**로 시작한다.
- **유효인산 ML**: 모든 후보가 기준선을 안정적으로 이기지 못했다. 항상 `available=false`, Δ=0 폴백, 구간 없음이다.
- **작물 적합도**: ML이 아니라 `crop_growth_guide` 기반 **문헌 룰**만 사용한다. 성과 ML은 필지×시즌 레이블 부재로 NO-GO다.
- **인과·행위 추천**: `06_treatment_event`가 없어 금지한다. 현재 모델은 “현재 상태로부터의 통계적 변화량”만 말할 수 있다.

## 1. 백엔드 적용 상태표

| 기능 | 현재 판정 | 백엔드 동작 |
|---|---|---|
| pH 변화량 점추정 | HOLD/제한 사용 | shadow 기록 우선. 향후 점추정만 조건부 노출 가능 |
| pH 90% 구간 | HOLD | spatial 포함률 0.873이므로 “90% 구간” 사용자 노출 금지 |
| 유기물 변화량·구간 | 조건부 GO | shadow 재확인 후 노출. “이론 추정” 한계 문구 필수 |
| 유효인산 변화량 | NO-GO | `available=false`, Δ=0 carry-forward, `lo/hi=null` |
| 작물 적합도 | 결정론 룰 | “문헌 기반 예상 적합도”로만 표시 |
| 작물 수량/성과 ML | NO-GO | API·UI에 예측 기능을 만들지 않음 |
| 시비·행위 효과/자동 추천 | NO-GO | 인과·처방 문구 금지 |

문서끼리 표현이 충돌하면 **현재 코드 + 독립 교차검증 → shadow 보고서 → 모델 선정 기록 → 후보 실험 보고서** 순서로 본다.

## 2. 토양 변화 모델 최종 결정

### 2.1 모델

| 목표 | 모델 | 입력 | 출력 |
|---|---|---|---|
| `delta_ph` | Ridge(`alpha=1.0`) + split-conformal | 공통 4개 피처 | point, lo, hi, available=true |
| `delta_organic_matter` | Ridge(`alpha=1.0`) + split-conformal | 공통 4개 피처 | point, lo, hi, available=true |
| `delta_available_p` | ML 미채택 | 같은 입력을 받아도 학습 예측 미사용 | point=0, lo/hi=null, available=false |

공통 입력 순서는 바꾸면 안 된다.

```text
ph_t0,
organic_matter_t0,
available_p_t0,
interval_days
```

현재 DB 매핑:

| 모델 피처 | 백엔드 원천 |
|---|---|
| `ph_t0` | `soil_state.ph` 또는 향후 `soil_state_snapshot.ph` |
| `organic_matter_t0` | `soil_state.organic_matter` |
| `available_p_t0` | `soil_state.p2o5` |
| `interval_days` | `target_date - feature_as_of` |

주의:

- `soil_state`의 `computed_at`은 계산시각이지 반드시 실측시각은 아니다. 안전한 `feature_as_of`를 위해 `soil_state_snapshot.measured_at` 구현이 필요하다.
- 학습 구간은 p05 17일, 중앙 333일, p95 768일, 최대 1,278일이다. 이 범위를 벗어난 horizon 정책은 `[확인 필요]`; 조용히 외삽하지 않는다.
- 물리성·기상 피처는 최종 모델에 넣지 않는다. 결합률이 각각 0.3%, 56%였고 기상 추가의 개선도 없었다.

### 2.2 성능 및 노출 게이트

| split | 목표 | n | MAE | 무변화 대비 | 90% 구간 포함률 |
|---|---|---:|---:|---:|---:|
| spatial | pH | 770 | 0.566 | +8.0% | **0.873** |
| temporal | pH | 1,478 | 0.506 | +6.2% | 0.940 |
| spatial | 유기물 | 770 | 10.454 | +11.7% | 0.964 |
| temporal | 유기물 | 1,472 | 10.028 | +5.5% | 0.944 |

판정:

- 유기물은 두 분할 모두 구간 포함률이 0.90 이상이다.
- pH는 지역 밖 spatial 구간이 0.873이고, 채점 가능한 12개 지역 중 6개가 0.90 미달이다.
- 위 수치는 과거 홀드아웃 **오프라인 shadow 프록시**다. 라이브 트래픽 검증 결과가 아니다.

### 2.3 버전·재현성 계약

```text
model_version   = soil_delta_ridge_conformal_2026-07-24
data_version    = 2026-07-24
feature_as_of   = t0
prediction_type = delta_regression | unavailable
```

- 연구 CSV의 `feature_as_of=t0`는 의미 표기다. 운영 로그에는 재현 가능한 실제 ISO 날짜도 별도로 남긴다.
- Ridge와 conformal 보정은 랜덤성이 없다.
- 학습 결측은 학습셋 중앙값으로 대치하며, 추론에도 **동일한 중앙값**을 써야 한다.
- conformal 구간은 각 목표의 `point ± q`다.
- 검증에서 관측된 반폭은 pH 약 ±1.10~1.25, 유기물 약 ±29.3~31.6이지만, 런타임은 문서 수치가 아니라 저장된 artifact의 `q`를 사용한다.

## 3. 연구 코드와 운영 코드의 경계

현재 [final_model.py](../../scripts/ml/final_model.py)는 다음을 한 프로세스에서 수행한다.

1. `training_rows.csv` 로드
2. Ridge 학습
3. 지역 단위 fit/calibration 분리
4. conformal 반폭 계산
5. 예측

이 코드를 FastAPI 시작 시 그대로 실행하면 안 된다.

- 앱 부팅 때 7,577행 CSV로 재학습하지 않는다.
- `data/ml/training_rows.csv`를 운영 컨테이너의 런타임 의존성으로 만들지 않는다.
- 현재 `backend/requirements.txt`에는 numpy/pandas/scikit-learn이 없다.

### 3.1 권장 최소 배포 형태

오프라인 학습 작업이 아래 JSON artifact를 만든 뒤 백엔드는 읽기만 한다.

```json
{
  "model_version": "soil_delta_ridge_conformal_2026-07-24",
  "data_version": "2026-07-24",
  "features": [
    "ph_t0",
    "organic_matter_t0",
    "available_p_t0",
    "interval_days"
  ],
  "feature_medians": {},
  "targets": {
    "delta_ph": {
      "coef": [],
      "intercept": 0.0,
      "conformal_q": 0.0
    },
    "delta_organic_matter": {
      "coef": [],
      "intercept": 0.0,
      "conformal_q": 0.0
    }
  }
}
```

아직 이 artifact와 exporter는 생성되지 않았다. 백엔드 통합 전 P0 작업이다.

권장 이유:

- Ridge 추론은 `intercept + Σ(coef_i × feature_i)` 한 줄이라 sklearn 런타임이 필요 없다.
- 학습 중앙값과 conformal `q`도 artifact에 함께 고정할 수 있다.
- artifact checksum과 모델 버전을 배포 단위로 관리하기 쉽다.

exporter는 전체 `training_rows.csv`로 `FinalModel.fit()`을 한 번 호출한다. 이 함수가 내부에서 region 코드를 정렬하고 뒤쪽 25% 지역을 calibration으로 분리하므로, exporter가 별도 무작위 분할을 추가하면 안 된다.

## 4. 백엔드 런타임 흐름

```text
soil_state_snapshot + target_date
  → 입력 검증/중앙값 대치
  → 버전 고정 artifact 추론
  → pH·유기물 Δ 및 구간
  → 유효인산 unavailable 폴백
  → shadow 로그 저장
  → 노출 게이트를 통과한 필드만 API 응답
```

### 4.1 추론 결과 내부 계약

아래는 값 예시가 아니라 DTO 타입 계약이다.

```text
{
  model_version: string,
  data_version: string,
  feature_as_of: ISO date,
  target_date: ISO date,
  predictions: {
    ph: {
      delta: number,
      projected_value: number,
      lo: number | null,
      hi: number | null,
      available: boolean,
      prediction_type: "delta_regression" | "unavailable",
      fallback_used: boolean
    },
    organic_matter: {
      delta: number,
      projected_value: number,
      lo: number | null,
      hi: number | null,
      available: boolean,
      prediction_type: "delta_regression" | "unavailable",
      fallback_used: boolean
    },
    available_p: {
      delta: 0,
      projected_value: available_p_t0,
      lo: null,
      hi: null,
      available: false,
      prediction_type: "unavailable",
      fallback_used: true
    }
  },
  imputed_features: string[],
  limitations: string[]
}
```

규칙:

- `projected_value = t0 + delta`.
- `interval_days <= 0`, 무한대, 숫자 변환 실패는 모델 호출 전 입력 오류로 차단한다.
- t0 피처 결측은 artifact에 저장된 학습 중앙값만 사용하고 `imputed_features`에 기록한다.
- pH·유기물 모델/파일 로드 실패 시 Δ=0, `fallback_used=true`.
- 유효인산은 정상 상황에서도 항상 Δ=0, `available=false`, `fallback_used=true`, 구간 null.
- 사용자 응답의 pH 구간은 재보정 전까지 숨긴다. 내부 shadow 로그에는 기록한다.
- 결측 대치가 발생하면 `imputed_features`를 반드시 남긴다.

### 4.2 shadow 로그

현재 검증 CSV 계약은 다음과 같다.

```text
split_type, region_code, pnu, target,
y_pred, lo, hi, y_true, in_interval, abs_err,
model_version, feature_as_of, prediction_type, fallback_used
```

운영 DB 로그는 최소한 아래를 보존해야 한다.

```text
user_farm_id,
target,
point,
lo,
hi,
model_version,
data_version,
feature_as_of,
target_date,
prediction_type,
fallback_used,
is_exposed,
created_at
```

실측 후에는 해당 예측과 새 `soil_state_snapshot`을 연결해 MAE·포함률을 재계산한다. 테이블명과 FK 구조는 백엔드 스키마 작업에서 확정한다.

## 5. 작물 적합도 룰

### 5.1 현재 구현

- 시드: [0004_crop_growth_guide_seed.py](../../backend/alembic/versions/0004_crop_growth_guide_seed.py)
- 계산: [suitability_service.py](../../backend/app/services/suitability_service.py)
- 테스트: [test_suitability_service.py](../../backend/tests/test_suitability_service.py)

5작물 13개 문헌 지침이 `crop_growth_guide`에 들어간다. 계산 결과:

```text
score: 0~100 | null
grade: S | A | B | C | null
breakdown: 지표별 value/score/weight/status
risk_flags: missing/invalid/outside_allowed
```

등급:

```text
S >= 90
A >= 75
B >= 60
C < 60
```

### 5.2 백엔드 연결 전 차단요인

1. `temp_day`는 현재 `weather_climatology`에 정확히 대응하는 컬럼이 없다. `temp_avg_normal`로 조용히 대체하지 않는다.
2. `planting_date`/달력으로 `fruit_growth`, `maturity`, `coloring`, `growing`, `early`, `tuber`를 고르는 단계 resolver가 없다.
3. 허용구간 끝 60점은 `[확인 필요]`다.
4. Alembic 0004는 생성·체인 검증만 완료됐고, 로컬 Docker DB가 꺼져 있어 실제 DB에는 적용하지 못했다.

따라서 룰 엔진은 계산 가능하지만 API에 연결하기 전 위 1~3을 확정해야 한다. 출력 명칭은 항상 **“문헌 기반 예상 적합도”**다.

### 5.3 aggregate sanity check

사과·배에 한해 2021~2023 KOSIS 시도 단수와 기상 프록시 룰 순위를 비교했다.

| 작물 | Spearman ρ | p | 판정 |
|---|---:|---:|---|
| 사과 | -0.309 | 0.355 | 불확실한 재검토 신호 |
| 배 | -0.518 | 0.102 | 불확실한 재검토 신호 |

이는 룰 정확도 검증이 아니다. 실제 룰 엔진 구현 전에 월평균기온으로 만든 프록시이며, 수량 예측·인과·ML 정확도 주장은 금지한다.

## 6. 작물 성과 ML과 first-party 수집

### 6.1 현재 판정

- `data/07_crop_outcome.csv`: 378행
  - 사과 172
  - 배 170
  - 감자 17
  - 오이 10
  - 상추 9
- 사과·배의 대부분은 KOSIS 시도×연 aggregate다.
- 공개 데이터에는 PNU/필지 단위 성과 정답이 없다.
- aggregate를 필지 수량 모델의 정답으로 사용하면 안 된다.

현재 허용되는 용도는 지역 순위 반증 sanity check뿐이다.

### 6.2 향후 백엔드 스키마

#### `crop_outcome_record`

v1 핵심 필드:

```text
id,
user_farm_id,
season_year,
planting_date,
harvest_date,
yield_amount,
cultivation_area,
yield_unit,
area_unit,
yield_per_area,
pest_disaster_flag,
source,
is_measured,
is_imputed,
quality_flag,
feature_as_of,
created_at
```

- `uq_outcome(user_farm_id, season_year)`.
- 사용자는 총수확량·면적·단위만 입력하고 `yield_per_area(kg/10a)`는 ETL이 계산한다.
- 알 수 없는 단위는 삭제하지 않고 `quality_flag=unit_uncertain`.

#### `soil_state_snapshot`

```text
id,
user_farm_id,
measured_at,
ph,
organic_matter,
available_p,
source,
is_measured,
is_imputed,
created_at
```

- append-only.
- 기존 `soil_state`는 현재값 캐시로 유지한다.

#### `farm_action_log` 보강

```text
material_code,
unit,
applied_area,
nitrogen_per_area,
phosphate_per_area,
potash_per_area,
organic_input_per_area,
source
```

이 데이터가 생기기 전에는 행위효과·인과·자동추천을 만들지 않는다.

### 6.3 작물 성과 ML 재개 게이트

아래를 모두 충족한 뒤 다시 감사한다. 임계값은 `[확인 필요]`.

| 기준 | 임계 |
|---|---:|
| 총 밭×시즌 레이블 | ≥ 200 |
| 작물별 레이블 | 5작물 각각 ≥ 30 |
| 지역 | ≥ 15 시군구 |
| 시간 | 지역×작물당 ≥ 2 시즌 |
| 실측 품질 | `is_measured=true` ≥ 70% |

게이트 전에는 crop ML API·0~100 ML 점수·수량 예측 기능을 만들지 않는다.

## 7. 데이터 계약

### 7.1 `training_rows.csv`

- 7,577행
- 4,414 PNU
- 301 지역
- 관측창 2023-01-01~2026-07-23
- 1행 = PNU의 연속 토양검정 `(t0,t1)` 한 쌍
- 정답 = `t1 - t0`

주요 필드:

```text
pnu, region_code, sgg_code,
t0_date, t1_date, interval_days,
ph_t0, organic_matter_t0, available_p_t0,
delta_ph, delta_organic_matter, delta_available_p,
physical_join,
w_temp_mean, w_precip_sum, w_temp_min, w_temp_max, w_precip_max,
weather_source, is_imputed_weather,
t0_is_imputed, t0_quality_flag, t0_n_samples,
data_version
```

누수 방지:

- `*_t1` 토양값을 피처로 넣지 않는다.
- spatial split은 region 전체를 test로 보내며 train/test PNU 중복이 0이다.
- temporal split은 최신 t1 20%를 test로 사용하며 시간 중첩이 없다.
- 무작위 행 분할 금지.

### 7.2 단위

| 값 | 단위 |
|---|---|
| pH | 무단위 |
| organic matter | g/kg |
| available P | mg/kg |
| yield per area | kg/10a |
| cultivation area | ha |
| production | t |

## 8. 구현 순서

### P0 — shadow 추론을 실제 백엔드에서 돌리기

- [ ] `FinalModel.fit()` 결과를 JSON으로 내보내는 오프라인 exporter 작성
- [ ] 모델 artifact에 feature 순서·중앙값·계수·절편·conformal q·버전 저장
- [ ] FastAPI용 경량 inference service 작성(앱 시작 시 artifact 1회 로드)
- [ ] `soil_state_snapshot.measured_at` 또는 동등한 `feature_as_of` 확보
- [ ] horizon 입력 계약(`target_date` 또는 `interval_days`) 확정
- [ ] prediction shadow 로그 테이블·Alembic 마이그레이션 작성
- [ ] pH·유기물·유효인산 unavailable 경로 테스트
- [ ] 사용자 응답에는 아직 노출하지 않고 `is_exposed=false`로 기록

### P1 — 노출 게이트

- [ ] 라이브 신규 실측으로 목표별 MAE·구간 포함률 재계산
- [ ] pH spatial 구간 재보정 후 0.90 충족 확인
- [ ] 유기물 “문헌 기반 이론 추정” 한계 문구 포함
- [ ] 실패 시 Δ=0 폴백과 stale/model-unavailable 상태 표시

### P2 — crop 룰 연결

- [ ] Alembic 0004 적용
- [ ] `temp_day` 실제 데이터원 확정
- [ ] 작물별 growth-stage resolver 확정
- [ ] 허용구간 끝 60점 승인
- [ ] `suitability_result` baseline 캐시 upsert 연결

### P3 — first-party 장기 수집

- [ ] `soil_state_snapshot`
- [ ] `crop_outcome_record`
- [ ] `farm_action_log` 단위·성분 보강
- [ ] 수확기 저마찰 입력 API와 소유권 검증
- [ ] 게이트 충족 후에만 crop ML 재감사

## 9. 테스트·재현 명령

PowerShell:

```powershell
$env:PYTHONIOENCODING='utf-8'
python scripts/ml/build_training_rows.py
python scripts/ml/baselines.py
python scripts/ml/experiment.py
python scripts/ml/final_model.py
python scripts/ml/shadow_validate.py
python scripts/ml/crop_suitability_sanity.py
```

백엔드 룰 테스트:

```powershell
cd backend
python -m unittest tests.test_suitability_service
```

현재 검증 상태:

- 신규 적합도 룰 테스트 4개 PASS.
- shadow 독립 재계산 PASS: 누수 없음, available_p 미방출, 결정론 확인.
- 전체 백엔드 테스트에는 별도 기존 버그 1건이 남아 있다: `soil_profile_client`의 `Deepsoil_Qlt_Cd`/공식 `Deepsoil_Qlt_Code` 불일치. ML 변경과 무관하다.

## 10. 알려진 불일치와 정리 우선순위

1. `final_model.py` 실제 코드는 available_p에 `no_change_pred`를 쓰지만 `_evaluate()` 출력 문자열은 “문헌룰값”이라고 적혀 있다. **동작은 Δ=0가 맞고 문자열만 오래됐다.**
2. `model_selection_decision.md` 중간 메모에는 available_p 1줄 수정이 필요하다고 적혀 있으나 stage 7에서 이미 수정됐다. `codex_shadow_crosscheck.md`와 현재 코드가 최신 근거다.
3. `crop_suitability_sanity_report.md`는 실제 룰 엔진 구현 전에 만든 기상 프록시 결과다. 실제 `suitability_service`의 정확도 결과로 해석하면 안 된다.
4. 모델 artifact가 아직 없어 백엔드 프로세스에서 안전하게 로드할 운영 산출물이 없다.
5. `temp_day`, growth stage, 점수 60 경계가 확정되기 전 crop 룰 API 연결 금지.

## 11. 산출물 색인

### 최종 판단

- `ML-Plan.md`
- `docs/ml/model_selection_decision.md`
- `docs/ml/shadow_validation_report.md`
- `docs/ml/codex_shadow_crosscheck.md`
- `docs/ml/crop_outcome_data_audit.md`
- `docs/ml/crop_outcome_collection_design.md`
- `docs/ml/crop_suitability_sanity_report.md`

### 실험·감사

- `docs/ml/data_audit_report.md`
- `docs/ml/experiment_report.md`
- `docs/ml/bayes_experiment_report.md`
- `docs/ml/codex_crop_outcome_crosscheck.md`
- `docs/ml/crop_data_sources.md`
- `docs/ml/crop_data_sources_codex.md`
- `docs/ml/crop_data_sources_web.md`
- `docs/ml/kosis_api_investigation.md`

### 실행 코드

- `scripts/ml/build_training_rows.py`
- `scripts/ml/splits.py`
- `scripts/ml/baselines.py`
- `scripts/ml/experiment.py`
- `scripts/ml/bayes_hierarchical.py`
- `scripts/ml/final_model.py`
- `scripts/ml/shadow_validate.py`
- `scripts/ml/crop_suitability_sanity.py`
- `scripts/ml/requirements.txt`
- `backend/app/services/suitability_service.py`

### 데이터

- `data/ml/training_rows.csv`
- `data/ml/shadow_predictions.csv`
- `data/ml/bayes_results.csv`
- `data/ml/crop_suitability_sanity.csv`
- `data/07_crop_outcome.csv`

## 12. 백엔드가 절대 하면 안 되는 것

- 요청마다 모델 재학습
- available_p의 Δ=0를 “ML 예측 성공”으로 표시
- pH spatial 구간을 보정 전 “90% 신뢰구간”으로 노출
- aggregate 작물 단수를 필지 성과 정답으로 학습
- crop 적합도를 “ML 정확도 검증 완료”로 표시
- 행위 데이터 없이 시비·관수의 인과 효과 주장
- `temp_avg_normal`을 승인 없이 `temp_day`로 조용히 매핑
- 미래 토양값·수확 후 통계·미래 기상을 피처에 포함
