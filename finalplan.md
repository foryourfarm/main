# FarmML v6 계약 백엔드 적용 계획

> 대상 계약: `outcomes/README.md` (`knowledge_version` / `scoring_version` = **2026-08-05-v6**)
> 작성 2026-08-05. 이 문서는 실행 계획이며 계약 자체가 아니다 — 계약은 `outcomes/`가 단일 소스다.
> 워크스페이스 경계: `../CLAUDE.md` §2. **FarmML 저장소는 이 작업에서 건드리지 않는다.**

---

## 0. 배경 — 왜 지금 하는가

`outcomes/`는 이미 v6로 미러돼 있고 해시도 일치한다(`test_farmml_contract.py::TestOutcomesLedger`).
문제는 **백엔드가 그 계약의 일부만 구현했다**는 것이다. 계약 문서 §2026-08-04 절이
"백엔드가 아래를 반영하기 전까지 같은 밭에 대해 두 시스템이 다른 점수를 낸다"고 명시했고,
`test_farmml_contract.py::TestUntransferredContractItems`가 그 미구현 상태를 **테스트로 고정**해뒀다.

이번 작업은 그 테스트를 뒤집는 일이다 — 통과 조건이 "컬럼이 없다"에서 "값이 계약과 같다"로 바뀐다.

### 이미 맞는 것 (건드리지 않는다)

| 항목 | 상태 |
|---|---|
| 곡선 상수 `ALLOWED_BOUNDARY_SCORE=60` / `OPTIMAL_EXIT_SCORE=95` / `DECAY_CURVATURE=9` | 계약과 동일, 테스트로 고정 |
| 단측 밴드(사과 `ca`) | `_indicator_score`가 이미 처리 |
| 결측 = 채점 제외(`FILL_MISSING=False`) | `calculate_suitability`가 처음부터 제외 |
| 감자 월 강수 밴드 미채점 | `0013`이 삭제 — 계약 `refuted:true`와 결과적으로 일치 |
| 감쇠폭(`risk_width`) 주입 | `0020` + `_risk_score` |

---

## 1. 범위 (2026-08-05 사용자 결정)

### 포함

| # | 갭 | 결정 |
|---|---|---|
| G1 | `crop_growth_guide` 성격 메타 4컬럼 (`cultivation_type`·`allowed_min_kind`·`allowed_max_kind`·`method`) | 신설 |
| G2 | `boundary_score(kind)` — `literature_limit` 경계는 60이 아니라 **0점** | 구현 |
| G3 | `category_score` — `code_scores` 등급코드 배점표 분기 | 구현 |
| G4 | 주 총점 = `min(토양 총점, 기온 점수)` 국가 3단 구조 | **장기 탭만.** 단기는 현행 가중평균 유지 |
| G5 | `limiting_factor` / `limiting_layer` 산출 | 구현 (장기) |
| G6 | 감자 강수 `refuted` | 가드 테스트만 (이미 일치) |
| G7 | UI 표기 4건 | **백엔드 필드 + FE 표기까지** |
| G10 | 물리성 지표 | **심토토성(사과·배)만.** 경사·자갈은 다음 라운드 |
| G11 | 기후층 무동작 감시 (`주 총점 − 토양 총점` 평균) | 구현 |

### 제외 (근거를 남기고 미룬다)

| 항목 | 이유 |
|---|---|
| `slope_pct` / `gravel_pct` 채점 | 다음 라운드. `band_score` 기존 경로 재사용 가능해 급하지 않다 |
| `soil_change_rule.crop_id` | 팀 결정 "보류". 현재 시드 행 **0건**이라 LIMING 오추천 위험이 아직 실재하지 않는다. **행을 넣는 PR이 이 항목의 트리거다** |
| 배수등급 U자형 채점 | 데이터 없음 (계약도 미이관) |
| 단기 탭 총점 구조 변경 | G4 결정에 따라 범위 밖 |
| 사과 arccas 적지/가능지 2단 지표 | 계약이 값을 이관하지 않음(`Trash/`에만 존재) |

### 알려진 계약 예외 1건

