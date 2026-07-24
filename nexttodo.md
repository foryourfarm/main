# 다음 할 일 — 챗봇 히스토리 영속화 + 밭 컨텍스트 주입 (인증 연동)

메인 대시보드 기능이 아니라 UI에서 별도로 클릭해 들어가는 부가 기능. 온디맨드 실시간 스트리밍(사전생성 캐시 아님).

## 이미 구현 완료 (feature/chatbot-backend)

기본 상담 챗봇(RAG) 백엔드가 동작한다. 로컬 스택(Ollama exaone3.5+bge-m3, pgvector 172청크)으로 종단 확인함.

- **검색**: 질문 → bge-m3 임베딩(Ollama `/api/embed`, `keep_alive:-1`) → `knowledge_chunk` pgvector 코사인 top-k(`config.rag_top_k=3`), `crop_id` 필터. (`app/infra/embedding_client.py`, `app/services/chat_service.py::retrieve_chunks`)
- **LlmClient**: `OllamaClient.generate` / `generate_stream`, `keep_alive:-1` 코드 명시, `num_predict`/`temperature` config 캡. (`app/infra/llm_client.py`)
- **프롬프트**: 코드 분리·버전 관리(`PROMPT_VERSION=chatbot-v2`). 역할+형식(#명령문/#제약조건/#입력문/#출력형식) + few-shot 3종: 근거기반 답변 / 작물 불명확 시 5종 되묻기 / 근거 없으면 전문가·농사로 안내 거절. (`app/prompts/chatbot.py`)
- **멀티턴**: 무상태 + 클라이언트 `history` 재전송(서버/DB 세션 없음). 최근 `chat_history_max_messages=6`개만 프롬프트 주입.
- **폴백**: 임베딩/검색/생성 실패·빈 응답·근거 없음 모두 규칙 기반 문구로 흡수, SSE 스트림 반드시 끝맺음(§13, §18-5).
- **엔드포인트**: `POST /api/v1/chat` SSE(`text/event-stream`), `ApiResponse` 래퍼 미사용(§6 스트리밍 예외). (`app/api/chat.py`)
- **테스트**: 프롬프트 조립·history·되묻기·폴백 트리거 9개(네트워크·DB 불필요, `tests/test_chat_service.py`).

## 다음 구현 — 인증 도입과 함께 (2026-07-24 진행 중)

> 상세 방향: 메모리 `chat-history-auth-roadmap`. 현재 무상태 인터페이스가 선행호환이라 갈아엎을 필요 없음.

- [x] **인증 설계 확정** — 분리 토큰 JWT(access 메모리 + refresh httpOnly 쿠키). 이메일 인증 안 함. **PR #12 머지 완료**. 계약: `docs/auth-security.md`, 근거: 메모리 `auth-method-jwt-httponly-cookie`.
- [x] **인증 백엔드 구현** — signup·login·refresh·logout·me + bcrypt + `get_current_user`. **PR #12 머지 완료**.
- [x] **밭 컨텍스트 주입(핵심 값)** — 로그인+밭이면 `user_farm`/`soil_state`를 프롬프트에 주입("내 땅 맞춤"), 밭 작물로 crop_id 자동설정(되묻기 제거), 토양=추정치 표기, 생육단계는 경과일만(매핑 §19 미확정). **PR #14 (오픈, 머지 대기)**. FE 계약: `docs/llm-integration.md` §10.
  - 종단 검증 완료(Postgres 172청크 + Ollama exaone3.5+bge-m3): 로그인 시 pH 5.3 추정치를 매뉴얼(적정 6.5~7.0)과 엮어 석회 처방까지. 더미 검증 중 토양 수치 꼬리 0 표시 버그 발견·수정(`Decimal.normalize`).
- [x] **`chat_message` 테이블 + Alembic 마이그레이션(0005)**: `(user_id, session_id, role, content, created_at)`. 런타임 기록 — 시드 아님. `DB.md` §3.16 명세 추가. 모델 `app/models/chat_message.py`.
- [x] **`ChatRequest.session_id: str | None` 추가**: authed+session_id면 서버가 DB에서 history 로드/저장(body history 무시), 아니면 지금처럼 클라 `history`. session_id는 클라가 uuid4 생성. 형식검증 `^[0-9a-fA-F-]{8,64}$`.
- [x] **소유권 검증**: `load_history`/`save_turn`가 항상 `(user_id, session_id)` 스코프 → 남의 session_id는 빈 히스토리. 계정삭제 시 대화 삭제(FK CASCADE). 성공한 턴만 저장(sink 비면 미저장).
- [x] 최소 테스트: `tests/test_chat_persistence.py` — 로드/저장 라운드트립, limit 최근순, 소유권 거부, 세션 격리(sqlite 인메모리, 5개 통과).

> **PR 2 미검증 잔여(육안 확인 필요, 메모리 `user-verifies-backend`)**: 아직 실스택 종단 확인 안 함. 확인 절차 = ①`alembic upgrade head`로 0005 적용 → `\d chat_message` ②로그인 access 토큰으로 `session_id` 붙여 `/chat` 2연속 호출 → 2번째가 1번째 맥락 이어받는지 + `chat_message`에 4행 쌓이는지 ③다른 유저 토큰 + 같은 session_id → 히스토리 안 새는지.

> **재개 메모(2026-07-24)**: 위 미완 3개 = "PR 2(대화 영속화)". dev는 `0cdf013`(PR #11 ML·#12 auth·#13 soil-fix 머지됨). PR #14(밭 컨텍스트)만 머지 확인하면 됨. Docker/Ollama 켜둔 상태로 마지막 세션 종료 → 재개 시 `docker ps`로 확인. 마이그레이션 head=0004 → 새 건 0005. 참고 커밋: auth `1af78d3`, 밭 컨텍스트 `4b7365d`+`2f3d971`.
> 밭 컨텍스트 구현 위치: `chat_service.load_farm_context`, `prompts/chatbot.py`(FarmContext/format_farm_context), `api/deps.get_current_user_optional`, `schemas/chat.ChatRequest.farm_id`.

## 후속 (범위 밖, 별도 PR)

- 답변이 "3~5문장" 지침을 살짝 넘겨 장황해지는 경향 → 프롬프트 미세조정은 §9 골든셋/LLM-as-judge 평가에서.
- 생략형 후속질문("그럼 물은?") 검색 정확도 한계 — 필요 시 history로 질문 압축(LLM 1콜) 추가(`chat_service` ponytail 주석).
- ~~**[dev 기존 버그]** `soil_profile_client`가 `Deepsoil_Qlt_Cd`를 읽는데 공식 스펙 XML은 `Deepsoil_Qlt_Code`~~ → **해결(PR #13 머지)**. 응답 필드 4개 `_Cd`→`_Code`. get_soil_profile 미호출이라 저장 데이터 손상 없었음.

## 재개할 때 다시 볼 문서

- 메모리 `chat-history-auth-roadmap`, `user-verifies-backend`(완료 전 육안 확인)
- `docs/llm-integration.md` (LlmClient 계약, 폴백 규칙, §2 생성 타이밍)
- `DB.md` §3.15 (knowledge_chunk), §11 인증/인가
- `CLAUDE.md` §13(LLM 프롬프트), §6(스트리밍 예외), §11(인가), §10(마이그레이션)
