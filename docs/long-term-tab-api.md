# 장기 탭 API 계약 (FE 인계)

> 대상: 프론트엔드 개발자 · 기준일 2026-07-25
> 범위: 장기 탭(시즌 커리큘럼·예방)에 필요한 엔드포인트 + 기상 데이터 출처/한계
> 규칙: `CLAUDE.md` §3-7(FE 인계 문서 필수), §6(API 규칙)

## 0. 한 줄 요약

- 히트맵은 `GET /api/v1/farms/{farm_id}/monthly-outlook` 하나로 12칸을 다 받는다.
- **모든 응답의 `limitations` 배열을 화면에 반드시 병기**한다. 근사치를 확정 실측처럼 보여주면 안 된다(`CLAUDE.md` §18-4).
- 점수는 "문헌 기반 예상 적합도"다. **"AI 예측"·"정확도 검증 완료"로 표기 금지**(`docs/ml/backend_ml_handoff.md` §12).

## 1. 공통

- 인증: `Authorization: Bearer <access>` 필수. 계약은 `docs/auth-security.md`.
- 응답 래퍼: `{ "success": true, "data": {...}, "error": null }` (`app/schemas/common.py`).
- 남의 밭 조회 시 **404**(`FARM_NOT_FOUND`) — 존재 여부를 노출하지 않는다(§11).

## 2. `GET /api/v1/farms/{farm_id}/monthly-outlook`

장기 탭 히트맵. 올해 1~12월 적합도를 한 번에 준다. (연도 선택은 요구 생기면 쿼리파라미터로 추가)

```json
{
  "success": true,
  "data": {
    "farm_id": 1,
    "crop_id": 1,
    "region_id": 255,
    "year": 2026,
    "label": "문헌 기반 예상 적합도",
    "months": [
      {
        "month": 8,
        "growth_stage": "fruit_growth",
        "status": "ok",
        "score": 58.3,
        "grade": "C",
        "risk_flags": ["temp_day:outside_allowed", "temp_night_min:missing"]
      }
    ],
    "limitations": ["일 기온(temp_day)은 ...", "..."]
  },
  "error": null
}
```

`months`는 **항상 12개**, `month` 1~12 오름차순이다.

| 필드 | 값 | FE 처리 |
|---|---|---|
| `status` | `ok` | 점수 표시 |
| | `out_of_season` | "제철 아님"(예: 배 겨울 — 해당 단계 지침 자체가 없음). 회색 처리 |
| | `insufficient_data` | "데이터 부족". 회색 처리, 점수 칸 비움 |
| `score` | 0~100 또는 `null` | `null`이면 등급도 `null` |
| `grade` | `S`/`A`/`B`/`C` 또는 `null` | S≥90, A≥75, B≥60, C<60 |
| `growth_stage` | 코드 또는 `null` | 한글 라벨은 아래 §2.1 |
| `risk_flags` | `"<지표>:<사유>"` 배열 | 사유: `missing`/`invalid`/`invalid_guide`/`outside_allowed` |

**색만으로 등급을 구분하지 말고 라벨을 병기**한다(§8 접근성).

### 2.1 생육단계 코드 → 라벨

`dashboard_service.STAGE_LABELS`와 동일하게 쓴다.

| 코드 | 라벨 |
|---|---|
| `fruit_growth` | 결실비대기 |
| `coloring` | 착색기 |
| `maturity` | 성숙기 |
| `growing` | 생육기 |
| `early` | 초기 생육 |
| `tuber` | 괴경비대기 |
| `null` | `status=out_of_season`이면 "제철 아님", 그 외 "전기간" |

### 2.2 단계 판정 방식 (알아야 하는 근사)

각 월의 단계는 **그 달에 가장 많은 날을 차지한 단계**다. 대표일 1개(예: 매월 15일)로 판정하면
월 경계에 걸친 짧은 단계가 12칸 어디에도 안 나타난다(사과 성숙 DOY 294~314 → 10/15·11/15 양쪽
빗나감 → 수확 단계 소실). **한 달에 두 단계가 걸치면 짧은 쪽은 표기되지 않는다** — 이 한계는
`limitations`에 실려 온다.

## 3. `GET /api/v1/farms/{farm_id}/suitability`

특정 밭의 **오늘** 적합도. 히트맵과 달리 지표별 `breakdown`을 준다(칸 클릭 시 상세용).

`monthly-outlook`과 동일 필드 + `as_of`(날짜), `breakdown`(지표별 메타데이터).

### 3.1 `breakdown` 구조

각 지표별 상세 정보:

```json
{
  "temp_day": {
    "value": 25.3,
    "score": 85.2,
    "weight": 0.12,
    "status": "optimal"
  },
  "sunlight": {
    "value": 8.2,
    "score": 72.0,
    "weight": 0.15,
    "status": "allowed",
    "method": "angstrom_corrected",
    "is_calculated": true,
    "confidence": 0.82
  }
}
```

| 필드 | 의미 | 표시 규칙 |
|---|---|---|
| `value` | 해당 월의 지표값 | 그대로 표시 |
| `score` | 0~100 규범 점수 | 그대로 표시 |
| `weight` | 적합도 계산에서의 가중치 | (표시 불필요) |
| `status` | `optimal` / `allowed` / `risk` / `missing` / `invalid` | 색상/라벨 조정 |
| `method` | (일조시간만) `measurement` / `angstrom_only` / `angstrom_corrected` | 계산값이면 기록 |
| `is_calculated` | (일조시간만) `true`면 계산값, `false`면 실측 | 계산값이면 UI에 작은 텍스트로 안내 |
| `confidence` | (일조시간 계산값만) 신뢰도 0.0~1.0 | 계산값이면 "신뢰도: XX%"로 표시 |