`rainfall_daily`(weight 1.5, 5작물)를 **단기 탭에서만 유지**한다. FarmML `weights.precipitation = 0`과
어긋나지만 그 0은 시즌 채점 계약이고, 단기 예보 일누적 강수는 다른 축이다(`0012` 문헌 "일 30~50mm").
장기 탭은 이미 `SEASONAL_UNAVAILABLE_INDICATORS`로 제외 중이라 **계약과 일치**한다.
→ 이 예외는 §7 인계 문서에 근거와 함께 명시한다. 조용히 두지 않는다.

---

## 2. 작업 분해

각 Phase는 **독립 PR**이다(CLAUDE.md §2 작은 PR). 브랜치는 전부 `dev`에서 분기, `dev`로 머지.

### P0 — 기준선 고정

- **목적**: 변경 전 점수를 기록해 P3의 점수 변동이 "의도한 것"인지 "회귀"인지 구분 가능하게.
- **작업**
  - `pytest` 전량 통과 확인 (현재 상태가 green인지)
  - `outcomes/` 해시 대조 재실행
  - 5작물 × 대표 지역 × 12개월 적합도 점수를 고정 픽스처로 스냅샷 → `tests/fixtures/baseline_scores_pre_v6.json`
- **완료조건**: 스냅샷 파일 존재 + 그것을 읽어 현행 산출과 대조하는 테스트가 green.
- **위험**: 스냅샷이 DB 시드에 의존하면 재현 불가 → 픽스처는 `CropGrowthGuide` 객체를 코드로 구성해 DB 없이 돌린다(`test_farmml_contract.py`가 이미 쓰는 방식).

### P1 — 스키마 (마이그레이션 `0038`·`0039`·`0040`)

> 🔴 계약 문서는 "마이그레이션 번호는 `0033`·`0034`"라고 적었지만 **그 번호는 이미 다른 것이 쓴다**
> (`0033_long_term_recommendation`, `0034_daily_recommendation_input_hash`). 다음 빈 번호는 **`0038`**이다.
> `0035`가 같은 오해를 이미 한 번 기록했다.

- `0038` — `crop_growth_guide` 컬럼 신설 (스키마만, 값 없음)
  - `cultivation_type` (`open_field` | `facility`, NULL 허용)
  - `allowed_min_kind` / `allowed_max_kind` (NULL 허용 — 방향별 2컬럼. **하나로 합치지 않는다**: 사과 기온은 하한이 `cultivable_range`, 상한이 `heuristic`이라 합치면 반드시 한쪽이 거짓 표기가 된다)
  - `method` (측정 프로토콜, NULL 허용)
  - `code_scores` (JSONB, NULL 허용 — 등급코드 → 점수 배점표)
- `0039` — 값 백필. `outcomes/memory/crop_rules/*.json`의 값을 그대로 옮긴다. **추측 금지**: JSON에 없는 필드는 NULL로 둔다.
- `0040` — `soil_state.subsoil_texture_code` (원본 등급코드 1~6, 99, NULL). 한글 변환값이 아니라 **코드 원본**을 저장한다.
  - 짝 작업: `app/infra/public_api/soil_profile_client.py`가 `Deepsoil_Qlt_Code`를 한글로 바꾸면서 원본을 버리고 있다 → 원본 보존.
- **완료조건**: `alembic upgrade head` → `downgrade` → `upgrade` 왕복 성공. `test_guide_outcomes_contract.py`가 새 컬럼 값을 `outcomes/` JSON과 대조.
- **위험**: 백필이 `outcomes/` JSON을 런타임에 읽으면 계약 위반(마이그레이션은 자기완결이어야 한다). → `0023`~`0031`이 쓰는 방식대로 **마이그레이션 안에 상수 표를 박고**, 그 표가 `outcomes/`와 같은지는 계약 테스트가 검증한다.

### P2 — 채점 엔진 코어 (`suitability_service.py`)

- `boundary_score(kind)` 신설. `LITERATURE_LIMIT_KIND` / `ALLOWED_BOUNDARY_SCORE` 상수명·값을 이관된 `scoring.py`와 **동일하게** 둔다(텍스트 대조 테스트가 이걸 잡는다).
  - `_indicator_score`가 허용경계에서 쓰는 60을 방향별 `kind`에 따라 0 또는 60으로 분기.
  - 영향: 오이 기온 5·35℃, 상추 기온 2.5·36℃, 감자 기온 27℃.
  - ⚠️ 사과 기온 하한은 `cultivable_range`이지 `literature_limit`이 **아니다**. 잘못 표기하면 사과 0점 지역이 93→121로 늘어난다(FarmML 실측).
