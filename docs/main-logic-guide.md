# 메인 로직 백엔드 구현 가이드 (팀원용)

> "무엇을·어디에·무슨 순서로·무슨 계약으로 짜고, 무엇을 하면 안 되는가"의 플레이북.
> **근거 원문은 [`docs/ml/backend_ml_handoff.md`](ml/backend_ml_handoff.md)** — 수치·모델 결정·데이터 계약은 전부 거기가 최종. 이 문서는 그걸 구현 작업으로 옮긴 것.
> 함께 읽기: `PRD.md` §8(토양변화)·§9(장기 적합도), `DB.md`, `CLAUDE.md` §10(마이그레이션)·§12(공공데이터)·§13(LLM).

---

## 0. 범위 — "메인 로직"이 뭐고 뭐가 아닌가

**메인 로직 = ①토양 변화 추론(첫 ML 산출물) + ②작물 적합도 룰 + ③(향후) first-party 수집.**

| 포함 | 제외(하지 말 것) |
|---|---|
| pH·유기물 Δ 예측(Ridge+conformal artifact 추론) | 요청마다 모델 **재학습** |
| 유효인산 `available=false` 폴백 | 유효인산 Δ를 "예측 성공"으로 표기 |
| `crop_growth_guide` 기반 **문헌 룰** 적합도 | 작물 수량/성과 **ML**(레이블 부재 → NO-GO) |
| 결정론 계산 + 근거 표기 | 시비·관수의 **인과 효과·자동 처방**(행위 데이터 없음) |

이론 추정·평년치·시군평균은 **한계 문구를 UI/응답에 반드시 병기**(CLAUDE.md §1-4, §12).

---

## 1. 아키텍처 위치 (어디에 짜나)

```
backend/app/
├── infra/ml/            # ★신규: artifact 로더 + 경량 추론(sklearn 런타임 의존 없음)
├── services/
│   ├── soil_delta_service.py     # ★신규: 입력검증→추론→폴백→shadow 로그 (P0)
│   └── suitability_service.py    # 기존: 적합도 룰 (P2에서 API 연결)
├── models/
│   ├── prediction_shadow.py      # ★신규: shadow 예측 로그 (P0)
│   └── soil_state_snapshot.py    # ★신규: 실측 이력 append-only (P0/P3)
├── schemas/             # DTO(핸드오프 §4.1 계약 그대로)
├── api/                 # 라우터 — 서비스 계층만 호출, 로직 금지(§6/§11)
└── alembic/versions/    # 스키마는 마이그레이션으로만 (§10)

scripts/ml/export_model.py   # ★신규(오프라인, 앱 밖): training_rows.csv → artifact JSON
```

**철칙**: 백엔드는 `training_rows.csv`로 부팅 때 학습하지 않는다. 오프라인 exporter가 만든 **JSON artifact를 읽기만** 한다. Ridge 추론은 `intercept + Σ(coef·feature)` 한 줄이라 numpy/pandas/sklearn 런타임 불필요.

---

## 2. P0 — 토양 변화 shadow 추론 (최우선, 사용자 미노출)

첫 ML 데이터셋(`training_rows.csv`, 7,577행)의 결과물을 실제 백엔드에서 돌리는 단계. **사용자에게 아직 안 보여주고 DB에만 기록**한다(노출은 P1 게이트 통과 후).

### 2.1 작업 단위 (각각 독립 PR 가능)

1. **오프라인 exporter** `scripts/ml/export_model.py`
   - `FinalModel.fit()`을 전체 `training_rows.csv`로 **한 번** 호출 → artifact JSON 저장.
   - 저장 내용: `model_version`, `data_version`, `features`(순서 고정), `feature_medians`, target별 `coef`/`intercept`/`conformal_q`.
   - exporter가 **별도 무작위 분할을 추가하면 안 됨**(FinalModel이 내부에서 region 정렬·뒤 25% calibration 분리를 이미 함).
   - artifact 스키마는 핸드오프 §3.1 참고.

2. **경량 추론** `infra/ml/soil_delta.py`
   - 앱 시작 시 artifact 1회 로드(checksum·버전 확인).
   - 입력 피처 순서 **절대 고정**: `ph_t0, organic_matter_t0, available_p_t0, interval_days`.
   - 결측 t0 피처는 artifact의 학습 중앙값으로 대치하고 `imputed_features`에 기록.
   - conformal 구간 = `point ± q`(artifact의 q 사용, 문서 수치 아님).

