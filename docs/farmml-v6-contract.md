# FarmML v6 계약 인계 (FE 개발자)

> 상태: **설계 확정 · 구현 중** (2026-08-05 P7 인계 단계).  
> 범위: P0~P6 완료. 근거: `finalplan.md`, `outcomes/README.md`.  
> 대상: 장기 탭 점수 구조·신규 필드 (단기 탭은 무변경).

---

## 엔드포인트 계약

모든 응답은 공통 래퍼 (`ApiResponse`): 성공 `{ "success": true, "data": ..., "error": null }`, 실패 `{ "success": false, "data": null, "error": { "code": str, "message": str } }`.

### `GET /api/v1/farms/{farm_id}/suitability` — 단일 적합도

오늘 날짜 기준 적합도(장기 탭 메인 카드).

**요청**
- 경로: `farm_id` (정수, 유저 소유 밭)
- 인증: `Authorization: Bearer <access_token>`

**성공 응답 (200)**
```json
{
  "success": true,
  "data": {
    "farm_id": 5,
    "crop_id": 1,
    "region_id": 120,
    "growth_stage": "blooming",
    "as_of": "2026-08-05",
    "status": "ok",
    "score": 72.3,
    "grade": "A",
    "score_weighted": 68.5,
    "limiting_factor": "일 평균기온",
    "limiting_layer": "기온",
    "label": "문헌 기반 예상 적합도",
    "breakdown": {
      "temp_day": {
        "value": 28.1,
        "score": 65.0,
        "weight": 1.0,
        "status": "risk",
        "baseline": null,
        "correction": null,
        "confidence": null,
        "source_ref": null,
        "cultivation_type": null,
        "boundary_kind": "heuristic",
        "score_tier": "literature",
        "allowed_min": 18.0,
        "allowed_max": 25.0
      },
      "ph": {
        "value": 6.2,
        "score": 100.0,
        "weight": 1.0,
        "status": "optimal",
        "confidence": "domestic_measured",
        "source_ref": "흙토람 2026-07",
        "cultivation_type": "open_field",
        "boundary_kind": null,
        "score_tier": "literature",
        "allowed_min": 5.75,
        "allowed_max": 6.75
      },
      "organic": {
        "value": null,
        "score": null,
        "weight": null,
        "status": "missing",
        "cultivation_type": null,
        "boundary_kind": null,
        "score_tier": null
      },
      "subsoil_texture": {
        "value": 2.0,
        "score": 100.0,
        "weight": 1.0,
        "status": "category",
        "confidence": null,
        "source_ref": null,
        "cultivation_type": "open_field",
        "boundary_kind": null,
        "score_tier": "literature"
      }
    },
    "risk_flags": [
      "temp_day:outside_allowed",
      "organic:missing"
    ],
    "limitations": [
      "지침 지표 8개 중 7개로만 채점한 점수입니다. 데이터가 없어 반영되지 않은 지표: 유기물.",
      "다음 지표는 시설재배 기준표로 채점합니다(노지 기준표가 없어 그대로 사용) — 유기물. 노지 밭이면 실제보다 후하거나 박하게 나올 수 있습니다.",
      "일 평균기온은 실측이 아니라 월 평균기온 근사입니다.",
      "기상값은 기상청 30년 평년값(1991~2020)이 아니라 최근 5년(2021~2025) 관측 평균입니다. 30년 평년값보다 연평균 약 1℃ 따뜻하며 그 차이는 달마다 다릅니다(-0.3 ~ +2.0℃).",
      "기온·강수는 과거 평균에 기상청 3개월전망(확률예보)을 반영해 보정했습니다. 전망이 없는 월·지표(야간최저기온·일조 등)는 과거 평균을 그대로 씁니다."
    ]
  },
  "error": null
}
```

**실패 (4xx/5xx)**
- `404` `FARM_NOT_FOUND` — 밭이 없거나 소유하지 않음(행 수준 보안 §11)
- `401` `UNAUTHORIZED` — 토큰 없음/만료
- `422` `VALIDATION_ERROR` — farm_id 형식 오류

---

### `GET /api/v1/farms/{farm_id}/monthly-outlook` — 월별 히트맵 (3개월)

오늘 기준 당월~2개월 후 전망(장기 탭 히트맵).

**요청**
- 경로: `farm_id`
- 인증: 필수