- `category_score(code, code_scores)` 신설. `code_scores`가 있는 지침은 `band_score` 경로로 보내지 않는다 — `optimal_min/max`가 없어 예외가 나거나 없는 순위를 가정한다.
- `refuted` 가드 테스트: `rainfall_monthly` 지침이 다시 들어오면 실패.
- **완료조건**: 7개 경계 성격 전부에 대해 `boundary_score()` 값을 계약과 대조하는 테스트 green. P0 스냅샷 대비 변동이 **위 3작물 기온 지표에만** 발생.
- **위험**: `kind` 미지정(NULL) 행이 조용히 0점을 받는 것. → NULL은 명시적으로 60점(종전 동작)이며, 그걸 테스트로 고정한다.

### P3 — 장기 총점 구조 (국가 3단)

- `build_monthly_rows` / `compute_monthly_outlook`에서 주 총점을 `min(soil_total, temp_score)`로 교체.
  - `soil_total` = 토양 지표 **내부 균등 평균**(요인별 점수제 합산). MLCM은 토양 내부에서 쓰지 않는다.
  - `temp_score` = 기온 축 점수. 기후 내부는 최대저해인자법.
  - 토양60/기온40 가중치는 이 구조에서 **쓰이지 않는다**. 가중평균은 `score_weighted`로 병기.
- `limiting_factor` + `limiting_layer` 산출: 총점을 정한 **층을 먼저** 가리킨다. 토양이 결속했으면 그 안의 최악 지표명, 기온이면 `"기온"`.
- **G11 감시**: `주 총점 − 토양 총점`을 응답 아닌 **로그/관리자 엔드포인트**에 집계. 0에 붙어 있으면 기후층이 아무 일도 하지 않는다는 신호(사과는 FarmML 실측에서 정확히 +0.00이었다).
- 단기 탭(`short_term_service`)은 **손대지 않는다**.
- **완료조건**: 장기 응답에 `score`(min 구조)·`score_weighted`·`limiting_factor`·`limiting_layer`. P0 스냅샷과의 차이가 전부 구조 변경으로 설명됨.
- **위험**: 등급 분포가 크게 바뀐다. 계약이 준 FarmML 실측 방향(평탄 min 대비 C등급이 크게 줄어듦)과 **부호가 같은지** 확인한다. 반대면 구현이 틀렸다.

### P4 — 심토토성 (사과·배)

- `0039`에 사과·배 `subsoil_texture` 지침 행 추가 (`code_scores` 채움, `optimal_*`는 NULL).
- `gather_indicator_values`에 `subsoil_texture` 추가 (원본 코드 전달).
- 등급코드 `99`(기타)·코드 부재는 **채점 제외**. 50점으로 메우지 않는다. 결측 노출은 기존 `<지표>:missing` 플래그가 담당.
- **완료조건**: 사과 `사양질`=100 / 배 `사양질`=75, 사과 `미사식양질`=50 / 배 `미사식양질`=100을 값으로 대조하는 테스트.
- **위험**: 🔴 **사과·배 순위가 정반대다.** 공통 토성 규칙을 쓰면 반드시 한쪽이 틀린다. 국가 배점표 자체의 작물별 차이지 계산 오류가 아니다. → P6에서 UI 노출.

### P5 — 계약 테스트 전환

- `TestUntransferredContractItems` 2건을 **값 대조 테스트로 교체**:
  - `boundary_score()`를 7개 성격 전부에서 계약과 대조
  - `category_score()`를 사과·배 배점표 전수 대조
- `test_guide_outcomes_contract.py`에 신규 4컬럼 대조 추가.
- `VERSIONS.json`의 `knowledge_version`/`scoring_version`을 **배포 코드의 계약 버전으로 기록**(체크리스트 8) — 상수로 박고 테스트가 대장과 대조.
- **완료조건**: 계약 문서 체크리스트 0~12 각 항목에 대응하는 테스트 또는 "해당없음" 근거가 존재.

### P6 — API 응답 + FE 표기

