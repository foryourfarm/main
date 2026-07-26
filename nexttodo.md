# 다음 할 일

> 갱신: 2026-07-26. "✅ 완료 (dev 머지)"는 실제로 dev에 머지된 것만.
> 상세 방향은 메모리/`docs/` 참고.

## 🔴 FE에서 실제로 화면 켜보고 발견한 문제 (최우선)

**계기**: 고창군 사과밭 장기 탭이 12개월 전부 "데이터 부족"으로 나옴 — 화면이 미연동처럼 보임.

1. **평년치 커버리지 부족(진짜 원인)** — `weather_climatology`가 256개 시/군 중 102개만 있었음.
   원인: ML용 `03_weather_monthly_modified.csv`가 218개 농업기상 관측지점 중 **150개만**
   선정해 만든 것(Data-Guideline.md 층화표집 다양성 기준 — 전국 커버가 목적이 아니었음).
   - **1차 조치(완료)**: `scripts/expand_weather_coverage.py` — 선정에서 빠진 68개 미사용
     관측지점을 추가 매칭해 실제 API로 5년치 수신 → **102→116개 지역**(+14, 실측 데이터,
     추정 아님). `data/03_weather_monthly_modified.csv`에 840행 append.
   - **2차 조치(완료)**: `climatology_service.py` — 그래도 안 채워지는 지역(140개, 예:
     부천시 원미구·고창군)은 `region_grid` 격자거리로 **최근접 보유 지역 값을 대체**하고
     "OO시 값을 약 N km 대체로 썼다"를 limitations에 명시(§18-4, 근사를 확정값처럼 안 쓰기).
     실측 검증: 부천 원미구→시흥시(10km) 대체, 고창군→장성군(16km) 대체, 순천시는 실측
     그대로(대체 없음). 테스트 6개(거리계산·문구생성) 통과, 전체 151개 회귀 없음.
   - **근본 해결**: 기상청 공식 30년 평년값 API 발급 → 전국 256개 완전 커버. 팀원이 API
     보유 중, 추후 PR로 받을 예정(우리 쪽 작업 아님). 지금 두 조치는 그 전까지의 완화책.
   - **커밋 확인(완료, 2026-07-26)**: `data/03_weather_monthly_modified.csv` 840행 append분,
     커밋 `041291e feat(weather): 평년치 커버리지 확장 + 인접지역 격자 대체`에 이미 반영됨.
     gitignore 대상 아님, tracked, working tree clean — 별도 조치 불필요.

