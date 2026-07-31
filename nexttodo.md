# 다음 할 일

> 갱신: 2026-07-31. **남은 일의 단일 목록이다** — 흩어져 있던 시점 보고서
> (`Bug_Report` `FinalReport` `MappingReport` `CI_report` `MIGRATION-GUIDE`)는
> `docs/reports/`로 옮기고 그 안의 미해결 항목만 여기로 접었다.
> "완료"는 실제로 `dev`에 머지된 것만.

---

## 🔴 지금 열려 있는 것

### PR #57 (`feat/climatology-knn` → `dev`) — 리뷰 대기

커밋 4개. CI backend/frontend 통과.

| # | 내용 | 상태 |
|---|---|---|
| 1 | 평년치 대체 KNN(k=10) — 정규화 MAE +10.99%, 예측불가 189→0건 | 코드·검증 완료 |
| 2 | 단기 예보 캐시 발표시각 기준 — 7.2s → 0.02s | 완료 |
| 3 | 채점 커버리지 한계 표기 + 일 강수량 장기 채점 제외 | 완료 |
| 4 | 읍·면 토양을 리 코드로 조회 (농촌 전역 결측 해소) | 완료 |
| 5 | 밭 등록 시/군 datalist 검색 | 완료 |

**머지 전 남은 것**: 화면에서 한계 문구·점수 눈으로 확인(§18-4는 API가 아니라 화면 기준).

### 결정 대기 — 밭 주소를 리 단위까지 받을 것인가

흙토람이 읍·면 데이터를 리 코드로만 갖고 있다는 걸 알게 되면서 나온 질문.
**면 평균 vs 리 실측의 점수 차를 실측했다**(밭 경지구분 기준):

| 면 | 리 수 | 면 평균 점수 | 평균 \|차이\| | 최대 차 | 등급 바뀐 리 |
|---|---|---|---|---|---|
| 부여 장암면 (상추) | 6 | 100 S | **34.7점** | **60.0점** | **4/6** |
| 고창 고수면 (감자) | 14 | 82.1 A | 7.5점 | 43.1점 | 3/14 |
| 고창 공음면 (오이) | 10 | 100 S | 2.6점 | 11.3점 | 1/10 |

장암면은 면 평균이 100점 S인데 리 3곳은 **40점 C**다. "내 땅"이라 믿고 보는 값이
정반대 신호를 준다 — PRD 철학 1("이론치와 실제의 괴리를 좁히는 게 핵심 경쟁력") 정면 위반.

- **찬성 근거**: 정확도 외에 호출도 준다(리 5회 13.6s → 1회 3s). 리 목록은
  `docs/seed/bjd_to_region.csv`에 15,209개가 이미 있다. 스키마 변경 불필요 —
  `user_farm.bjd_code`가 법정동코드 10자리라 리 코드를 그대로 담는다.
- **필요한 일**: `district` 테이블에 리 5,066→약 20,000행 적재, 등록 폼에 리 단계
  추가(동 지역은 리가 없어 조건부 노출), 기존 읍면동 밭은 지금의 리-풀 폴백 유지.
- **미착수** — 착수 전 확인 필요.

### 기존 밭 토양 복구 (미적용)

리 코드 버그로 NULL이 박힌 밭이 있다. `scripts/repair_empty_soil_state.py --apply`.
위 리 단위 결정에 따라 채울 값이 달라지므로 **결정 후 실행**한다.

```
farm 10 (고수면, 감자)  ph=6.47 ec=1.33 p2o5=496.21 om=17.1   표본 121건
farm 11 (공음면, 오이)  ph=6.02 ec=5.02 p2o5=502.15 om=16.2   표본  66건
farm 12 (고창읍, 상추)  ph=5.63 ec=0.70 p2o5=127.90 om=30.57  표본  70건
farm 7  (부천 원미구)   여전히 0건 — 도시 동, 흙토람에 실제로 표본 없음
farm 6, 8, 9            bjd_code=None (구버전 등록) — 조회 자체가 불가
```

공음면 시설 EC 5.02는 값 검증이 필요하다. 시설재배 염류집적으로 높게 나오는 게
정상이긴 하나 오이 허용범위를 크게 넘어 점수가 급락한다 — 맞는 값이면 그게 정직한 결과다.