**백엔드 필드** (`schemas/suitability.py`, breakdown 항목별):
- `cultivation_type` — 그 밴드가 시설 기준인지 노지 기준인지
- `boundary_kind` — `allowed_min_kind` / `allowed_max_kind`
- `score_tier` — `literature` | `reference`. `derived` 경계 밖 점수는 `reference`

**FE 표기 4건** (`frontend/`):
1. **「시설 기준 적용 중」 꼬리표** — `cultivation_type == "facility"` 밴드. 오이·상추는 토양 7개 전부, 감자는 6개가 시설 기준으로 노지 실측을 채점 중이다. 사용자가 노지 밭 점수를 보면서 그 기준이 시설 기준인지 모르면 안 된다.
2. **사과 `ca` 「기준 초과·참고」 강등** — `allowed_max = 6.5`는 문헌값이 아니라 역산치(염기포화도 80% × CEC 10.0)이고, **상한 밖 감점 기울기에 근거가 국내외 0건**이다. 전국 치환성 Ca 중앙값 7.23이 상한 밖이라 다수 밭이 이 기울기로 감점된다. 「문헌 기반 점수」와 같은 자리에 두지 않는다.
3. **사과·배 토성 순위 역전 안내** — 같은 밭 같은 흙에서 사과 100점·배 75점이 나온다. 버그로 오인되지 않게 근거(국가 배점표의 작물별 차이)를 노출.
4. **EC 스케일 경고** — 흙토람 `elcd`가 1:5 비환산인지 지도자료용 ×5인지 미확인. ×5라면 밴드가 통째로 어긋난다. 제품 설명 + 운영 로그 양쪽에 유지.

- 기존 규칙 준수: 색만으로 등급 구분 금지(라벨 병기, CLAUDE.md §8), `types/farm.ts`의 `INDICATOR_NAMES`를 백엔드와 같은 표기로 유지.
- **완료조건**: 4건이 실제 화면에 뜬다. 스크린샷 또는 컴포넌트 테스트.

### P7 — 리뷰 게이트 + 인계 문서

- `docs/farmml-v6-contract.md` — FE 개발자용 인계 문서(CLAUDE.md §3-7 **필수**). 엔드포인트 계약, 신규 필드, FE가 해야 할 것, 에러 처리, **§1 계약 예외 1건의 근거**.
- 계약 체크리스트 0~12 대조표 (각 항목 → 구현 위치 또는 미적용 근거).

---

## 3. 서브에이전트 분배

오케스트레이션은 **ECC**가 맡는다. 각 Phase는 `ecc:orch-change-feature`(기존 동작 기능 변경 →
테스트를 새 명세로 먼저 갱신 → 구현 → 리뷰 → 게이트 커밋) 한 사이클이다.
P6 FE는 신규 표기라 `ecc:orch-add-feature`.

| Phase | 구현 담당 | 검증 담당 | 게이트 |
|---|---|---|---|
| P0 | `ecc:code-explorer` (현행 채점 경로 추적) | `ecc:tdd-guide` (스냅샷 픽스처) | 전량 green |
| P1 | `voltagent-lang:fastapi-developer` (SQLAlchemy 2.0 + Alembic) | `ecc:database-reviewer` (마이그레이션 안전성·왕복) | upgrade/downgrade 왕복 |
| P2 | `voltagent-lang:python-pro` (순수 채점 함수) | `ecc:tdd-guide` → `ecc:silent-failure-hunter` (NULL kind 조용한 0점) | 7성격 값 대조 green |
| P3 | `voltagent-lang:python-pro` | `voltagent-data-ai:data-scientist` (구조 변경 후 분포가 계약 실측과 부호 일치하는지) | 스냅샷 diff가 전부 설명됨 |
| P4 | `voltagent-lang:fastapi-developer` (클라이언트 코드 보존 + 지침 행) | `ecc:tdd-guide` (배점표 전수 대조) | 사과·배 역전 값 고정 |
| P5 | `ecc:tdd-guide` | `ecc:pr-test-analyzer` (계약 체크리스트 커버리지) | 체크리스트 0~12 전항 대응 |
| P6 BE | `voltagent-core-dev:api-designer` (응답 계약) | `ecc:fastapi-reviewer` | 스키마 계약 확정 |
| P6 FE | `voltagent-lang:nextjs-developer` | `ecc:react-reviewer` + `ecc:a11y-architect` (색만으로 구분 금지) | 4건 화면 노출 |
| P7 | `voltagent-dev-exp:documentation-engineer` | `ecc:orch-review` (다차원 리뷰 + CRITICAL/HIGH 적대적 검증) | 블로킹 findings 0 |

