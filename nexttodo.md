# 다음 할 일 — 상담 챗봇(RAG) 백엔드 구현

메인 대시보드 기능이 아니라 UI에서 별도로 클릭해 들어가는 부가 기능. 온디맨드 실시간 스트리밍(사전생성 캐시 아님).

## 이미 정해진 것 (다시 고민하지 말 것)

- **LLM 모델**: `exaone3.5:7.8b` 그대로 재사용 (챗봇 전용 모델 따로 안 씀). Qwen3 8B와 벤치마크 비교해서 결정함 — 근거: `docs/llm-benchmark-eval.md`, 메모리 `llm_model_choice_exaone`.
- **임베딩 모델**: `bge-m3` (Ollama, `config.embedding_model`). 1024차원.
- **벡터 저장소**: pgvector, `knowledge_chunk` 테이블. ChromaDB 등 별도 벡터DB 안 씀(이미 검토 완료, CLAUDE.md/DB.md에 명시). 5작물 172개 청크 이미 임베딩·적재 완료(`scripts/embed_corpus.py`).
- **모델 상시 로드**: 임베딩(bge-m3)과 생성(exaone) 둘 다 VRAM에 항상 떠 있어야 함(재로딩 비용이 10초 예산을 넘김 — bge-m3 재로딩 +3.4초, exaone 재로딩 +6~7초 실측). **LlmClient/임베딩 클라이언트 코드에서 모든 Ollama API 호출에 `"keep_alive": -1`을 기본값으로 박아넣을 것** — OS 환경변수(OLLAMA_KEEP_ALIVE)에 의존하면 Ollama 재시작 시 초기화되므로 코드에서 명시.
- **응답 시간 예산**: 총 10초(임베딩+검색+생성 다 포함). exaone 웜 상태 평균 ~3.6초라 여유 있음. `num_predict`는 150~200 정도로 캡 걸기(테스트에서 "3~5문장" 지침을 살짝 넘겨 장황해지는 경향 있었음).
- **프롬프트 설계 방향**: 역할 지정 + 형식 지정 기법(`#명령문/#제약조건/#입력문/#출력형식`) + 근거 없으면 거절하는 패턴을 few-shot으로 고정. Chain-of-Thought, 멀티 페르소나, 할루시네이션 유도 기법은 이 프로젝트 성격(정확성/환각방지 최우선)과 안 맞아서 안 씀.

## 구현할 것

- [ ] **검색 함수**: 사용자 질문 → bge-m3 임베딩(Ollama `/api/embed`) → `knowledge_chunk`에서 pgvector 코사인 유사도 top-k(예: k=3) 검색, `crop_id` 필터 옵션
- [ ] **프롬프트 템플릿 파일**: 코드에 흩뿌리지 말고 템플릿 파일/상수로 버전 관리(CLAUDE.md §13). 위 "프롬프트 설계 방향" 반영
- [ ] **LlmClient 구현체**: `docs/llm-integration.md` §4 계약대로 `OllamaClient.generate(prompt) -> str`. httpx 호출, `keep_alive:-1`, 타임아웃, `num_predict` 캡
- [ ] **폴백 규칙**: LLM 실패/빈 응답 시 규칙 기반 기본 문구로 대체(§5), 서비스 안 죽게
- [ ] **FastAPI 엔드포인트**: `POST /api/v1/.../chat` — SSE 스트리밍, `ApiResponse` 래퍼 안 씀(§6 스트리밍 예외)
- [ ] **서비스 계층**: 검색+프롬프트조립+LlmClient 호출 묶기. 라우터에 로직 새지 않게(`app/services/`)
- [ ] **pydantic 스키마**: 요청/응답 DTO, SQLAlchemy 모델 직접 노출 금지
- [ ] **최소 실행 가능한 테스트** 하나 이상(결정론적 로직 부분 — 예: 프롬프트 조립 함수, 폴백 트리거 조건)

## DB 마이그레이션 — 이 브랜치 받으면 해야 할 것

`chatbot` 브랜치에서 마이그레이션 체인이 `0001 → 0002 → 0003`(head)까지 늘어남.
`0003_knowledge_chunk.py`가 새로 추가됨: `CREATE EXTENSION vector` + `knowledge_chunk` 테이블 생성 + crop 5종 시드.
이 브랜치를 처음 받는 사람(또는 새 로컬 환경)은 순서대로:

1. `docker compose up -d` — `docker-compose.yml` 이미지가 `postgres:16` → `pgvector/pgvector:pg16`으로 바뀜. 이미 떠 있던 컨테이너가 있으면 이미지 교체를 위해 재생성 필요(로컬 개발 DB라 볼륨 삭제해도 무방, DB.md §9.1).
2. `cd backend && pip install -r requirements.txt` — `pgvector` 파이썬 드라이버 추가됨(SQLAlchemy `Vector` 컬럼 타입에 필요).
3. `cd backend && alembic upgrade head` — 0001/0002/0003 순서로 적용. 로컬에 처음 반영하는 거면 전부, 이미 0001/0002까지 적용된 로컬이면 0003만 새로 적용됨.
4. (선택, RAG 데이터 필요할 때만) `backend/.venv/Scripts/python.exe scripts/embed_corpus.py` — bge-m3로 5작물 청크 임베딩해 `knowledge_chunk`에 채움. diff 동기화라 재실행해도 안전(변경분만 처리).

## 재개할 때 다시 볼 문서

- `docs/llm-integration.md` (LlmClient 계약, 폴백 규칙, 생성 타이밍)
- `docs/llm-benchmark-eval.md` (모델 비교 실측 근거)
- `DB.md` §3.15 (knowledge_chunk 스키마)
- `CLAUDE.md` §13 (LLM 프롬프트 관리 규칙), §6 (스트리밍 예외)