3. **서비스** `services/soil_delta_service.py` — 런타임 흐름(핸드오프 §4):
   `snapshot + target_date → 입력검증/중앙값대치 → artifact 추론 → pH·유기물 Δ+구간 → 유효인산 unavailable 폴백 → shadow 로그 → (게이트 통과 필드만 응답)`

4. **스키마/마이그레이션**
   - `soil_state_snapshot`(append-only, `measured_at` 포함) — `feature_as_of`를 안전하게 잡기 위해 필요. 기존 `soil_state`는 현재값 캐시로 유지.
   - `prediction_shadow`(핸드오프 §4.2 최소 필드): `user_farm_id, target, point, lo, hi, model_version, data_version, feature_as_of, target_date, prediction_type, fallback_used, is_exposed, created_at`.
   - FK는 유저 하위이므로 `ON DELETE CASCADE`(§11/§17).

5. **DTO** — 핸드오프 §4.1 타입 계약 그대로. SQLAlchemy 모델 직접 노출 금지, pydantic 변환(§6).

### 2.2 결정론·방어 규칙 (반드시)

- `interval_days <= 0`, 무한대, 숫자변환 실패 → **모델 호출 전** 입력 오류로 차단.
- pH·유기물 artifact 로드/추론 실패 → `Δ=0, fallback_used=true`(서비스가 죽지 않게, §18-5).
- 유효인산은 정상 상황에서도 **항상** `Δ=0, available=false, fallback_used=true, lo/hi=null`.
- **pH 구간(lo/hi)은 사용자 응답에서 숨긴다**(spatial 포함률 0.873 → 재보정 전 노출 금지). shadow 로그엔 기록.
- 학습 구간 밖 horizon(p05 17일 ~ p95 768일, 최대 1,278일) 정책은 **`[확인 필요]`** — 조용히 외삽 금지.
- 같은 입력 → 같은 출력(Ridge·conformal은 랜덤성 없음). 추론에도 **학습과 동일한 중앙값** 사용.

### 2.3 완료 조건 (P0 done)

- [ ] artifact exporter가 재현 가능한 JSON 생성(체크섬·버전 포함)
- [ ] 앱 시작 시 artifact 1회 로드, 요청마다 재학습 안 함
- [ ] pH·유기물·유효인산(unavailable) 경로 각각 테스트
- [ ] `prediction_shadow`에 `is_exposed=false`로 기록
- [ ] 결측 대치 시 `imputed_features` 남김

### 2.4 ML 데이터 최신화 시 지속 반영 (★필수 요건 — 재현 파이프라인)

새 토양검정 데이터가 쌓여 학습셋이 갱신되면 **코드 변경 없이** 최신 모델을 계속 반영할 수 있어야 한다. 위의 "artifact를 읽기만 하는" 구조가 이걸 위한 것이다:

1. **(오프라인)** `training_rows.csv` 갱신 → `scripts/ml/export_model.py` 재실행 → 새 artifact JSON 생성. `data_version` 갱신(모델식이 바뀌면 `model_version`도).
2. **배포** — 새 artifact를 배포 단위로 교체(checksum·버전 관리). 백엔드는 재시작 시 최신 artifact를 1회 로드. **추론 코드는 안 바뀐다** — 계수·중앙값·conformal q 값만 바뀐다.
3. **회귀 감시** — 모든 예측 로그에 `model_version`+`data_version`을 남기므로 refresh 전후 MAE·구간 포함률을 비교할 수 있다. 나빠지면 이전 artifact로 롤백.
4. **스키마 변경은 명시적으로** — feature 순서·이름이 바뀌면 artifact 스키마 변경이다. exporter와 inference를 **동시에** 갱신하고 버전을 올린다. 조용히 바꾸지 않는다.
5. **자동화** — 정기 재학습이 필요하면 오프라인 배치(스케줄러)로 `export → shadow 검증 → artifact 교체`를 돌린다. **앱 부팅/요청 경로에서는 절대 학습하지 않는다**(§6).

> 요약: "데이터 최신화 → 새 artifact → 배포"가 반복 가능한 파이프라인이고, 백엔드는 언제나 **버전이 고정된 artifact를 읽기만** 한다. 이 규율을 깨면(런타임 학습·버전 미기록) 지속 반영과 재현성이 무너진다.

---

## 3. P1 — 노출 게이트 (P0 이후)