조사 도구: `scripts/trace_soil.py <farm_id>` (읽기 전용, 6단계 전 구간 추적).

---

## 🟠 인프라 · 프로세스

`docs/reports/CI_report.md` §8에서 옮김. CI 자체는 도입 완료(PR #56).

1. **`dev` 브랜치 보호 규칙** — CI가 있어도 빨간불 PR을 머지할 수 있다.
   Settings → Branches → "Require status checks to pass". **저장소 admin 필요.**
2. **HTTP 엔드포인트 테스트 0건** — TestClient 기반 테스트가 하나도 없다.
   서비스 계층 회귀는 CI가 잡지만 **배선 회귀는 아무도 못 잡는다.**
3. **의존성 버전 고정** — `requirements.txt`가 전부 `>=`라 상류 릴리스로 갑자기 깨질 수 있다.
4. **마이그레이션 검증 Job** — `services:`로 Postgres 띄워 `upgrade`/`downgrade` 왕복.
5. **ruff 린트** — `CLAUDE.md §4`가 권장하는데 로컬 venv에 설치조차 안 돼 있다.
6. **3개월전망 자동 갱신 스케줄러 부재** — `scripts/load_weather_outlook.py`는 멱등하게
   짜여 있는데 정작 스케줄러가 없다(cron·APScheduler·Actions 전부 부재). 매월 23일 전후
   발표 때마다 사람이 수동 실행해야 하고, 안 돌리면 **에러 없이 조용히** 낡은 예보로 남는다.

---

## 🟡 데이터 적재 — 비어 있는 것

`docs/reports/Bug_Report.md` §8에서 옮김.

- **일사량 평년값 ETL 없음** (`0016`에 컬럼만 있음). 없으면 일조 지표가 계속 빈다.
  `scripts/calibrate_sunlight.py`가 이미 전국 일별을 받아오므로 (지역, 월) 평균만 내면 된다.
- **`temp_night_min_normal`·`sunlight_normal` 전 행 NULL** — 채워지면 KNN 이득이 두 필드로도 확장된다.
- **관측지점 510개 시드 미적재** (`0015`). `getAwsStnLstTbl`이 `stn_id`/`lat`/`lon`/`ht`를 준다.
- **`VWORLD_API` 키 없음** (주소 → PNU 변환용). 나머지 6개 키는 로드 확인됨.
- **기상청 30년 평년값 API** — 전국 256개 완전 커버의 근본 해결. 팀원이 키 보유, 추후 PR로 받음.
  지금의 KNN 대체는 그때까지의 완화책이다.

### 주의 (되돌리지 말 것)

- 명세서 오타 2건: ① 유효인산 논 5구간 "251~250이하"는 실제 201~250 ② 헤더 태그 케이스가
  API별로 다름. 둘 다 코드 주석에 근거를 남겼다.
- API 쿼터 — `getWeatherYearMonList3`에서 429를 만난 적 있다. 지점별 반복 호출 금물(§18-1).

---

## ⏭️ 기능 — 미착수

**생육 기준** (PR #47에서 보류)
- 감자 온도기준 모드 불일치: 문헌은 달력월(3~6월), `crop_growth_stage`는 파종후경과일. `[확인 필요]`
- 상추 K/Ca/Mg: `soil_state`에 컬럼이 없어 보류. 흙토람 클라이언트는 이미 파싱 중이라
  스키마 컬럼 + 스코어링 매핑만 남음.
- 지침 지표가 전반적으로 얇다 — 오이·배 2개, 감자 3개. 채점 커버리지 문구로 정직하게
  노출은 되지만, 지표를 늘리는 게 근본이다.

**LLM** (다음 순서)
- 오늘의 추천 행동 — 단기 탭 위험신호를 자연어로. `daily_recommendation` 테이블 설계는 있음
- 장기 커리큘럼 서술, 대시보드 카드 한 줄 설명

**메인 로직 — 블로킹된 것**
- P0 exporter: `scripts/ml/final_model.py` + `data/ml/training_rows.csv`가 리포에 없음
- P1 노출 게이트: 라이브 실측(예측↔재검정 쌍) 데이터 자체가 없음
- P3 first-party 수집: `crop_outcome_record`·`farm_action_log` 성분 보강 — 그릇은 만들 수 있음

**장기 탭을 "앞으로 3개월"로 제한** (2026-07-27 논의, 진행 안 함)
지금은 올해 1~12월 전체를 계산한다. 신뢰할 수 있는 신호는 3개월전망뿐이라 이 범위로
좁히는 게 §12 원칙과 맞다. 착수 전 방식부터 정할 것:
- 정공법: `build_monthly_rows`가 (연도,월) 윈도우를 받게 + `load_corrections` 다년도 대응
  + `MonthlyOutlookEntry`에 `year` 추가. `test_monthly_outlook.py` 9개가 "12개월·단일연도"
  전제라 같이 손봐야 함.
- 싼 대안: 12개월 계산은 두고 응답만 3개 슬라이스. 11·12월 시작 시 내년 1~2월이 빠진다
  (연중 2달 구멍, `ponytail:` 남기고 넘어가는 것도 선택지).

**FE 남은 것**
- 대시보드/밭상세 데이터 신뢰도 배지(출처 N/3)
- 카드에 LLM 한 줄 설명 (LLM 착수 후)

**배포** — GCP(Cloud Run + Cloud SQL + 로컬 LLM은 GPU VM). 별도 논의.

---

## ✅ 완료 (dev 머지)

- **인증**: 분리 토큰 JWT + FE 연동. `docs/auth-security.md`
- **챗봇**: RAG(pgvector) + 밭 컨텍스트 + 대화 영속화 + 프롬프트 인젝션 방어.
  화면 흔들림 수정(#42), 작물 자동인식(#43). `docs/llm-integration.md`
- **장기 탭**: 월별 히트맵 API+FE(#27), 3개월전망 적재(#28), 보정 적용(#29), 화면(#30)
- **단기 탭**: 예보 조회·캐시·지속위험 판정 API+화면(#33). 강수 단위 버그(0011~0013)도 같은 PR
- **밭 온보딩**: 시/군→읍면동 API + 화면, 경지구분 필터, 행정통합 코드 대응표(#32)
- **설정 화면**: `GET/PATCH/DELETE /api/v1/farms` + `/settings` + 출처 footer(#39).
  `docs/farm-settings-api.md`. 마이그레이션 `0014`(`user_farm.bjd_code`)
- **밭 상세 모달 진입**(#41) — intercepting route로 절충. `/farm/[farmId]` 라우트는 유지
- **위경도→격자 변환**: `kma_grid.py` + `region_grid` 256개 실제 격자 시드
- **기상 평년치 커버리지**: 102→116개 실측 확장 + 나머지 140개 격자 대체(`041291e`)
- **배 생육기 ARCCAS 확장**: 4~10월로 확대, 4월 오판정 수정(#40). 사과는 성격이 달라 미반영 `[확인 필요]`
- **생육 기준 문헌 갱신**: 오이·상추·감자(#47, `0019`)
- **CI**: GitHub Actions 백엔드 테스트 + 프론트 빌드(#56)
- **P0/P2/대시보드/region 시드**: #26으로 dev 회수(stacked PR 사고 해소)

---

## 참고

- **아카이브**: `docs/reports/` — 시점 보고서 5건. 미해결 항목은 전부 위로 옮겼으니
  이 폴더는 "그때 왜 그렇게 판단했나"를 되짚을 때만 본다.
- **명세**: `CLAUDE.md`(개발 헌법), `PRD.md`(원래 의도), `PRD2.md`(코드 기준 역기획), `DB.md`
- **FE 인계**: `docs/auth-security.md`, `docs/farm-settings-api.md`, `docs/long-term-tab-api.md`,
  `docs/llm-integration.md`, `docs/main-logic-guide.md`
- **설계 기준**: `docs/design/Correction_Re_Draft.md`
- **ML**: `docs/ml/climatology-knn-plan.md`, `docs/ml/backend_ml_handoff.md`
- **메모리**: `region-vs-district-data-units`(이번 리 발견으로 갱신 필요),
  `weather-climatology-coverage-status`, `user-verifies-backend`, `frontend-stack-nextjs`
