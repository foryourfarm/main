# 다음 할 일

> 갱신: 2026-07-25. "✅ 완료 (dev 머지)"는 실제로 dev에 머지된 것만.
> 상세 방향은 메모리/`docs/` 참고.

## 🔶 커밋·PR 완료, dev 반영 대기 (5분할 중 1개만 dev 도달)

**stacked PR 사고**: PR #21~25로 5분할해 올렸으나 #22~25가 dev가 아니라 **직전 feature 브랜치를
base로** 머지돼서(#22→models, #23→service, #24→suitability, #25→region) dev엔 #21만 들어갔다.
나머지 4개 커밋은 `feature/dashboard-weather-climatology`에 dev 위 선형으로 쌓여 있어, 이 브랜치를
dev로 한 번 더 PR해서 회수한다(내용은 #22~25에서 이미 리뷰됨).

| 커밋 | 내용 | dev 반영 |
|---|---|---|
| `95f1cee` | P0 토양변화 shadow 로그 모델 + 마이그레이션 | ✅ PR #21 |
| `4c2afa7` | P0 shadow 추론 서비스 + 테스트 | ⏳ 회수 PR |
| `4b7e105` | P2 생육단계 resolver + 적합도 API | ⏳ 회수 PR |
| `1472b72` | region 마스터 256개 시드 | ⏳ 회수 PR |
| `a37a800` | 대시보드 집계 API + 기상 평년치 ETL | ⏳ 회수 PR |

**P0: 토양변화 shadow 추론 — 뼈대만**
- 모델 `soil_state_snapshot`/`prediction_shadow` + `0006` 마이그레이션(DB 적용됨)
- 경량 추론 `infra/ml/soil_delta.py`(artifact 로더+검증+Ridge 한 줄 추론, sklearn 불필요)
- 서비스 `soil_delta_service.py`(입력검증→추론→폴백→shadow 로그), DTO `schemas/soil_delta.py`
- 테스트 fixture artifact로 12개 검증(결정론·중앙값대치·폴백·available_p 항상 미채택)
- **exporter(①)만 못 함** — `scripts/ml/final_model.py`+`data/ml/training_rows.csv`가 `.gitignore` 대상이라 이 리포에 실물 없음. 진짜 artifact 생성 불가, fixture로만 검증된 상태.

**P2: 작물 적합도 룰 API 연결 — 완료**
- 결정 확정: temp_day=월평년(`temp_avg_normal`) 근사(한계 병기) / 생육단계 resolver(2모드: 연중일자·파종후경과일) / 60점 경계 유지
- 시드 `crop_growth_stage`(6행, 농촌진흥청 농사로 근거) + `0007` 마이그레이션(DB 적용됨)
- `growth_stage_service.resolve_growth_stage` + `suitability_service.compute_farm_suitability`
- `GET /api/v1/farms/{farm_id}/suitability`(소유권 스코프, 404/401 검증됨)
- **suitability_result 캐시 write는 의도적으로 생략** — 지역 baseline 캐시인데 `region_soil_profile` 모델·테이블이 없어 밭 고유 결과를 넣으면 클로버링 버그. region 데이터 갖춰지면 별도 PR.

**대시보드 집계 + 평년치 적재 — 완료**
- `GET /api/v1/dashboard`(작물 카드: crop/region명+생육단계 한글라벨+과수🌳/밭🌾 타입(시드에서 파생)+적합도)
- region 마스터 256개 시드 `0008`(CSV에서 프로그램 생성, DB 적용됨 — **기존 강릉 id 1→226으로 바뀜, region_id=1 참조하던 데이터 있으면 재확인 필요**)
- `scripts/load_weather_climatology.py`(관측 5년 평균 근사, 102지역×12월=1224행, `source='obs_mean_2021_2025'`, temp_avg+rainfall만 — night_min/sunlight 소스 없어 null)
- 실동작 검증: 테스트 밭을 커버지역(순천시)으로 옮겨 대시보드 카드 75.6점 A 등급 확인. 전체 66개 테스트 2회 통과.

전체 66개 백엔드 테스트 통과(`backend/.venv/Scripts/python.exe -m unittest discover -s tests`).

## ✅ 완료 (dev 머지)

**챗봇(상담 RAG)**
- 백엔드 RAG: bge-m3 임베딩 → `knowledge_chunk` pgvector top-k(`rag_top_k=3`, crop 필터) → exaone3.5 스트리밍. 폴백(임베딩/검색/생성 실패·근거없음)으로 SSE 반드시 끝맺음. (`chat_service`, `llm_client`, `api/chat.py`)
- 밭 컨텍스트 주입("내 땅 맞춤") — 로그인+밭이면 `user_farm`/`soil_state`(추정치) 프롬프트 주입, 밭 작물로 crop_id 자동설정. **PR #14**.
- **대화 영속화** — `chat_message(user_id,session_id,role,content,created_at)` + Alembic 0005(FK CASCADE). authed+`session_id`면 서버가 `(user_id,session_id)` 스코프로 DB 로드/저장, 게스트는 클라 history. 소유권·저장정책(성공 턴만). **PR #16**. `DB.md` §3.16.
  - 실스택 종단 검증 완료(멀티턴 맥락 로드·4행 적재·읽기/쓰기 소유권 격리). 계정삭제 시 대화 CASCADE 삭제 실동작 확인.
- **프롬프트 인젝션/탈옥 방어**(`chatbot-v4`) — #보안 규칙 + 방어 few-shot. 정체노출/프롬프트유출/규칙초기화/간접주입 차단. 라이브 8종 공격 거부·정상질문 회귀없음. **PR #19**. `docs/llm-integration.md` §11.
- 답변 절단 수정: `llm_num_predict` 200→512(한국어 답변 문장 중간 절단). **PR #17**.

**인증**
- 백엔드: 분리 토큰 JWT(access 메모리 + refresh httpOnly 쿠키), signup/login/refresh/logout/me + bcrypt. **PR #12**. 계약 `docs/auth-security.md`.
- 프론트 연동: `lib/auth`(토큰스토어+authFetch 401인터셉터), `AuthProvider`(세션복구), login/signup 페이지, AuthBar. 크로스오리진 종단 검증. **PR #18**.

**프론트엔드(Next.js)**
- Next 16 App Router + React 19 + TS strict 스캐폴드. 챗봇 상담 화면(`/chat`) 게스트 모드 SSE 연결, 생각중 표시. **PR #17**. (스택 결정: 메모리 `frontend-stack-nextjs`)

**문서/정리**
- 팀원용 메인로직 구현 가이드 `docs/main-logic-guide.md`(P0~P3 + ML 데이터 최신화 지속반영). 루트 문서/PDF를 `docs/{design,data,api-specs}`로 정리. `docs/README.md` 인덱스. **PR #20**.

## ⏭️ 미착수 / 다음

**메인 로직 백엔드 — 블로킹된 것**
- P0 exporter: `scripts/ml/final_model.py` + `data/ml/training_rows.csv`를 리포에 넣어야 진짜 artifact 생성 가능(둘 다 현재 없음)
- P1 노출 게이트: 라이브 실측(예측↔재검정 쌍)이 쌓여야 MAE·구간포함률 재계산 가능 — 지금은 데이터 자체가 없음
- P3 first-party 수집: `crop_outcome_record`(수확기 입력) + `farm_action_log` 성분 보강 — **"수집 그릇"은 지금 코드로 만들 수 있음**(데이터 자체는 유저가 써야 쌓임), 아직 미착수

**기상 데이터 — 다음 자연스러운 확장**
- **장기예보(3개월 전망) 적재 — R2 해결됨, 착수 가능** (2026-07-25 실측 검증)
  - 소스: 기상청 3개월전망 **RSS XML** `http://www.kma.go.kr/repositary/xml/fct/mon/img/fct_mon3rss_108_YYYYMMDD.xml`
    (data.go.kr 15050698은 PDF fileData라 사용 불가, API허브 예특보엔 장기예보 없음)
  - tercile 확률이 숫자 태그로 옴 → `weather_outlook` 스키마 그대로 사용 가능:
    `<local_ta>/<local_ta_name>` + `<month_local_ta>/<monthN_local_ta_{normalYear,similarRange,minVal,similarVal,maxVal}>`
    (예: 전국 8월 평년값 25.1, 비슷범위 24.6~25.6, 낮음10/비슷30/높음60). 강수량은 `local_rn`/`_rn_` 동형.
  - **δ 미결정 해소 가능**: `similarRange` 반폭이 tercile 경계 폭 → δ를 임의 상수 대신 데이터에서 유도(`DB.md` §10).
  - 필수 방어 2개(둘 다 실측된 실제 케이스): ① 발표일 이동 — 매월 23일 기준이나 2026-05는 **22일**(주말),
    23·24일 URL은 존재하지 않음 → 23일부터 ±며칠 탐색. ② **HTTP 200인데 HTML 에러페이지**를 반환 →
    상태코드만 믿지 말고 XML 파싱·루트/태그 존재까지 검증(안 하면 쓰레기 적재).
  - 남은 결정: 권역 13개(전국+12) → `region` 256개 매핑. `region.sido`로 대부분 유도되나
    **강원 영서/영동은 시/군 단위 수동 매핑 필요** → 임의 결정 말고 시드로 근거 남길 것(`CLAUDE.md` §3-2).
  - 자동화: 발표 주기 고정 + `uq_outlook` 유니크로 멱등 → 스케줄러로 자동 갱신(수동 버튼 불필요, 스크립트 직접 실행이 곧 수동 경로).
- 기상청 공식 30년 평년값 + 야간최저·일조 API 발급(현재는 관측 5년 평균 근사로 2개 지표만 대체 중)
- 단기 탭(당일 실시간 기상·위험배너·오늘의 추천행동) — weather_snapshot 연동 전무, API 키 미발급

**대시보드/FE 남은 위젯** — `docs/design/` 대시보드 스펙 대비
- 데이터 신뢰도 배지(출처 N/3, 토양=흙토람/기상=평년 표기) — 백엔드 토양 provenance는 지금도 가능, 기상 부분은 위 항목 선행
- ~~장기 탭 월별 전망 히트맵~~ → 백엔드 완료(`GET /api/v1/farms/{farm_id}/monthly-outlook`).
  **FE 렌더링은 미착수**. 현재는 평년치만 — 위 outlook 보정 미적용(`DB.md` §8.1 대비 갭, limitations에 명시함)
- 시기별 커리큘럼/자연어 설명(LLM) — 정형데이터 준비됨, LLM 연결 미착수
- 로그인 게이팅 미들웨어, 온보딩(지역/작물 등록) 페이지, 대시보드/밭상세 화면 자체(백엔드 API는 준비됨)
- 챗봇 로그인 모드 연결: FE에서 access 첨부 + `session_id` + `farm_id` 전달 — 백엔드는 이미 준비됨

**배포** — GCP(프론트/백엔드 Cloud Run + Cloud SQL + 로컬 LLM은 GPU VM). 별도 논의 예정.

## 후속 (범위 밖, 별도 PR)

- 답변 장황함 프롬프트 미세조정 → §9 골든셋/LLM-as-judge 평가에서.
- 생략형 후속질문("그럼 물은?") 검색 정확도 — 필요 시 history로 질문 압축(LLM 1콜)(`chat_service` ponytail 주석).

## 참고 문서

- 메모리: `chat-history-auth-roadmap`(챗봇 완성), `frontend-stack-nextjs`, `user-verifies-backend`(백엔드 완료 전 육안 확인), `auth-method-jwt-httponly-cookie`, `llm_model_choice_exaone`, `soil-delta-p0-shadow-state`(P0/P2/대시보드/평년치 상세 근거·블로커)
- `docs/main-logic-guide.md`, `docs/ml/backend_ml_handoff.md`, `docs/auth-security.md`, `docs/llm-integration.md`, `docs/design/`(대시보드 UI 스펙)
- `DB.md`(§3.15 knowledge_chunk, §3.16 chat_message, §11 인증/인가), `CLAUDE.md` §6/§10/§11/§13