라이브 신규 실측이 쌓이기 전엔 어떤 Δ도 사용자에게 확정처럼 보여주지 않는다.

- [ ] 라이브 실측으로 목표별 MAE·구간 포함률 **재계산**(오프라인 shadow 프록시로는 부족).
- [ ] pH spatial 구간 재보정 후 **0.90 충족** 확인해야 pH 구간 노출.
- [ ] 유기물 노출 시 **"문헌 기반 이론 추정"** 한계 문구 필수.
- [ ] 실패 시 `Δ=0` 폴백 + `stale`/`model-unavailable` 상태 표시(§12).

---

## 4. P2 — 작물 적합도 룰 API 연결

계산 로직(`suitability_service.py`)·시드(`0004_crop_growth_guide_seed.py`)·테스트는 이미 있음. **API 연결 전 아래 3개를 먼저 확정**해야 함(핸드오프 §5.2):

1. `temp_day`의 실제 데이터원 확정 — `weather_climatology`엔 대응 컬럼이 없다. `temp_avg_normal`로 **조용히 대체 금지**(승인 필요).
2. `planting_date`/달력 → 생육단계(`fruit_growth`/`maturity`/`coloring`/`growing`/`early`/`tuber`) **resolver** 구현.
3. 허용구간 끝 **60점** 경계 승인(`[확인 필요]`).

- 출력 명칭은 언제나 **"문헌 기반 예상 적합도"**(ML 정확도 검증 완료 아님).
- 등급: `S≥90 / A≥75 / B≥60 / C<60`. 색만으로 등급 구분 금지, 라벨 병기(§8).
- 연결 후 `suitability_result` baseline 캐시 upsert((지역, 작물, 단계) 단위, §17).
- 선행: Alembic 0004 실제 DB 적용.

---

## 5. P3 — first-party 장기 수집 (crop ML 재개의 전제)

공개 데이터엔 필지 단위 성과 정답이 없어 성과 ML은 NO-GO. 우리가 직접 모아야 열린다.

- [ ] `soil_state_snapshot`(P0에서 이미 도입)
- [ ] `crop_outcome_record`(핸드오프 §6.2): 사용자는 총수확량·면적·단위만 입력, `yield_per_area(kg/10a)`는 ETL 계산. 알 수 없는 단위는 삭제 말고 `quality_flag=unit_uncertain`.
- [ ] `farm_action_log` 성분·단위 보강(질소/인산/칼리/유기물 per area).
- [ ] 수확기 저마찰 입력 API + 소유권 검증(§11).
- [ ] **재개 게이트**(핸드오프 §6.3) 충족 후에만 crop ML 재감사: 총 밭×시즌 레이블 ≥200, 작물별 ≥30, 지역 ≥15, 지역×작물당 ≥2시즌, 실측 ≥70%.

---

## 6. 절대 금지 (핸드오프 §12 — 위반 시 리뷰 반려)

- 요청마다 모델 재학습 / `training_rows.csv`를 런타임 의존성으로
- 유효인산 `Δ=0`를 "ML 예측 성공"으로 표기
- pH spatial 구간을 보정 전 "90% 신뢰구간"으로 노출
- aggregate 작물 단수를 필지 성과 정답으로 학습
- 적합도를 "ML 정확도 검증 완료"로 표기
- 행위 데이터 없이 시비·관수 **인과 효과** 주장
- `temp_avg_normal`을 승인 없이 `temp_day`로 매핑
- 미래 토양값(`*_t1`)·수확 후 통계·미래 기상을 피처에 포함(누수)

---

## 7. 지금 열려 있는 `[확인 필요]` (막히면 사람에게)

- horizon(interval_days) 학습 구간 밖 정책
- `temp_day` 데이터원
- 생육단계 resolver 기준(파종일 경과 → 단계 매핑)
- 적합도 허용구간 끝 60점
- crop 성과 ML 재개 임계값

---

## 8. 시작 체크리스트

1. `docs/ml/backend_ml_handoff.md` 정독(이 문서의 근거 원문).
2. `scripts/ml/final_model.py`·`suitability_service.py` 코드 확인.
3. Docker DB 켜고 Alembic head 확인 → P0 스키마 마이그레이션 작성.
4. P0부터. exporter → 추론 → 서비스 → shadow 로그 순. 각 단계 독립 PR(작게, §14).
5. 비자명 로직(추론·폴백·입력검증)엔 실행 가능한 테스트 최소 2개(§3-6).
