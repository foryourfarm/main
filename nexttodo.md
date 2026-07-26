# 다음 할 일

> 갱신: 2026-07-25 (야간). "✅ 완료 (dev 머지)"는 실제로 dev에 머지된 것만.
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
   - **근본 해결(미착수)**: 기상청 공식 30년 평년값 API 발급 → 전국 256개 완전 커버.
     지금 두 조치는 그 전까지의 완화책.
   - **커밋 전 확인할 것**: `data/03_weather_monthly_modified.csv` append 결과가 실제
     git 추적 대상(gitignore 안 됨) — 840행 추가된 채로 커밋해도 되는지 확인.

2. **강수 지표 단위 혼동 버그 (이미 수정·커밋됨, PR #33)** — `rainfall` 하나에 월평년(mm/월)과
   예보 일누적(mm/일)을 섞어써서 "비 안 온 날(0mm)이 위험"으로 오판정되던 것.
   `rainfall_monthly`/`rainfall_daily`로 분리, 감자의 근거 없는 월강수 기준(시즌 총량을
   12로 나눈 값)도 제거(0011~0013). 상세는 PR #33 본문.

## 🟡 FE 설정·네비게이션이 설계 문서와 크게 어긋남

`docs/design/Correction_Re_Draft.md`(팀 확정 UI 설계) 대비 지금 화면 격차:

| 설계 | 지금 상태 |
|---|---|
| 네비게이션: 대시보드\|상담\|설정 (간결) | 일치(설정 추가 완료) |
| 장기/단기 = **카드 클릭 → 모달** | 장기/단기 = **탭 전환**(모달 아님) — 기능은 되지만 설계와 다른 패턴 |
| **설정 탭**: 지역/작물 재설정 + 데이터 출처 footer | 구현됨(`/settings`) — 아래 참고 |
| 카드에 LLM 한 줄 설명 | 없음(LLM 미착수라 당연 — 후순위 항목) |
| 팔레트: Primary #2D5016 등 (Design01) | `farm.module.css`가 이미 이 팔레트 사용 중 — 이 부분은 일치 |

**다음 세션에서 결정할 것**: 모달 방식으로 갈지 지금 탭 방식을 유지할지 팀 확인 필요
(모달 전환은 `/farm/[farmId]` 라우트 자체를 없애고 대시보드에 오버레이로 붙이는
구조 변경이라 작지 않음). 설정 화면(지역/작물 변경, 밭 삭제)은 이견 없이 필요 —
지금 밭을 잘못 등록해도 고칠 방법이 없음.

## ⏭️ 미착수 / 다음

**설정 화면 — 구현됨(PR, 사람 검증 대기)**
- `GET/PATCH/DELETE /api/v1/farms` + `/settings` 화면 + 출처 footer. 계약은 `docs/farm-settings-api.md`.
- 마이그레이션 `0014`: `user_farm.bjd_code` 추가(읍면동을 저장하지 않아 수정 화면에서 보여줄 수도
  없었음). 기존 행은 `soil_state.base_source` 문구에서 backfill 시도, 통합전코드라 못 채운 행은 NULL
  (로컬 테스트 밭 9건 전부 NULL로 확인 — 설정에서 재선택하면 채워짐).
- 위치·작물 변경 시 `soil_state` 재초기화(읍면동 또는 경지구분이 바뀔 때만 — 사과→배는 재조회 안 함).
  실측 이력·행위 기록은 보존(위치 변경으로 지울 사실 아님).
- 네비게이션도 설계대로 정리: 대시보드 | 상담 | 설정(밭 등록은 설정·대시보드에서 진입).

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

**FE 남은 것**
- 위 "설정·네비게이션" 격차 해소
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