**계산값 표시 규칙(일조시간):**
- `is_calculated === true` → "계산값(신뢰도: XX%)" 작은 텍스트로 표시
- `is_calculated === false` → 별도 표시 없음

## 4. `GET /api/v1/dashboard`

유저의 모든 밭 카드. `crop_name`/`region_name`/`crop_type`(`orchard`|`field`)/`growth_stage_label`/`score`/`grade`/`status`/`limitations`.

## 5. 기상 데이터 출처와 한계 ★FE 표기 의무★

장기 탭 점수의 기상 입력은 **평년치**다. 실시간 예보가 아니다.

| 신호 | 상태 | 비고 |
|---|---|---|
| 월평년 기온·강수 | ✅ 적재됨 | ⚠️ 기상청 공식 30년 평년값이 아니라 **관측 5년 평균 근사**(`source='obs_mean_2021_2025'`), 102지역 |
| 야간최저 평년 | ❌ 없음 | 소스 미발급 → `null` → 해당 지표는 `risk_flags`에 `missing`으로 뜬다 |
| 일조 평년 | ✅ 계산값 제공 | 실측 ASOS 데이터 우선, 없으면 Angstrom+동적보정 계산. **정확도 0.90 이상만 포함**. 계산값이면 `breakdown["sunlight"]["is_calculated"]=true` + confidence 표시 |
| 3개월 장기예보(tercile) | 🔶 적재는 가능해짐 | `weather_outlook`에 적재(§6). **점수 보정 적용은 아직 미구현** — 별도 PR |
| 단기예보(당일~3일) | ❌ 없음 | 단기 탭 미착수, API 키 미발급 |

즉 지금 히트맵은 "이 지역의 평년 기후 + 내 밭 토양 추정치"로 계산한 **이론 추정**이다.
`limitations`를 접어두지 말고 카드/탭에 보이게 두는 것이 요구사항이다.

### 5.1 일조시간 계산 방식 (신뢰도 기준)

일조시간은 정확도 0.90 이상인 경우만 적합도 계산에 포함된다. 미달 시는 자동으로 제외되고 FE는 다른 지표만으로 적합도를 판정한다.

| 방식 | 신뢰도 | 포함 여부 | 방법 |
|---|---|---|---|
| 실측 ASOS 평년 | 0.95 | ✅ 포함 | ASOS 105개 관측소 일조시간 실측 평년값 직접 사용 |
| Angstrom + 보정 | 0.76~0.87 | ✅ 포함 | 기온 기반 Angstrom 공식 + 구름/강수/습도 동적 보정 |
| Angstrom 기본 | 0.70 | ❌ 제외 | 기온만으로 Angstrom 공식 계산 (정확도 미달) |

**계산값 판정:**
- `method=measurement` → 실측값 (표시 불필요)
- `method=angstrom_*` → 계산값 (UI에 "계산값(신뢰도: XX%)" 작은 텍스트)

## 6. 장기예보 적재 파이프라인 (백엔드 운영 메모)

FE가 직접 쓸 건 없지만, 위 표의 "적재는 가능해짐"의 실체.

- 소스: 기상청 3개월전망 **RSS XML**
  `http://www.kma.go.kr/repositary/xml/fct/mon/img/fct_mon3rss_108_YYYYMMDD.xml`
  (`data.go.kr` 15050698은 PDF fileData라 기계판독 불가, API허브 예특보엔 장기예보 없음)
- 실행: `backend/.venv/Scripts/python.exe scripts/load_weather_outlook.py`
- **자동화 방식**: 위 명령을 스케줄러에 걸면 끝. 발표는 매월 23일 전후 1회이고
  `uq_outlook` 유니크로 upsert라 **매일 돌려도 멱등**이다. 별도 "업데이트 버튼"은 불필요하다.
- 실측으로 확인한 함정 2개(코드에 방어 있음):
  1. 발표일 이동 — 2026-05는 22일에 나왔고 23·24일 URL은 없었다 → 23일 기준 ±3일 탐색.
  2. 없는 날짜도 **HTTP 200 + HTML 에러페이지** 반환 → XML 파싱·루트태그까지 검증해야 한다.
- 권역 매핑: RSS는 13개 권역(전국+12) 단위 → `region_outlook_zone` 시드로 시/군 256개에 펼친다.
  **태백시는 영서/영동 공식 근거를 못 찾아 전국 권역으로 폴백**(`is_fallback=true`) — 이 지역
  밭은 UI에 "권역 미특정"을 병기할 근거가 된다.
- δ(보정 단위)는 상수가 아니라 `similar_low`/`similar_high`에서 유도한다. 비슷구간이 평년값
  기준 **비대칭**이라(실측: 평년 296.6mm, 구간 209.3~374.4) 반폭 하나로 뭉개지 않는다.

## 7. 아직 없는 것

- 히트맵 칸 클릭 → 그 월의 지표별 상세(현재 `breakdown`은 오늘 기준만)
- 시기별 커리큘럼 자연어 서술(LLM) — 정형 데이터는 준비됨, 연결 미착수
- 장기예보 보정을 반영한 점수(`DB.md` §8.1 대비 갭)