**성공 응답 (200) — 주요 필드만**
```json
{
  "success": true,
  "data": {
    "farm_id": 5,
    "crop_id": 1,
    "region_id": 120,
    "label": "문헌 기반 예상 적합도",
    "months": [
      {
        "year": 2026,
        "month": 8,
        "growth_stage": "blooming",
        "status": "ok",
        "score": 72.3,
        "grade": "A",
        "score_weighted": 68.5,
        "limiting_factor": "일 평균기온",
        "limiting_layer": "기온",
        "risk_flags": ["temp_day:outside_allowed"],
        "outlook_applied": true,
        "outlook_published_at": "2026-07-23T00:00:00"
      },
      {
        "year": 2026,
        "month": 9,
        "growth_stage": "ripening",
        "status": "ok",
        "score": 78.1,
        "grade": "A",
        "score_weighted": 75.2,
        "limiting_factor": null,
        "limiting_layer": null,
        "risk_flags": [],
        "outlook_applied": false,
        "outlook_published_at": null
      },
      {
        "year": 2026,
        "month": 10,
        "growth_stage": null,
        "status": "out_of_season",
        "score": null,
        "grade": null,
        "score_weighted": null,
        "limiting_factor": null,
        "limiting_layer": null,
        "risk_flags": [],
        "outlook_applied": false,
        "outlook_published_at": null
      }
    ],
    "limitations": [
      "월별 전망은 과거 기상 평균 기반 이론 추정이며 실제 예보가 아닙니다.",
      "각 월의 생육단계는 그 달에 가장 많은 날을 차지한 단계로 표기합니다 — 한 달에 두 단계가 걸치면 짧은 쪽은 표기되지 않습니다.",
      "토양 지표는 3개월 전체에 현재 추정값을 동일 적용합니다(월별 토양 변화는 반영하지 않음)."
    ]
  },
  "error": null
}
```

**주의**
- `months`의 연도는 칸마다 있다 — 창이 해를 넘기므로(예: 11~12월·1월) 칸마다 달라짐.
- `status` = `"dormant"`면 `score`/`grade`/`limiting_*`은 `null` — 기상 판정 근거 없음(계절 밖).

---

### `GET /api/v1/farms/{farm_id}/long-term-advice` — 추천 문구

히트맵을 기반으로 생성된 자연어 추천(LLM 또는 규칙 기반, 별도 요청).

**요청**
- 경로: `farm_id`
- 인증: 필수

**성공 응답 (200)**
```json
{
  "success": true,
  "data": {
    "text": "사과는 현재 개화기입니다. 8월 기온이 평년보다 높을 것으로 예상되는데, 착과 후 과실비대를 위해 적절한 수분 관리가 필요합니다. 9월부터는 기온이 점차 하강하여 착색 조건이 개선될 것으로 보입니다.",
    "is_llm": true
  },
  "error": null
}
```

- `is_llm: false` — LLM 실패/미도달 → 규칙 기반 문구. 다듬어진 것처럼 보이게 하지 않음.
- 항상 `text`가 채워져 있음(LLM 장애 시 폴백).

---

## 신규 응답 필드 상세

### 1. `cultivation_type` (지표별)

그 밴드의 재배형 기준 — `"open_field"` (노지) 또는 `"facility"` (시설).

**의미**
- 오이·상추·감자의 토양 지표 일부가 RDA 시설재배 기준표로 적용되며, 노지 실측을 시설 기준으로 채점하고 있다.
- 사용자가 "노지 밭인데 왜 점수가 낮은가"를 이해할 수 없음 — **반드시 UI에 노출**.

**FE 표기 (§G7-1)**
- `cultivation_type == "facility"`인 지표 옆에 「시설 기준 적용 중」 꼬리표 표시.
- 카드/히트맵 모두 적용.

**예시**
- 오이·상추: 토양 7개 전부 시설 기준
- 감자: 유기물·유효인산·K·Ca·Mg·EC (pH는 노지)

---

### 2. `boundary_kind` (지표별, 채점된 것만)

점수를 정한 **방향의** 허용경계 성격. 한 밴드의 하한·상한이 다른 성격일 수 있어 결속한 쪽만 낸다.

**가능한 값**
- `"literature_limit"` — 문헌 생리적 절대한계 (생장 0점). **허용경계 0점**.
- `"cultivable_range"` — arccas 적지 범위. 허용경계 60점.
- `"literature_threshold"` — 학술적 임계값. 허용경계 60점.
- `"heuristic"` — optimal 폭의 ±50% 휴리스틱. 허용경계 60점.
- `"derived"` — 우리가 역산한 경계 (문헌값 아님). 허용경계 60점 → **P6에서 「참고」로 표기**.

