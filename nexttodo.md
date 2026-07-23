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

## 다음 구현 — 인증 도입과 함께 (2026-07-25 시작)

> 상세 방향: 메모리 `chat-history-auth-roadmap`. 현재 무상태 인터페이스가 선행호환이라 갈아엎을 필요 없음.

- [ ] **인증 설계 확정 먼저** — 세션ID 포맷·소유권 규칙이 인증 방식(세션/토큰)에 딸려 정해짐(§11, 미결정 §19).
- [ ] **`chat_message` 테이블 + Alembic 마이그레이션**: `(user_id, session_id, role, content, created_at)`. 마스터 데이터 아님(런타임 기록) — 시드 아님.
- [ ] **`ChatRequest.session_id: str | None` 추가**: authed면 서버가 session_id로 DB에서 history 로드/저장, 게스트면 지금처럼 클라 `history` 경로 유지.
- [ ] **소유권 검증**: 본인 대화만 접근(요청 유저 == chat_message.user_id, §11). 계정삭제 시 대화 삭제(§17 보존정책).
- [ ] **밭 컨텍스트 주입(핵심 값)**: 로그인+밭이 붙으면 유저의 실제 `farm_id`/`soil_state`/작물을 프롬프트에 주입 → "내 땅 맞춤". 대화 저장보다 이게 우선순위.
- [ ] 최소 테스트: session_id 기반 history 로드/저장, 소유권 거부 케이스.

## 후속 (범위 밖, 별도 PR)

- 답변이 "3~5문장" 지침을 살짝 넘겨 장황해지는 경향 → 프롬프트 미세조정은 §9 골든셋/LLM-as-judge 평가에서.
- 생략형 후속질문("그럼 물은?") 검색 정확도 한계 — 필요 시 history로 질문 압축(LLM 1콜) 추가(`chat_service` ponytail 주석).
- **[dev 기존 버그]** `soil_profile_client`가 `Deepsoil_Qlt_Cd`를 읽는데 공식 스펙 XML은 `Deepsoil_Qlt_Code` → `test_public_api_base` 1건 실패. 별도 fix PR.

## 재개할 때 다시 볼 문서

- 메모리 `chat-history-auth-roadmap`, `user-verifies-backend`(완료 전 육안 확인)
- `docs/llm-integration.md` (LlmClient 계약, 폴백 규칙, §2 생성 타이밍)
- `DB.md` §3.15 (knowledge_chunk), §11 인증/인가
- `CLAUDE.md` §13(LLM 프롬프트), §6(스트리밍 예외), §11(인가), §10(마이그레이션)