2. **강수 지표 단위 혼동 버그 (이미 수정·커밋됨, PR #33)** — `rainfall` 하나에 월평년(mm/월)과
   예보 일누적(mm/일)을 섞어써서 "비 안 온 날(0mm)이 위험"으로 오판정되던 것.
   `rainfall_monthly`/`rainfall_daily`로 분리, 감자의 근거 없는 월강수 기준(시즌 총량을
   12로 나눈 값)도 제거(0011~0013). 상세는 PR #33 본문.

## 🟡 FE 설정·네비게이션이 설계 문서와 크게 어긋남

`docs/design/Correction_Re_Draft.md`(팀 확정 UI 설계) 대비 지금 화면 격차:

| 설계 | 지금 상태 |
|---|---|
| 네비게이션: 대시보드\|상담\|설정 (간결) | 일치(설정 추가 완료) |
| 장기/단기 = **카드 클릭 → 모달** | **절충 완료(PR #41)**: 장기/단기 탭은 그대로 유지, 대시보드→밭 상세 "진입"만 모달로. Next.js intercepting route(`/farm/[farmId]` 라우트는 유지, 대시보드에서 클릭 시에만 인터셉트) |
| **설정 탭**: 지역/작물 재설정 + 데이터 출처 footer | dev 머지 완료(`/settings`, PR #39) — 아래 "완료" 참고 |
| 카드에 LLM 한 줄 설명 | 없음(LLM 미착수라 당연 — 후순위 항목) |
| 팔레트: Primary #2D5016 등 (Design01) | `farm.module.css`가 이미 이 팔레트 사용 중 — 이 부분은 일치 |

**결정됨(2026-07-26)**: 라우트를 없애는 큰 구조 변경 대신 intercepting route로 절충 —
`/farm/[farmId]`는 그대로 두고 대시보드발 진입만 모달로 가로챈다. 설정 화면(지역/작물
변경, 밭 삭제)은 이미 dev 머지 완료.

## ⏭️ 미착수 / 다음

**메인 로직 백엔드 — 블로킹된 것**
- P0 exporter: `scripts/ml/final_model.py` + `data/ml/training_rows.csv`가 리포에 없어 진짜 artifact 생성 불가
- P1 노출 게이트: 라이브 실측(예측↔재검정 쌍) 데이터 자체가 없음
- P3 first-party 수집: `crop_outcome_record`·`farm_action_log` 성분 보강 — 그릇은 만들 수 있음, 미착수

**LLM (다음 순서로 정함)**
- 오늘의 추천 행동 — 단기 탭 위험신호를 자연어로. `daily_recommendation` 테이블 설계는 있음
- 장기 커리큘럼 서술, 대시보드 카드 한 줄 설명

**기상 데이터 — 남은 확장**
- 3개월전망(outlook) tercile 적재는 완료(PR #28~29). 기상청 공식 30년 평년값 발급이 남은
  근본 과제(위 "커버리지 부족" 참고)
- 단기 탭 API 자체는 완료(PR #33) — 남은 건 위 커버리지·LLM 뿐
- **3개월전망 자동 갱신 스케줄러 미착수(2026-07-26 확인)**: `scripts/load_weather_outlook.py`는
  멱등하게 짜여 "스케줄러가 매일 돌아도 무해"하다고 스크립트 자체 docstring에 설계돼 있는데,
  정작 그 스케줄러가 코드베이스에 없음(cron·APScheduler·GitHub Actions 전부 부재 확인).
  지금은 매월 23일 전후 발표 때마다 사람이 수동으로 스크립트를 돌려야 함 — 안 돌리면 조용히
  낡은 예보로 남는다(에러 없이 그냥 갱신 안 됨). CLAUDE.md §19 미결정 "기상 캐시 갱신 주기"와
  같은 갭. 백엔드에 스케줄러(APScheduler 등, `app/infra/scheduler` 예정 자리) 붙이는 작업 필요.

**FE 남은 것**
- 대시보드/밭상세 데이터 신뢰도 배지(출처 N/3)
- ~~챗봇 로그인 모드 연결~~: 구현됨(미커밋, 사람 검증 대기) — `lib/chat.ts`가 Bearer access +
  `session_id`(마운트당 uuid4) + `farm_id`(`/chat?farmId=`) 전달. `/farm/[farmId]`에 "이 밭으로
  상담하기" 링크. access 30분 만료를 스트리밍이 못 잡으므로 `ensureAccessToken()`으로 선제 refresh.
  안 만든 것: 지난 대화 불러오기(조회 API 없음 → 리로드=새 스레드), 밭 선택 드롭다운(밭 1개면 백엔드 자동)

**배포** — GCP(프론트/백엔드 Cloud Run + Cloud SQL + 로컬 LLM은 GPU VM). 별도 논의 예정.

## ✅ 완료 (dev 머지 또는 PR 상신)

- **인증**: 분리 토큰 JWT + FE 연동. `docs/auth-security.md`.
- **챗봇**: RAG(pgvector)+밭 컨텍스트+대화 영속화+프롬프트 인젝션 방어. `docs/llm-integration.md`.
- **P0/P2/대시보드/region 시드**: PR #26으로 dev 회수 완료(stacked PR 사고 해소).
- **장기 탭**: 월별 히트맵 API+FE(PR #27), 3개월전망 적재(PR #28), 보정 적용(PR #29), 대시보드+히트맵 화면(PR #30).
- **밭 온보딩**: 시/군→읍면동 API + 화면, 경지구분 필터, 행정통합 코드 대응표(PR #32). 명세는 PR #31.
- **단기 탭**: 예보 조회·캐시·지속위험 판정 API+화면(PR #33). 강수 단위 버그·생육지침 근거/신뢰도 컬럼도 같은 PR.
- **위경도→격자 변환**: `kma_grid.py`(공개 기준점 8개 검증) + `region_grid` 256개 실제 격자 시드.
- **설정 화면**: `GET/PATCH/DELETE /api/v1/farms` + `/settings` 화면 + 출처 footer(PR #39). 계약은
  `docs/farm-settings-api.md`. 마이그레이션 `0014`(`user_farm.bjd_code` 추가, backfill 가능한 것만 채움).
  위치·작물 변경 시 읍면동/경지구분이 바뀔 때만 `soil_state` 재초기화, 실측 이력·행위 기록은 보존.
- **기상 평년치 커버리지 확장**: 102→116개 실측 확장 + 나머지 140개 격자 최근접 대체(PR, `041291e`).
  근본 해결(기상청 30년 평년값 API)은 팀원 보유, 추후 PR로 받을 예정.
- **배 생육기 ARCCAS 확장**: 4~10월로 범위 확대, 4월 적합도 오판정 수정(PR #40). 사과는 기존
  단계별 세분값과 성격 달라 이번엔 미반영(`[확인 필요]`, 팀 확인 후 별도 PR).
- **밭 상세 모달 진입** (PR #41): 위 "카드 클릭 → 모달" 결정 참고.
- **챗봇 화면 흔들림 수정** (PR #42): `.page`가 `height:100dvh`라 전역 헤더 높이를 무시해 입력창이
  화면 밖으로 밀리고, 스트리밍 중 문서가 뷰포트보다 커져 브라우저 스크롤바가 생겼다 없어지며
  폭이 ±15px 흔들리던 문제. 답변 말풍선 최소폭도 첫 인사말 기준으로 ratchet(커지면 유지, 안 줄어듦).
- **챗봇 작물 자동인식** (PR #43): `crop_id` 없으면(밭 2개 이상 유저 등) RAG가 5종 작물 지식을
  뒤섞어 검색해 로컬 LLM이 헷갈려 거절 문구+답변이 섞여 나오는 등 불안정했음. 질문 문장에서
  작물명(사과·배·오이·감자·상추) 자동 인식해 검색 좁힘. 미지원 작물(토마토 등)은 기존대로
  전문가 상담 유도 유지(팀 확인됨, 의도된 동작).

## 후속 (범위 밖, 별도 PR)

- 답변 장황함 프롬프트 미세조정 → §9 골든셋/LLM-as-judge 평가에서.
- 생략형 후속질문("그럼 물은?") 검색 정확도 개선.

## 참고 문서

- 메모리: `chat-history-auth-roadmap`, `frontend-stack-nextjs`, `user-verifies-backend`,
  `auth-method-jwt-httponly-cookie`, `llm_model_choice_exaone`, `region-vs-district-data-units`,
  `soil-delta-p0-shadow-state`
- `docs/main-logic-guide.md`, `docs/ml/backend_ml_handoff.md`, `docs/auth-security.md`,
  `docs/llm-integration.md`, `docs/long-term-tab-api.md`, `docs/design/Correction_Re_Draft.md`(FE 설계 기준)
- `DB.md`, `PRD.md`(§5 지역 단위 2층 분리), `CLAUDE.md`