**중요**
- 사과 기온 하한은 `cultivable_range`(적지), 상한은 `heuristic`(±50%).  
  한 밴드에서 성격이 갈리므로 한 컬럼에 합치면 반드시 한쪽이 거짓 표기된다.
- `status == "optimal"`(최적구간)·`"category"`(등급코드)·`"missing"`/`"invalid"` 등 채점 자체가 없으면 `None`.

---

### 3. `score_tier` (지표별, 채점된 것만)

이 점수가 문헌 기반(`"literature"`)인지 참고용(`"reference"`)인지.

**규칙**
- `"literature"` — 모든 채점된 지표(optimal/allowed/risk non-derived/category).
- `"reference"` — `status == "risk"` **AND** `boundary_kind == "derived"`.
  - 유일한 현재 대상: 사과 `ca.allowed_max = 6.5` (역산치, 근거 없음).

**FE 표기 (§G7-3)**
- 그래프/카드에서 `"reference"` 점수는 「참고」 표시.
- 「문헌 기반 점수」와 같은 자리에 두지 않기.

---

### 4. `score_weighted` (응답 최상위, 장기만)

종전 토양60/기온40 **가중평균** 총점 (부차 지표).

**의미**
- P3(2026-08-05) 주 총점이 `score = min(토양 축, 기후 축)`으로 구조 변경됨.
- min에는 가중 개념이 없음 → 가중평균은 병기만.
- **단기 탭은 무변경** (가중평균 유지).

**주의**
- `score` ≠ `score_weighted` (둘 다 있음!)
- 오늘 기준: `score`가 주 판정, `score_weighted`는 참고.
- 히트맵: 같은 밭·같은 달이면 대시보드와 히트맵이 같은 `score` 값을 보임.

---

### 5. `limiting_factor` / `limiting_layer` (응답 최상위, 장기만)

총점을 결속한 **축**과 그 축 안의 **지표**.

**구조 (국가 적지평가 3단)**
1. 토양 축: 지표 균등평균 (K·Ca·Mg·pH·EC·유기물·토성 등의 평균)
2. 기후 축: 최대저해인자법 (기온·강수의 min)
3. 총점: 위 둘의 min

**필드**
- `limiting_layer`: `"토양"` 또는 `"기온"` — 어느 축이 결속했는가.
- `limiting_factor`:
  - 토양 결속 → `INDICATOR_NAMES`의 한글명 (예: "일 평균기온", "토양 산도(pH)")
  - 기후 결속 → `"기온"` (고정)
  - 기상 지표가 없는 달 → `None`

