# 🌾 For Your Farm

귀농인 맞춤형 재배 의사결정 지원 서비스 — 실제 귀농인이 자기 지역·작물을 등록하면, 매일 실제 공공데이터(기상·토양) 기반으로 장기(시즌 커리큘럼)·단기(당일 실시간 대응) 행동 가이드를 자연어로 제공한다.

> "박제된 매뉴얼이 아니라, 내 땅과 오늘 날씨에 맞는 맞춤형 행동 가이드."
> 전국 표준 재배 지침만으로는 정착지 고유의 토양·기후 차이를 알 수 없다. 지역·작물을 등록하면 실제 데이터로 적합도를 분석하고, 위험 요소를 선제적으로 안내한다.

---

## 목차

- [스크린샷](#스크린샷)
- [기술 스택](#기술-스택)
- [아키텍처](#아키텍처)
- [폴더 구조](#폴더-구조)
- [설치](#설치)
- [환경 변수](#환경-변수)
- [실행](#실행)
- [Build](#build)
- [Deploy](#deploy)
- [Cloud SQL 연결](#cloud-sql-연결)
- [개발 규칙](#개발-규칙)
- [브랜치 전략](#브랜치-전략)
- [기여 방법](#기여-방법)

---

## 스크린샷

| 대시보드 | 장기 탭 (시즌 커리큘럼) | 단기 탭 (당일 예보·행동) |
|---|---|---|
| _(스크린샷 자리)_ | _(스크린샷 자리)_ | _(스크린샷 자리)_ |

---

## 기술 스택

**대상 작물 (5종 고정)**: 사과, 배, 오이, 감자, 상추

| 영역 | 스택 |
|---|---|
| Frontend | Next.js (App Router), TypeScript, React |
| Backend | FastAPI (Python), SQLAlchemy 2.0, Alembic |
| Database | PostgreSQL (GCP Cloud SQL) |
| Infra | GCP Cloud Run |
| AI | 로컬 LLM (행동추천·상담) — 개발 Ollama / 서빙 vLLM |
| 외부 데이터 | 농진청 흙토람(토양), 기상청(실황·단기예보) — 실시간 조회 + 캐싱 |

자세한 코딩 규칙은 [`CLAUDE.md`](./CLAUDE.md), 제품 명세는 [`PRD.md`](./PRD.md), DB 설계는 [`DB.md`](./DB.md) 참고.

---

## 아키텍처

```
                    ┌──────────────────────┐
                    │   Frontend (Next.js) │
                    │  대시보드·장/단기 탭  │
                    │  챗봇 UI              │
                    └──────────┬───────────┘
                               │ REST API
                    ┌──────────▼───────────┐
                    │  Backend (FastAPI)    │
                    │  ─ 적합도 룰 엔진(장기)│
                    │  ─ 토양변화 추정(단기) │
                    │  ─ 위험신호 판정       │
                    │  ─ LLM 연동·스케줄러   │
                    └───┬───────────────┬───┘
                        │ SQLAlchemy    │ HTTP
              ┌─────────▼──────┐  ┌─────▼──────────┐
              │ PostgreSQL     │  │ 로컬 LLM        │
              │ (Cloud SQL)    │  │ (Ollama/vLLM)   │
              └────────────────┘  └────────────────┘
                        ▲
              실시간 조회 + 캐싱
              ┌─────────┴──────────┐
              │ 흙토람 / 기상청 API │
              └────────────────────┘
```

- 클라이언트는 DB에 직접 접속하지 않는다. 모든 접근은 FastAPI를 경유.
- 단기 탭은 기상청 실황·단기예보를 **실시간 조회**하되 캐싱·갱신주기 제한으로 방어. 장기 탭은 평년 데이터 기반 적합도.
- LLM 일일 추천은 스케줄러로 사전생성해 DB에 저장, 챗봇만 실시간(vLLM). 자세한 설계는 `PRD.md`.

---

## 폴더 구조

```
foryourfarm/
├── CLAUDE.md            # 개발 헌법 (컨벤션, 협업 규칙, 금지사항)
├── PRD.md               # 제품 요구사항 명세
├── DB.md                # DB 설계
├── README.md            # 본 문서
├── docs/
│   ├── llm-integration.md
│   └── seed/            # 생육 지침 시드 (작물별 JSON/YAML)
├── frontend/            # Next.js (App Router)
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── hooks/
│   ├── types/
│   └── public/assets/
└── backend/             # FastAPI (Python)
    ├── requirements.txt
    ├── alembic.ini
    ├── alembic/
    │   └── versions/    # 마이그레이션 (0001_init_schema.py)
    └── app/
        ├── main.py      # FastAPI 앱 + 예외 핸들러
        ├── core/        # config (설정)
        ├── db/          # SQLAlchemy 세션
        ├── models/      # SQLAlchemy 모델 (region, crop, ...)
        ├── schemas/     # pydantic DTO (ApiResponse 등)
        ├── api/         # 라우터 (health, ...)
        ├── services/    # 유스케이스, 룰 엔진
        └── infra/       # 공공 API·LLM 클라이언트, 스케줄러
```

---

## 설치

**요구 사항**
- Node.js 20+
- Python 3.11+ (개발 환경은 3.14 확인됨)
- Docker Desktop (로컬 PostgreSQL 구동용 — `pgvector/pgvector:pg16` 이미지, 챗봇 RAG용 벡터 확장 포함)
- 로컬 LLM 런타임 (Ollama) — 생성 `exaone3.5:7.8b` + 임베딩 `bge-m3`. 아래 [로컬 LLM · 챗봇(RAG) 준비](#로컬-llm--챗봇rag-준비) 참고

```bash
git clone <repo-url>
cd foryourfarm

# frontend
cd frontend
npm install

# backend — 가상환경 + 의존성 설치
cd ../backend
python -m venv .venv
# Windows: .venv\Scripts\activate   /  macOS·Linux: source .venv/bin/activate
.venv/Scripts/pip install -r requirements.txt   # (셸에 맞게)
```

---

## PostgreSQL 로컬 구축

Postgre를 따로 설치할 필요 없이 Docker로 띄운다. 팀원 전부 동일한 방법으로 구축한다.

```bash
# 1. 레포 루트에서 컨테이너 실행 (최초 1회, 이후엔 docker compose up -d 만 반복)
docker compose up -d

# 2. 떠 있는지 확인
docker ps   # foryourfarm-db 가 보이면 정상
```

- 접속 정보: `host=localhost` `port=5432` `db=foryourfarm` `user=foryourfarm` `password=foryourfarm` — [환경 변수](#환경-변수)의 `DATABASE_URL` 기본값과 동일하게 맞춰뒀다.
- **스키마 적용은 Alembic으로**: `cd backend && .venv/Scripts/alembic upgrade head` (셸에 맞게). baseline은 `backend/alembic/versions/0001_init_schema.py`.
- 스키마·컬럼의 의미는 [`DB.md`](./DB.md)에 전부 설명되어 있다. 실제 데이터(작물/지역/생육지침/토양변화계수)는 아직 안 채워져 있으니, 시드 작업은 `DB.md` §9 참고.
- 컨테이너를 완전히 밀고 새로 시작하고 싶으면: `docker compose down -v` (볼륨까지 삭제 — 로컬 개발 DB에서만).

---

## 환경 변수

**frontend/.env.local**
```
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

- 변수명은 `NEXT_PUBLIC_API_BASE`다(`frontend/lib/auth.ts`). `_URL`을 붙이면 코드가 못 읽고
  기본값으로 조용히 넘어간다 — 화면엔 에러가 안 뜨고 요청만 안 간다.
- **`/api/v1`을 붙이지 않는다.** 경로는 `authFetch`가 붙인다. 넣으면 `/api/v1/api/v1/...`이 된다.
- 포트는 **8000**이다. 백엔드를 8080으로 띄우면 프론트가 못 찾는다(아래 [실행](#실행)과 맞출 것).

**`.env`** — 리포 **루트**에 둔다 (`.env.example` 복사해서 사용)
```
DATABASE_URL=postgresql+psycopg://foryourfarm:foryourfarm@localhost:5432/foryourfarm
LLM_BASE_URL=http://localhost:11434   # GCP는 infra/ollama-vm 참고해 내부 IP로 교체
LLM_MODEL=exaone3.5:7.8b
WEATHER_API_KEY=   # 기상청 — 발급 전까지 비움
SOIL_API_KEY=      # 흙토람 — 발급 전까지 비움
```

- 비밀값은 절대 커밋하지 않는다. `.env*`는 `.gitignore` 대상(`.env.example`만 예외).
- 프론트 공개값만 `NEXT_PUBLIC_` 접두어(`CLAUDE.md` §9).

---

## 실행

```bash
# 0. DB가 안 떠 있다면 먼저 (PostgreSQL 로컬 구축 참고)
docker compose up -d

# backend (localhost:8000 — 프론트 기본값과 맞춰야 한다)
cd backend
.venv/Scripts/alembic upgrade head        # 최초/스키마 변경 시
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000

# 법정동 마스터(읍면동 + 리 20,275행) — 밭 등록 선택지·토양 조회 키
.venv/Scripts/python ../scripts/load_districts.py

# frontend (localhost:3000)
cd frontend
npm run dev
```

- 셸에 따라 `source .venv/bin/activate` 후 `alembic`/`uvicorn`을 바로 써도 된다.
- 마스터 데이터(지역/작물/생육지침/토양변화계수) 시드는 `DB.md` §9 참고(아직 미적재).

---

## 로컬 LLM · 챗봇(RAG) 준비

챗봇/행동추천은 로컬 Ollama로 구동한다. 모델이 **두 개**(생성 + 검색 임베딩) 필요하다.

```bash
# 1. Ollama 설치(https://ollama.com) 후 모델 받기
ollama pull exaone3.5:7.8b   # 생성(답변) — 모델 선택 근거: docs/llm-benchmark-eval.md
ollama pull bge-m3           # 검색 임베딩(1024차원) — 챗봇 RAG 필수

# 2. Ollama 서버(11434) 확인
curl http://localhost:11434/api/tags

# 3. 챗봇 검색 근거(knowledge_chunk) 채우기 — `alembic upgrade head` 이후 1회
backend/.venv/Scripts/python.exe scripts/embed_corpus.py   # 5작물 청크 임베딩·적재(재실행 안전, diff 동기화)
```

- 두 모델은 코드에서 `keep_alive:-1`로 VRAM에 상주시킨다(재로딩이 응답 예산 초과). `EMBEDDING_MODEL`은 루트 `.env.example` 참고.
- 챗봇 엔드포인트: `POST /api/v1/chat` (SSE 스트리밍, `ApiResponse` 래퍼 미사용). 상세 설계는 [`docs/llm-integration.md`](./docs/llm-integration.md).
- **Ollama/모델·임베딩 데이터가 없어도 백엔드는 뜬다** — 챗봇 호출만 규칙 기반 폴백 문구로 응답하고 서비스는 죽지 않는다(`CLAUDE.md` §13, §18-5).

---

## Build / Deploy

GCP Cloud Run 기준. 백엔드·프론트 모두 컨테이너로 빌드해 배포한다.

**순서가 중요하다.** 아래 ①②를 건너뛰고 배포하면 밭 등록이 FK 위반으로 깨지고,
④를 건너뛰면 프론트가 백엔드를 못 찾는다. 이유는 각 단계에 적어뒀다.

### ① DB 스키마 최신화

```bash
cloud-sql-proxy <PROJECT_ID>:<REGION>:<INSTANCE> --port 5432 &
cd backend && .venv/Scripts/alembic upgrade head
```

### ② 법정동 마스터 적재 — **백엔드 배포보다 먼저**

```bash
.venv/Scripts/python ../scripts/load_districts.py   # 20,275행(읍면동 5,066 + 리 15,209)
```

`user_farm.bjd_code`가 `district`를 FK로 건다. 리 행이 없는 상태로 백엔드가 뜨면
유저가 리를 고르는 순간 등록이 실패한다. 멱등(upsert)이라 여러 번 돌려도 안전하다.

### ③ 백엔드 빌드·배포

```bash
# 리포 루트에서. cd backend 하면 안 된다 — 컨텍스트가 루트여야 docs/seed/가 이미지에 들어간다
gcloud builds submit --config cloudbuild.yaml .
gcloud run deploy foryourfarm-backend \
  --image gcr.io/<PROJECT_ID>/foryourfarm-backend \
  --add-cloudsql-instances <PROJECT_ID>:<REGION>:<INSTANCE> \
  --set-env-vars DATABASE_URL=...,LLM_BASE_URL=...,WEATHER_API_KEY=...,SOIL_API_KEY=...
```

`--tag` 방식은 쓸 수 없다. 그건 컨텍스트 루트의 `Dockerfile`만 찾는데 우리 것은
`backend/Dockerfile`이고 컨텍스트는 리포 루트여야 한다(`backend/Dockerfile` 주석 참고).
그 조합을 만들려고 `cloudbuild.yaml`을 둔다.

배포된 백엔드 URL을 받아둔다 — 다음 단계에서 쓴다.

```bash
gcloud run services describe foryourfarm-backend --format='value(status.url)'
```

### ④ 프론트 빌드·배포 — 백엔드 URL을 **빌드 시점에** 넣는다

```bash
gcloud builds submit --config cloudbuild.frontend.yaml \
  --substitutions=_API_BASE=https://foryourfarm-backend-xxxx.run.app frontend
gcloud run deploy foryourfarm-frontend \
  --image gcr.io/<PROJECT_ID>/foryourfarm-frontend
```

`NEXT_PUBLIC_*`은 `next build` 때 클라이언트 번들에 굳는다. **`gcloud run deploy
--set-env-vars`로는 못 바꾼다** — 런타임에 주입해도 이미 빌드된 번들은 기본값
(`http://localhost:8000`)을 들고 있어서, 배포는 성공하는데 브라우저가 localhost를 부른다.
백엔드 URL이 바뀌면 프론트를 **다시 빌드**해야 한다.

- 배포는 `main` 브랜치 기준으로만 진행한다(아래 [브랜치 전략](#브랜치-전략)).
- 로컬에서 이미지를 확인하려면:
  `docker build -f backend/Dockerfile .` / `docker build -f frontend/Dockerfile frontend`

---

## Cloud SQL 연결

로컬 개발:
```bash
cloud-sql-proxy <PROJECT_ID>:<REGION>:<INSTANCE> --port 5432
```

Cloud Run 배포 시에는 `--add-cloudsql-instances`로 연결하며, `DATABASE_URL`은 Unix 소켓 경로(`postgresql+psycopg://USER:PW@/foryourfarm?host=/cloudsql/<INSTANCE_CONNECTION_NAME>`) 형식을 사용한다.

---

## 개발 규칙

코딩 컨벤션, API/DB/보안/성능 규칙, 절대 금지사항 등은 전부 [`CLAUDE.md`](./CLAUDE.md)에 정리되어 있다. PR 올리기 전 반드시 확인.

---

## 브랜치 전략

- `main`: **배포 전용**. 여기로 직접 작업하거나 머지하지 않는다.
- `dev`: **통합 및 실전 테스트 브랜치**. 모든 기능 개발·테스트가 여기로 모인다.
- `feature/<scope>-<요약>`, `fix/<요약>`, `docs/<요약>` → `dev`에서 분기, `dev`로 PR.
- `dev → main` 승격은 충분히 검증된 뒤 별도로 진행(일반 기능 PR의 대상 아님).

---

## 기여 방법

1. `dev`에서 `feature/<scope>-<요약>` 브랜치 생성.
2. 커밋은 [Conventional Commits](https://www.conventionalcommits.org/) 형식(`CLAUDE.md` §14).
3. PR은 항상 **`dev`를 대상**으로 오픈.
4. PR 전 [`CLAUDE.md`](./CLAUDE.md) QA 체크리스트·코드 리뷰 체크리스트 셀프 점검.
5. 리뷰 1인 이상 승인 후 머지.
