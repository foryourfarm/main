# 밭 설정 API 계약 (FE 인계)

> 대상: 프론트엔드 개발자 · 기준일 2026-07-26
> 범위: 설정 화면(밭 목록 조회·수정·삭제) + 데이터 출처 footer
> 규칙: `CLAUDE.md` §3-7(FE 인계 문서 필수), §6(API 규칙), §11(소유권)

## 0. 한 줄 요약

- 밭 목록 `GET /api/v1/farms`, 수정 `PATCH /api/v1/farms/{farm_id}`, 삭제 `DELETE /api/v1/farms/{farm_id}`.
- **시/군을 바꿀 때는 `bjd_code`(읍/면/동)도 같이 보낸다.** 안 보내면 400 — 옛 읍면동은 새 시/군에 속하지 않는다.
- 위치나 작물이 바뀌면 서버가 **토양 기준값을 새로 조회**한다(밭의 토양 숫자가 바뀜). 사용자에게 미리 알린다.
- 삭제는 CASCADE — 토양 상태·행위 기록·추천이 함께 사라지고 되돌릴 수 없다. 확인창 필수.

## 1. 공통

- 인증: `Authorization: Bearer <access>` 필수(`lib/auth.ts`의 `authFetch` 사용).
- 응답 래퍼: `{ "success": true, "data": ..., "error": null }`.
- 남의 밭이면 **404 `FARM_NOT_FOUND`** — 존재 여부를 노출하지 않는다(§11).

## 2. `GET /api/v1/farms` — 밭 목록

`data`는 밭 객체 배열. 대시보드(`GET /dashboard`)와 달리 **적합도 계산을 하지 않는다**(등록 정보만, 빠름).

```json
{
  "id": 12,
  "region_id": 46150,
  "region_name": "순천시",
  "bjd_code": "4615012300",
  "district_name": "삼거동",
  "crop_id": 1,
  "crop_name": "사과",
  "planting_date": "2026-03-01",
  "label": "집 앞 사과밭",
  "soil_source": "흙토람 토양검정(읍면동 4615012300, 경지구분 4), 표본 100건"
}
```

- `bjd_code`/`district_name`이 **null일 수 있다** — 0014 마이그레이션 이전에 등록된 밭. FE는 "읍/면/동을 다시 선택하면 토양 데이터가 정확해집니다"를 노출하고, 수정 시 반드시 읍면동을 받아야 한다.
- `soil_source`는 조회 단위·표본수가 들어간 문구다. 그대로 보여주면 "내 밭 실측이 아니다"가 전달된다(§18-4).

## 3. `PATCH /api/v1/farms/{farm_id}` — 수정

**보낸 필드만 바뀐다.** 응답은 §2와 같은 밭 객체(수정 후 값).

```json
{ "region_id": 52790, "bjd_code": "5279025000", "crop_id": 4, "planting_date": "2026-04-05", "label": "뒷밭" }
```

| 상황 | 코드 | 의미 / FE 처리 |
|---|---|---|
| 시/군만 보냄(읍면동 불일치) | 400 `DISTRICT_REGION_MISMATCH` | 시/군 변경 시 읍면동 선택을 강제한다 |
| 읍면동이 null인 밭을 수정 | 400 `BJD_CODE_REQUIRED` | 읍면동 select를 필수로 |
| 없는 지역/읍면동/작물 | 404 `REGION_NOT_FOUND` / `DISTRICT_NOT_FOUND` / `CROP_NOT_FOUND` | 선택지는 마스터 API에서만 받는다 |
| 수정 불가 필드 전송 | 400 `FIELD_NOT_EDITABLE` | `region_id, bjd_code, crop_id, planting_date, label`만 허용 |

- `label`은 명시적 `null`로 지운다(안 보내면 유지).
- **토양 기준값 재조회 조건**: 읍면동이 바뀌거나, 작물의 경지구분(논/밭/시설/과수)이 바뀔 때. 사과→배처럼 같은 과수끼리면 재조회하지 않는다(같은 표본 → 같은 값).
- 유저 실측 이력(`soil_state_snapshot`)과 행위 기록(`farm_action_log`)은 **지우지 않는다** — 유저가 실제로 한 일이라서. 다만 그 이력은 이전 위치 기준이라는 한계가 남는다([확인 필요] P1 재검정에서 다룸).

## 4. `DELETE /api/v1/farms/{farm_id}` — 삭제

`data`는 `"deleted"` 문자열. 딸린 `soil_state`·`soil_state_snapshot`·`farm_action_log`·`daily_recommendation`·`prediction_shadow`가 FK CASCADE로 함께 삭제된다. 되돌릴 수 없으므로 FE에서 확인을 받는다.

## 5. FE 구현 현황

- `app/settings/page.tsx` — 밭 목록 + 수정/삭제 + 출처 footer. 네비게이션은 대시보드 | 상담 | 설정(설계 §1.2).
- `components/FarmForm.tsx` — 등록(온보딩)/수정 공용 폼. `farm` prop을 주면 수정 모드.
- 출처 footer 문구는 `SOURCES` 상수(설정 페이지). 기상=기상청, 토양=흙토람, 작물기준=농사로·문헌.

## 6. 아직 없는 것

- 밭 이름만 빠르게 바꾸는 인라인 편집(YAGNI — 수정 폼으로 충분).
- 삭제 취소(undo)·휴지통. 확인창으로 갈음.
