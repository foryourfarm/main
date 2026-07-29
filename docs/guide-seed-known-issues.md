# 생육 지침 시드 알려진 문제 (2026-07-29)

> `crop_growth_guide` 시드에서 발견된 채점 정확성 문제 목록. PR #52(risk_width 도입) 로컬 검증 중
> 발견했다. 수정 완료분과 미해결분을 함께 남긴다 — 미해결분은 담당자 배정이 필요하다.

## 배경: 채점 곡선이 어떻게 생겼나

`suitability_service._indicator_score`는 지표값을 4구간으로 나눈다.

```
      100 ┤━━━━━━━━━━━━            최적구간 (optimal_min ~ optimal_max)
       95 ┤            ╲           최적 이탈 즉시 -5 고정감점
          │             ╲___
       60 ┤                 ╲      허용경계 (allowed_min/max)
          │                  ╲
          │                   ╲___
        0 ┤                       ━━━━  허용경계 + risk_width 밖
          └────────────────────────────
           최적      허용      위험
```

- 허용구간 감쇠 척도 = **완충폭**(optimal 경계 ~ allowed 경계 거리)
- 위험구간 감쇠 척도 = **`risk_width`**(전국 실측 산포도, PR #52 / 마이그레이션 0020)

문제는 대부분 **`allowed_min`/`allowed_max`가 NULL이면 이 곡선이 통째로 무너진다**는 데서 나온다.
NULL이면 `_indicator_score`가 `risk_width`를 읽기 **전에** 0점을 반환한다
(`backend/app/services/suitability_service.py:124-132`).

```python
if value < lo:
    if guide.allowed_min is None:
        return 0.0, "risk"          # ← 여기서 끝. risk_width 안 봄
    ...
if guide.allowed_max is None:
    return 0.0, "risk"              # ← 여기서 끝. risk_width 안 봄
```

PR #52 이전엔 이게 맞았다 — 감쇠 척도가 완충폭이라 `allowed`가 없으면 척도 자체가 없었다.
PR #52가 `risk_width`(완충폭과 무관한 절대폭)를 도입하면서 척도는 생겼는데, 코드 경로는 옛
전제 그대로라 도달하지 못한다.

---

## 수정 완료 (마이그레이션 0021, 브랜치 `fix/apple-guide-allowed-bounds`)

### F-1. 사과 허용경계 5행 누락

원인은 코드가 아니라 시드다. 0004 시드(농사로 안내책자)는 optimal만 주는 출처였고, 다른 작물은
이후 0012/0015/0019에서 허용경계가 채워졌는데 **사과의 0004 행들만 한 번도 손을 안 탔다.**

| stage | indicator | 기존 allowed | → 수정 | 산출 |
|---|---|---|---|---|
| fruit_growth | temp_day | NULL / 31 | **15** / 31 | 18 − 6×0.5 (상한 31은 문헌값, 보존) |
| maturity | temp_day | NULL / NULL | **17.5 / 27.5** | 20∓2.5, 25±2.5 |
| coloring | temp_day | NULL / NULL | **11.5 / 13.5** | 12∓0.5, 13±0.5 |
| — | organic | NULL / NULL | **15 / 35** | 20∓5, 30±5 |
| — | p2o5 | NULL / NULL | **175 / 675** | 300∓125, 550±125 |

**산출식은 새로 만들지 않았다.** 0019가 문헌이 침묵하는 경계에 이미 쓴 휴리스틱
`allowed = optimal 경계 ± (optimal_max − optimal_min) × 0.5`을 그대로 적용했다.
실제 값으로 역산 확인: 오이 pH 7.45 = 6.8 + 1.3×0.5, 감자 유기물 55.5 = 47 + 17×0.5,
상추 유효인산 175/475 = 250−75 / 400+75. 세 사례 모두 일치.

추정치임을 각 행 `source_ref`에 명시했다(CLAUDE.md §18-4).

실측 채점 변화 (실 DB, 0021 전/후):

| 케이스 | 전 | 후 |
|---|---|---|
| 착과~비대기 16℃ | 0.00 | **81.07** (허용) |
| 착과~비대기 14℃ | 0.00 | **17.98** (위험) |
| 성숙기 26℃ | 0.00 | **88.22** (허용) |
| 유기물 16 g/kg | 0.00 | **75.65** (허용) |
| 유효인산 200 mg/kg | 0.00 | **75.65** (허용) |

최적구간 점수(100)는 전부 불변 — 회귀 없음.

### F-2. 사과 착색기 `temp_night_min` (8, 8) 행 삭제

`optimal_min = optimal_max = 8`이라 **폭이 0인 점 값**이었다. 야간최저기온이 정확히 8.00℃일
때만 100점, 그 외 전부 0점. 평년치가 소수점까지 8.00으로 떨어질 일이 없어 사실상 상시 0점이고,
착색기 가중치의 약 18%(장기 탭 기준 1.0/5.5)를 근거 없이 깎아왔다.

폭이 0이라 F-1의 휴리스틱도 적용 불가(±0)이고, `risk_width`도 산포도를 낼 수 없어 NULL이다.
0004가 인용한 `crop-domain-knowledge.md`가 현재 리포에 없고 `outcomes/memory/crop_rules/apple.json`
에도 야간기온 항목이 없어 원 문헌 확인이 불가능하다.

**값을 추측으로 고치는 대신 채점에서 제외했다.** 집계는 값 없는 지표를 `weight_sum`에서 빼므로
나머지 지표로 정상 채점된다. **문헌 확보 시 구간으로 복원 필요 — 담당자 필요.**

---

## 미해결 — 담당자 필요

### P1. 사과 착색기 `temp_day` optimal(12~13℃)이 실제 착색기 기온대와 안 맞음

F-1로 절벽은 없앴지만 **이 행은 여전히 전국 대부분에서 0~9점**이다. 값 자체가 문제로 보인다.

착색기는 `crop_growth_stage`상 day_of_year 233~293 = **8/21 ~ 10/20**이다. 그 기간 평년 기온
(`weather_climatology`, 116개 지역 실측):

| 월 | 평균 | 최저 | 최고 |
|---|---|---|---|
| 8월 | 26.1℃ | 21.0 | 27.8 |
| 9월 | 22.2℃ | 16.5 | 24.8 |
| 10월 | 14.7℃ | 9.6 | 18.4 |

optimal 12~13℃는 **어느 달에도 맞지 않는다.** 10월 최저 기온대 지역만 근접한다.

F-2의 `temp_night_min` (8,8)과 같은 계열의 **시드 매핑 오류로 의심**된다 — "착색에 필요한
야간 저온" 또는 "주야간 온도차" 문헌을 `temp_day`(주간 평균기온) 지표에 잘못 넣은 것으로 보인다.
사과 착색 생리 문헌 재확인이 필요하다. **추측으로 고치지 않았다(CLAUDE.md §3-4).**

### P2. 감자 `tuber` 단계 하한 2행 — 사과와 같은 원인

| crop | stage | indicator | optimal | allowed | risk_width | 증상 |
|---|---|---|---|---|---|---|
| 감자 | tuber | temp_day | 23~24 | **NULL** / 27 | 2.2408 | 23℃ 미만 즉시 0점 |
| 감자 | tuber | temp_night_min | 10~14 | **NULL** / 28 | (없음) | 10℃ 미만 즉시 0점 |

`temp_day`는 F-1과 동일한 휴리스틱(23 − 1×0.5 = 22.5)으로 즉시 해결 가능하다.
`temp_night_min`은 `risk_width`가 없어 완충폭 폴백으로만 동작한다.

이번 PR 범위를 "사과"로 한정해 넣지 않았다. 별도 PR 권장.

### P3. `risk_width`가 no-op인 지표들

마이그레이션 0020의 `RISK_WIDTH` 딕셔너리에는 `k`, `ca`, `mg`가 있지만
**`crop_growth_guide`에 해당 indicator 행이 아예 없어 UPDATE 3건이 no-op**이었다.

PR #52 본문의 "상추 Ca/K/Mg 0점 개선(56→6, 50→4, 41→0)"은 `outcomes/` ML 파이프라인 한정
수치이고 **백엔드 채점에는 반영되지 않는다.** 오해 소지가 있어 명시한다.

근본 원인은 0019에 이미 기록돼 있다: `soil_state` 테이블에 k/ca/mg 컬럼이 없고
`INDICATOR_SOURCE_FIELDS`에도 안 걸려 있다. 흙토람 클라이언트(`soil_exam_client.py`)는 이미
파싱 중이라 값은 들어온다 — **스키마 + 매핑 작업만 하면 된다.**

### P4. `temp_night_min` / `rainfall_daily`의 `risk_width`가 NULL

지역간 실측 산포도를 낼 수 없어 0020이 NULL로 뒀다(의도된 것, 숨기지 않음). 해당 지표는
종전 완충폭 폴백으로 동작한다. 감수 곡선 문헌 확보 시 개선 대상.

`rainfall_daily`의 `allowed_min` NULL 5건은 **고칠 필요 없다** — `optimal_min=0`이고 강수량은
음수가 안 나와 하한 분기가 발동하지 않는다(0012에 명시된 의도).

### P5. `crop-domain-knowledge.md` 리포에서 유실

마이그레이션 0004가 시드 전체의 근거로 인용한 문서인데 현재 리포에 없다.
0004에서 온 값(사과 4행, 감자 `tuber`/`early`, 배·오이·상추 일부)의 출처 추적이 불가능하다.
누가 가지고 있는지 확인 필요 — 없으면 P1/F-2 같은 문제를 계속 문헌 없이 판단해야 한다.

---

## 환경 이슈

`outcomes/scripts/ml/test_imputation.py`(PR #52 신규, 200줄)와 `test_crop_literature_anchor.py`는
**로컬에서 실행하지 못했다.** `backend/.venv`와 시스템 Python(3.14) 어디에도 numpy/pandas가 없다.
ML 산출물 검증이 필요한 사람은 별도 venv 준비가 필요하다. 백엔드 런타임 의존성은 아니다.

---

## 검증 기록 (0021)

| 항목 | 결과 |
|---|---|
| `alembic upgrade head` (0020→0021) | 통과 |
| 적용 후 사과 7행 상태 확인 | 5행 경계 채워짐, `temp_night_min` 삭제, pH/rainfall_daily 불변 |
| `alembic downgrade -1` | 통과 — 경계 NULL 복원, 삭제 행 재삽입, `source_ref` 접미사 제거, 문헌값 31 보존 |
| 재 `upgrade head` | 통과 |
| 백엔드 pytest | 237 passed + 2117 subtests |
| 전/후 채점 비교 (실 DB) | 최적구간 불변, 경계 밖만 개선 (위 표) |