### 에이전트에게 반드시 전달할 제약 (CLAUDE.md §3-2, §9)

모든 서브에이전트 프롬프트에 다음을 박는다:

- **`outcomes/` 파일을 편집하지 않는다.** 다음 미러에서 덮어써진다. 값이 틀렸으면 보고만 한다.
- **FarmML 경로(`../FarmML/**`)를 읽지도 참조하지도 않는다.** 필요한 값은 전부 `outcomes/` 안에 있다.
- **`[확인 필요]` 항목을 임의로 확정하지 않는다.** 특히 EC 스케일, 감자 유기물 재배형 표기, 상추 pH 밴드.
- **농업 기준값을 코드에 하드코딩하지 않는다.** 마이그레이션 시드 또는 DB로만.
- **추측 금지.** 계약 JSON에 없는 필드는 NULL로 둔다.
- 산출물은 **파일 경로 + 전체 코드 + 실행 방법 + 테스트**까지. 조각만 내지 않는다.

### 병렬 가능성

- P1과 P2 설계는 병렬 가능하나 **P2 구현은 P1 머지 후**(컬럼 의존).
- P4는 P1·P2 이후. P3와는 독립이라 병렬 가능.
- P6 FE는 P6 BE 스키마 확정 후.
- 순차 사슬: `P0 → P1 → P2 → P3 → P5 → P6BE → P6FE → P7`, P4는 P2 이후 아무 때나 끼어든다.

---

## 4. 브랜치 / 커밋

CLAUDE.md §14 준수.

| Phase | 브랜치 |
|---|---|
| P0 | `feature/backend-v6-baseline` |
| P1 | `feature/backend-guide-meta-columns` |
| P2 | `feature/backend-boundary-kind-scoring` |
| P3 | `feature/backend-national-total-score` |
| P4 | `feature/backend-subsoil-texture` |
| P5 | `feature/backend-v6-contract-tests` |
| P6 | `feature/frontend-v6-disclosure` |
| P7 | `docs/farmml-v6-handoff` |

전부 `dev`에서 분기 → `dev`로 PR. `main` 직접 푸시 금지. 리뷰 1인 이상 승인.
커밋: Conventional Commits, 한 커밋 = 한 논리 변경.

---

## 5. 위험

| 위험 | 완화 |
|---|---|
| 🔴 **P3이 전 사용자 점수를 바꾼다** | P0 스냅샷 대비 diff를 전수 설명. 계약이 준 FarmML 실측 방향과 부호 대조 |
| 🔴 사과 주 총점이 사실상 토양 총점 (기온이 min에서 결속 안 함) | G11 감시 지표로 상시 관측. 계약도 `[확인 필요]`로 남긴 미해결 사안 |
| 마이그레이션 백필이 `outcomes/`를 런타임 참조 | 상수 표를 마이그레이션 안에 박고, 일치는 계약 테스트가 검증 |
| `allowed_*_kind` NULL 행이 조용히 0점 | NULL = 60점(종전 동작)을 테스트로 고정 |
| 시설 밴드로 노지 채점하는 20개 지표 | 값은 안 바꾼다(사용자 결정). P6-1 꼬리표로 노출만 |
| 상추 pH 밴드(6.5~7.0)로 103지역이 제한요인 | 재개조건 미충족(흙토람 진단기준표 원문 + pH 추출법). **이번 범위 아님** |
| `soil_change_rule` LIMING 행 투입 시 감자 오추천 | 현재 0행. 그 행을 넣는 PR이 `crop_id` 추가의 트리거임을 여기 기록 |

---

## 6. 완료 정의

1. `pytest` 전량 green.
2. `test_farmml_contract.py::TestUntransferredContractItems`가 **값 대조 테스트로 교체**됨.
3. 계약 체크리스트 0~12 각 항목에 구현 위치 또는 미적용 근거가 대응됨.
4. `docs/farmml-v6-contract.md` FE 인계 문서 존재.
5. FE 표기 4건이 실제 화면에 노출.
6. `knowledge_version` / `scoring_version` = `2026-08-05-v6`가 배포 코드에 기록됨.