**사용례**
```javascript
if (response.limiting_layer === "토양") {
  console.log(`토양의 ${response.limiting_factor}이 제한요인입니다`);
} else {
  console.log(`${response.limiting_factor}(${response.limiting_factor === "기온" ? "월평년)" : "기타"}`);
}
```

---

## 점수 구조 변경 — FE가 꼭 알아야 할 것

### 장기 탭만 변경

| 항목 | P2 이전 | P3 이후 (2026-08-05) |
|---|---|---|
| 주 총점 정의 | 가중평균 (토양60·기온40) | min(토양 축, 기후 축) |
| 가중평균 | 주 판정 | 부차 지표 (`score_weighted`) |
| 단기 탭 | — | **무변경** (가중평균 유지) |

### 두 탭의 총점이 이제 다르다

- **장기 탭**: `score` = 국가 3단 구조 min
- **단기 탭**: `score` = 가중평균 (P2와 동일)
- FE가 같은 밭을 보면서 "장기와 단기 점수가 왜 다른가" 혼동할 수 있음 — **두 탭이 다른 구조를 쓴다는 것을 문서/UI에 명시**.

### 등급 분포 변화

min 구조 도입으로 C등급이 매우 줄어들었다 (P0 스냅샷 대비 확인 필요).  
이것은 **실수가 아니라 의도된 구조 변경**.

---

## `limitations` 배열의 새 문구 3종

`FarmSuitability.limitations`와 `MonthlyOutlookEntry`에 들어가는 배열. 화면에 그대로 노출하므로 **백엔드·FE 양쪽에서 값을 복제하면 안 됨**.

### 1. 시설 기준 적용 (조건부)

```
다음 지표는 시설재배 기준표로 채점합니다(노지 기준표가 없어 그대로 사용) — 유기물·유효인산·K·Ca·Mg·EC. 노지 밭이면 실제보다 후하거나 박하게 나올 수 있습니다.
```

- 지표명 부분은 **동적** (위 `cultivation_type` 로직에서 나옴)
- 오이·상추·감자만 해당.

### 2. 심토토성 순위 역전 (조건부)

```
심토 토성 점수는 작물마다 순위가 다릅니다 — 같은 흙이 사과에서는 최적, 배에서는 보통이 될 수 있습니다. 국가 토양 적지평가 배점표가 작물별로 다르기 때문이며 오류가 아닙니다.
```

- 지침에 `subsoil_texture`가 있을 때만 표기.
- **버그 의심 방지** 필수.

### 3. EC 스케일 경고 (조건부)

```
토양 염류(EC)는 측정 환산 방식이 확정되지 않아 값이 실제보다 크거나 작을 수 있습니다 — EC 점수는 참고로만 보십시오.
```

- 지침에 `ec`가 있을 때만 표기.
- **[확인 필요]** 항목 — 흙토람 elcd가 1:5 비환산인지 ×5 환산인지 미확정.

---

## 에러 처리

### HTTP 상태 코드

| 코드 | 에러 코드 | 메시지 | 의미 | FE 처리 |
|---|---|---|---|---|
| 404 | `FARM_NOT_FOUND` | "밭을 찾을 수 없습니다." | 없거나 소유하지 않음 | 404 화면 또는 "밭이 삭제되었을 수 있습니다" |
| 401 | `UNAUTHORIZED` | "인증이 필요합니다" | 토큰 없음 | 로그인 화면 |
| 401 | `INVALID_TOKEN` | "토큰이 만료되었습니다" | 만료/위조 | refresh 1회 후 재시도 → 실패하면 재로그인 |

### `status` 필드 (응답 본문)

지침과 데이터의 관계를 나타냄. **다른 필드와 함께 읽어야 함** — `status`만으로 판단하면 안 됨.

| status | 의미 | score | grade | UI |
|---|---|---|---|---|
| `"ok"` | 정상 산출 | 채움 | 채움 | 점수·등급 표시 |
| `"dormant"` | 기상 판정 근거 없음 (계절 밖) | **null** | null | "이 시기는 평가 대상이 아닙니다" |
| `"out_of_season"` | 지침 자체가 없음 (예: 배 겨울) | null | null | "현재 단계 지침이 없습니다" |
| `"insufficient_data"` | 지표 전부 결측/이상 | null | null | "데이터 부족" |

---

## 계약 예외 1건 (근거)

### `rainfall_daily` — 단기만 유지, 장기는 제외

| 구분 | 상황 | 채점 여부 |
|---|---|---|
| **장기 탭** | 평년치는 월 단위라 일 강수량 입력 불가 | **제외** (`SEASONAL_UNAVAILABLE_INDICATORS`) |
| **단기 탭** | 기상청 예보 일누적(mm/일) 사용 가능 | **유지** (5작물, weight 1.5) |

**근거**
- FarmML `weights.precipitation = 0` (시즌 채점 계약) vs 백엔드 단기 `rainfall_daily`(weight 1.5, 5작물).
- **어긋나지만 의도된 것**: 시즌 채점(장기)과 단기 예보는 다른 축. 문헌 "일 30~50mm" 기준이 있어 단기에서는 실제로 필요.
- 장기: 이미 `SEASONAL_UNAVAILABLE_INDICATORS`로 제외해 **계약 일치**.

---

## 계약 체크리스트 0~12 — 구현 위치

목표: 체크리스트 항목 → 백엔드 구현 매핑 (또는 의도적 제외 근거).

| # | 항목 | 구현/상태 |
|---|---|---|
| **0** | 결측 제외 + 버전 기록 | `calculate_suitability`(제외 로직) + `contract_version.py` |
| **1** | 작물별 밴드만 | DB 시드 (migrations 0023·0024·0028·0029·0031·0035) |
| **2** | 단측 밴드 + 로그 감쇠 | `_indicator_score` (optimal_min/max 중 하나만 None 허용) |
| **3** | `code_scores` → `category_score` 분기 | `calculate_suitability` (guide.code_scores ≠ null) + migrations 0041 |
| **4** | 주 총점 min 구조 | `national_total` (min(토양 균등평균, 기후 min)) |
| **5** | 배수등급 U자형 | **제외** — 데이터 없음 |
| **6** | EC 경고 유지 | `EC_SCALE_LIMITATION` (limitations에 동적 추가) |
| **7** | 판단자료 | **미이관** — 산출 CSV 트랙 폐기 |
| **8** | 버전 기록 | `contract_version.py` (`KNOWLEDGE_VERSION`·`SCORING_VERSION`) |
| **9** | 토성 순위 역전 노출 | `SUBSOIL_TEXTURE_RANK_LIMITATION` (limitations 조건부) + FE 표기 (P6-3) |
| **10** | `refuted` 미채점 | 감자 월강수(0013) 삭제 → 계약 일치. `refuted` 가드는 테스트로만 |
| **11** | 기온 보정(+0.36℃) `literature_limit`엔 미적용 | FarmML 소관. 백엔드는 보정된 값을 시드로 받음. 보정 코드 없음 확인됨 |
| **12** | `derived` 경계 밖 「참고」 | `score_tier` (reference/literature) + P6 FE 표기 |

**미적용 항목 근거**
- 5번: 데이터 없음. 향후 있으면 추가 가능.
- 7번: 지역 점수 산출 트랙 폐기 (2026-08-05 사용자 결정, finalplan §0).
- 11번: 기온 보정은 FarmML 시드 입력 (백엔드는 이미 보정된 값을 받음).

---

## 미해결·인수인계 사항

### 1. 심토토성 적재 배선 부재

**현재 상태**
- 채점 경로·지침·테스트: **완성**
- 값 적재: **미해결**

**원인**
- `soil_state.subsoil_texture_code`를 채우는 경로가 **없음**.
- `soil_profile_client.get_soil_profile` 호출자: 0건.
- 그 클라이언트는 PNU(19자리 지번코드)를 요구하는데 `user_farm`은 `bjd_code`(읍면동)까지만 알고 있음.

**해결 방법**
1. `user_farm`에 PNU 추가 저장 (또는 다른 좌표 데이터).
2. 흙토람 API 호출 로직 다시 활성화.
3. 마이그레이션 0040으로 기존 토양 상태에 코드 역채우기.

**다음 사람이 할 일**
- 흙토람 API 스키마 재확인 (최신인지).
- user_farm 컬럼 추가 검토 (위치 데이터 중복 여부).
- 마이그레이션 작성 (PNU 유입 시점부터 역채우기).
- 결측(예: 일반도시지역) 처리 정의.

---

### 2. 로컬 dev DB 오염

**현재 상태**
- `alembic_version = 0037`인데 0012·0021·0023·0024·0031·0035의 데이터 효과 빠짐.
- 지표 밴드: 48행이 아니라 40행. 값 상이 14건 (예: 사과 pH 5.5~7.0 vs 계약 5.75~6.75).

**원인**
- 누군가 마이그레이션을 실행하지 않고 `alembic stamp`만 함.
- 또는 백업 복원 후 재stamp.

**복구 방법**
1. `foryourfarm` DB 삭제.
2. 빈 DB에서 `alembic upgrade head` 체인 실행.
3. 확인: `backend/alembic/versions/0039_guide_boundary_kind_backfill.py`의 상수 표가 실제 48행과 일치하는지.

**이제 조용히 넘어가지 않는다.** `0039`의 `upgrade()`가 실행 시점에 각 행의 `allowed_min`/`allowed_max`를 성격 판정 근거와 대조하고 다르면 `RuntimeError`로 멈춘다. 오염된 DB에서는 다음 메시지가 뜨고 트랜잭션이 롤백되어 리비전이 0037에 머문다:

```
RuntimeError: 0039: crop=1 ph 허용경계가 성격 판정 근거와 다르다 —
DB (Decimal('5.5'), Decimal('7.0')) vs 기대 (Decimal('5.75'), Decimal('6.75')).
```

이 가드가 필요한 이유: 계약 테스트(`test_guide_outcomes_contract.py`)는 DB 없이 상수 표만 대조하므로 **DB 쪽 밴드 드리프트를 잡을 수 없다.** 밴드가 계약과 다른 DB에 계약 성격을 붙이면 `literature_limit` 0점 경계가 문헌이 말하지 않은 지점으로 옮겨간다.

**다음 작업 할 사람용**
- 지금 dev DB를 쓰고 있다면 복구 후 다시 시작.
- `pytest test_guide_outcomes_contract.py` 실행해서 시드 값 대조.

---

### 3. 제외 항목 (의도적)

계획 §1에서 명시적으로 제외된 항목들. **이번 범위 밖**.

| 항목 | 이유 |
|---|---|
| `slope_pct` / `gravel_pct` 채점 | 다음 라운드. 기존 `band_score` 경로 재사용 가능해 급하지 않음. |
| `soil_change_rule.crop_id` | 팀 보류. 현재 시드 행 **0건**이라 LIMING 오추천 위험 없음. 행 추가 PR이 이 항목의 트리거. |
| 배수등급 U자형 | 데이터 없음. (계약도 미이관) |
| 단기 탭 총점 구조 변경 | 범위 밖 (장기만 변경). |
| 사과 arccas 2단 지표 | 계약이 값을 이관하지 않음. |

---

### 4. G11 — 기후층 무동작 감시 (상시 관측 대상)

🔴 **현 구조의 근본 한계**: 생육적온은 월평균 기온에 거의 항상 만족돼(계약 실측 사과 기온 점수 평균 99.5, S 148/150) `min`에서 결속하지 않는다. 계약 실측에서 사과는 **주 총점이 토양 총점과 완전히 같았다**(`national_minus_soil_mean` = +0.00) — 즉 주 총점이 실질적으로 토양 총점이다. 계약도 이 사안을 `[확인 필요]`로 남겼다.

그 감시 수단이 계약 쪽에서 사라졌으므로(그 필드는 이관되지 않는 `regional_score_manifest.json`에 있었다) **백엔드가 자기 산출에서 직접 감시한다.**

| 항목 | 값 |
|---|---|
| 구현 | `app/services/suitability_service.py::_log_national_total_climate_delta` |
| 로거 | `logging.getLogger("app.services.suitability_service")` — `app/core/log_config.py`의 구조화 로깅을 탄다 |
| 레벨 | `INFO` |
| 로그 접두 | `national_total climate_delta` |
| 필드 | `crop_id` `region_id` `year` `month` `score` `soil_total` `temp_score` `delta` |
| `delta` 정의 | `주 총점 − 토양 총점` (소수 2자리) |

**응답 필드로 내지 않는다** — 프론트가 쓰지 않는 값이고 집계는 로그 쪽에서 한다. 새 테이블·새 관리자 엔드포인트도 만들지 않았다.

**읽는 법**: `delta`가 0에 붙어 있으면 그 작물에서 기후 축이 아무 일도 하지 않는다는 신호다. 두 축이 모두 채점된 경우에만 로그를 남긴다(한쪽이 비면 `delta`가 항상 0이라 신호가 아니다). 로그 실패는 응답 경로를 막지 않는다.

**Cloud Logging 예시 쿼리**
```
jsonPayload.message =~ "national_total climate_delta" AND jsonPayload.message =~ "delta=0.0"
```

---

### 5. 그 밖의 남은 것

| 항목 | 상태 |
|---|---|
| 상추 pH 밴드 `6.5~7.0`(시설 기준) | 전국 밭 pH 중앙값 5.9가 밴드 밖이라 계약 실측에서 103지역의 제한요인이었다. 원인이 ① 우리 pH 추출법이 문헌과 다른 것인지 ② 전국 밭이 상추 기준으로 실제 산성인지 판단 근거가 없다. **재개조건: 흙토람 공식 진단기준표 원문 1건 + pH 추출법 확인.** 문헌 없이 밴드를 넓히지 않았고 상추만 pH를 채점에서 빼지도 않았다 — 한 작물만 빼면 문제를 보고하는 대신 감추는 것이 된다. |
| 감자 유기물 재배형 표기 | `[확인 필요]` — `potato.json`의 `organic_matter`는 `cultivation_type: "facility"`인데 같은 필드 `source`가 2010 개정증보판 노지 행도 20~30이라고 적어놨다. 둘 다 참일 수 없다. **값을 바꾸지 않고 그대로 옮겼다**(추측 확정 금지). 시설 기준 안내에 이 지표가 포함돼 나간다. |
| `INDICATOR_SOURCE_FIELDS` (`suitability_service.py`) | **참조하는 코드가 0건인 죽은 맵**이고 `k`·`ca`·`mg`·`subsoil_texture`가 빠져 있다. 이번 작업이 만든 문제가 아니라 기존 상태이며 손대지 않았다 — 정리 대상으로 기록. |

---

## 검증 방법

### FE·BE 개발자 자체 검증

아래는 실제로 실행해 통과를 확인한 명령이다. 백엔드는 `backend/.venv`를 쓴다 — 시스템 python으로는 의존성이 없어 수집 단계에서 31개 오류가 난다.

```bash
# 1. 백엔드 전량 테스트 (기준: 684 passed, 2342 subtests, 0 failed)
cd backend
.venv/Scripts/python.exe -m pytest -q

# 2. 계약 테스트만
.venv/Scripts/python.exe -m pytest -q \
  tests/test_farmml_contract.py tests/test_guide_outcomes_contract.py tests/test_baseline_scores.py

# 3. baseline 스냅샷 변동 표 보기 (P2·P3 변동이 "설명된 변동"인지)
.venv/Scripts/python.exe -m pytest -q -s tests/test_baseline_scores.py
#  ⚠️ tests/fixtures/baseline_scores_pre_v6.json 은 v6 이전 영구 기록이다. 재생성하지 말 것 —
#     덮어쓰면 회귀가 조용히 통과한다. 재생성 명령은 그 테스트 파일 docstring에 있다.

# 4. 프론트엔드
cd ../frontend
npx tsc --noEmit          # TypeScript: No errors found
npm run test              # 8 passed (lib/disclosure.ts 표기 분기)
npm run build             # ✓ Compiled successfully
```

**Alembic 왕복** — 🔴 **빈 DB에서만 한다.** 오염된 dev DB에서는 `0039` 가드가 정상적으로 실패시킨다(위 §2 참고). `downgrade base`를 쓰지 말 것 — 전 테이블을 지운다. v6 구간만 되짚으면 충분하다.

```bash
docker compose up -d db
docker exec foryourfarm-db psql -U foryourfarm -d postgres \
  -c "CREATE DATABASE fyf_replay OWNER foryourfarm;"

cd backend
export DATABASE_URL="postgresql+psycopg://foryourfarm:foryourfarm@localhost:5432/fyf_replay"
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m alembic downgrade 0037   # v6 이전으로
.venv/Scripts/python.exe -m alembic upgrade head     # 다시 head
```

빈 DB 체인 replay 결과가 기준값이다: `crop_growth_guide` **50행**(v6 이전 48행 + `0041`의 사과·배 심토토성 2행), `literature_limit` 경계 8건(오이 기온 하한·상한, 상추 spring·fall 하한·상한, 감자 early·tuber **상한만**), 사과 기온 3행은 성격 전부 NULL.

**`outcomes/` 버전 대조** — 계약 문서의 명령은 `outcomes/`를 작업 디렉터리로 두고 실행한다(경로가 그 디렉터리 기준 상대경로다).

```bash
cd outcomes
python -c "
import hashlib, json, pathlib
v = json.load(open('VERSIONS.json', encoding='utf-8'))
print(v['knowledge_version'], '/', v['scoring_version'])
bad = 0
for rel, meta in v['files'].items():
    p = pathlib.Path(rel)
    if not p.is_file():
        print('MISSING', rel); bad += 1; continue
    if hashlib.sha256(p.read_bytes()).hexdigest() != meta['sha256']:
        print('MISMATCH', rel); bad += 1
raise SystemExit(bad)
"
# exit 0 → v6 원본과 바이트 동일. 같은 대조를 pytest 쪽에서도 한다
# (test_farmml_contract.py::TestOutcomesLedger).
```

### 계약 검증 체크리스트

- [ ] `score = min(토양, 기온)` 구조 (단기는 그대로).
- [ ] `score_weighted`가 가중평균인가? (부차 지표)
- [ ] `limiting_factor`/`limiting_layer` 결속 방향이 정확한가?
- [ ] `cultivation_type` 노출 (오이·상추·감자만).
- [ ] `boundary_kind`와 `score_tier`가 모두 들어가는가?
- [ ] `limitations` 배열이 동적으로 생성되는가? (하드코딩 금지)
- [ ] 단기 탭 `score`는 가중평균 유지하는가? (무변경)
- [ ] `status = "dormant"`일 때 `score` = null인가?
- [ ] 지침 오류/결측 시 `risk_flags`에 기록되는가?

---

## FE가 해야 할 것 (요약)

### ✅ 이번 릴리스에서 구현 완료된 것

아래 4건은 이미 반영됐다(`54586c0`). 다시 만들 필요 없다.

| # | 구현 위치 |
|---|---|
| 1 시설 기준 꼬리표 | `components/DayDetailModal.tsx` ScoreRows 지표명 옆 + `limitations` 문구(장기 탭엔 지표 UI가 없어 이 경로로도 낸다) |
| 2 참고 점수 강등 | 같은 표 점수 셀, `role="note"`로 분리 |
| 3 토성 순위 안내 | `limitations` 배열 — `Limitations.tsx`가 자동 렌더, FE 코드 변경 없음 |
| 4 EC 경고 | 같음 |

조건 판정은 `frontend/lib/disclosure.ts`의 순수 함수(`isFacilityIndicator`·`isReferenceTierScore`)에 있다. 컴포넌트에 인라인하지 말고 그 함수를 쓴다(`CLAUDE.md` §8).

### 🔴 아직 화면에 안 나오는 신규 필드 3개 — 다음 라운드 작업

백엔드가 내려주고 `types/farm.ts`에 타입도 있으나 **렌더하는 곳이 없다.** 이번 릴리스 범위(계획 P6은 표기 4건만 규정)에 포함되지 않았다.

| 필드 | 왜 필요한가 | 제안 위치 |
|---|---|---|
| `limiting_factor` | v6로 총점 정의가 바뀌어 점수가 크게 떨어진 달이 생기는데, 사용자는 게이지 숫자와 등급만 보고 **왜 떨어졌는지**를 알 수 없다. 이 필드가 정확히 그 답이다 | `LongTermPanel.tsx` `MonthCell` — 예: 「제한요인: 유효인산」 |
| `limiting_layer` | 제한요인이 토양 얘기인지 기온 얘기인지 먼저 알려준다 | 같음 |
| `score_weighted` | 종전 가중평균. 구조 변경 전후를 비교해 보여주고 싶을 때만 | 상세 화면(선택) |

⚠️ 표시할 때 `limiting_layer`를 먼저 읽어라 — `limiting_factor`가 `"기온"`이면 그것이 곧 층 이름이고, 토양이면 그 층 **안의 최악 지표명**이다.

### P6 신규 UI 표기 4건 — 조건 명세 (참고)

1. **「시설 기준 적용 중」 꼬리표**  
   - 조건: breakdown의 지표가 `cultivation_type == "facility"`
   - 위치: 지표명 옆 (카드/히트맵)
   - 범위: 오이·상추·감자 토양 지표 일부

2. **사과 Ca 「기준 초과·참고」 강등**  
   - 조건: `score_tier == "reference"`
   - 위치: 점수 옆 (「문헌 기반 점수」와 다른 자리)
   - 예: 「참고」 또는 「기준 초과」

3. **사과·배 토성 순위 역전 안내**  
   - 조건: 지침에 `subsoil_texture` 있음
   - 위치: `limitations` 배열에서 자동 표기 (백엔드가 넣음)
   - 실제로 버그 아닌 것을 알려줌

4. **EC 스케일 경고**  
   - 조건: 지침에 `ec` 있음
   - 위치: `limitations` 배열
   - 내용은 백엔드가 제공

### 점수 구조 이해

```typescript
// 장기 탭
const { score, score_weighted, limiting_layer, limiting_factor } = suitability;
// score = min(토양축, 기후축) — 주 판정
// score_weighted = 가중평균 — 참고값
// limiting_layer = "토양" | "기온"
// limiting_factor = 지표명 또는 "기온"

// 단기 탭
// score = 가중평균 (P2와 동일, 변경 없음)
// score_weighted 미존재 (없음)
```

### status 분기

```typescript
if (status === "dormant") {
  // 기상 판정 근거 없음 — score 미노출
  showMessage("이 시기는 평가 대상이 아닙니다");
} else if (status === "out_of_season") {
  // 지침 자체가 없음
  showMessage("현재 단계 지침이 없습니다");
} else if (status === "insufficient_data") {
  // 데이터 전부 결측
  showMessage("데이터 부족");
} else {
  // "ok" — score/grade 표시
  showCard(score, grade, limiting_factor);
}
```

### 오류 처리

```typescript
try {
  const data = await fetch(`/api/v1/farms/${farmId}/suitability`, {
    headers: { Authorization: `Bearer ${access}` },
  });
} catch (e) {
  if (e.code === "FARM_NOT_FOUND") {
    // 404: 밭이 없거나 삭제됨
    navigate("/farms");
  } else if (e.code === "UNAUTHORIZED") {
    // 401: 토큰 만료 → refresh → 재시도 (middleware 처리)
  }
}
```

---

## 배포 이슈 (알려진 것)

현재 없음. P1~P6 완료 시점 추가 예정.

---

## 문의·피드백

- 엔드포인트 응답 구조 불명: `backend/app/schemas/suitability.py` 참조.
- 점수 산출 로직: `backend/app/services/suitability_service.py` (함수별 주석 상세).
- 테스트: `backend/tests/test_farmml_contract.py` (계약 값 대조).

---

**마지막 갱신**: 2026-08-05 (P7)  
**대상 계약**: `outcomes/README.md` v6 (`knowledge_version` / `scoring_version` = `2026-08-05-v6`)
