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
- [Build / Deploy](#build--deploy)
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

GCP Cloud Run 기준. **Cloud Shell에서 손으로 진행한다** — 아래 순서를 그대로 따른다.

이 절차는 2026-08-01 실제 배포로 검증했다. 스크립트로 감싸지 않는 이유는 §맨 아래 참고.

**순서가 중요하다.** ④를 건너뛰면 밭 등록이 FK 위반으로 깨지고, ⑥을 건너뛰면 프론트가
백엔드를 못 찾는다. 둘 다 **배포 시점엔 성공한 것처럼 보인다.**

### ① 리포 준비

```bash
gh auth login && gh repo clone foryourfarm/main foryourfarm -- -b dev --depth 1 && cd foryourfarm
python3 -m venv backend/.venv && backend/.venv/bin/pip install -q -r backend/requirements.txt
```

### ② Cloud SQL 프록시 — **unix 소켓으로** (별도 탭, 켜둔 채로)

```bash
export CONN=$(gcloud sql instances list --format='value(connectionName)' | head -1)
curl -LO https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.14.3/cloud-sql-proxy.linux.amd64
mv cloud-sql-proxy.linux.amd64 ~/cloud-sql-proxy && chmod +x ~/cloud-sql-proxy
sudo mkdir -p /cloudsql && sudo chown $USER /cloudsql
~/cloud-sql-proxy --unix-socket /cloudsql "$CONN"
```

TCP(`--port 5432`)가 아니라 **소켓**이어야 한다. Cloud Run이 쓰는 `DATABASE_URL`이
`?host=/cloudsql/<CONN>` 형식이라, 프록시를 같은 경로에 띄우면 **하나의 값이 로컬 DB 단계와
Cloud Run 양쪽에 그대로 맞는다.** TCP로 띄우면 URL을 두 벌 관리해야 한다.

`Listening on /cloudsql/...` + `ready for new connections!`가 뜨면 그 탭은 그대로 둔다.

> 다운로드가 33MB다. `curl -s`로 받으면 진행률이 안 보여서 멈춘 것처럼 착각한다.
> 중간에 끊겼으면 `curl -L -C -`로 이어받는다(파일 크기가 33MB 미만이면 잘린 것).

### ③ 접속 정보 — 비밀번호를 타이핑하지 않는다

```bash
export CONN=foryourfarm-hackathon:asia-northeast3:foryourfarm-db
export DATABASE_URL=$(gcloud run services describe foryourfarm-backend \
  --region asia-northeast3 --format=json \
  | python3 -c "import json,sys; print(next(e['value'] for e in json.load(sys.stdin)['spec']['template']['spec']['containers'][0]['env'] if e['name']=='DATABASE_URL'))")
echo "$DATABASE_URL" | sed -E 's#://[^:]+:[^@]+@#://***:***@#'   # 비번 가린 확인
```

떠 있는 서비스에서 값을 그대로 읽어온다 — 오타가 없고, **엉뚱한 DB에 마이그레이션이 갈
위험이 사라진다.** 마지막 줄이 `?host=/cloudsql/...` 소켓 형식인지 확인한다(②와 맞물린다).

### ④ 스키마 + 시드 — **백엔드 배포보다 먼저**

```bash
(cd backend && .venv/bin/python -m alembic upgrade head)
backend/.venv/bin/python scripts/load_districts.py   # 20,275행(읍면동 5,066 + 리 15,209)
backend/.venv/bin/python scripts/audit_seeds.py      # 나머지 시드가 비었는지 먼저 센다
```

`audit_seeds.py`는 **테이블 행수와 컬럼 값 유무를 같이 센다.** 행수만으로는 부족하다 —
`weather_climatology`가 3,060행 있어도 `temp_night_min_normal`이 전 행 NULL이면 그 지표는
채점되지 않는데 행수 검사로는 "OK"로 보인다(2026-08-03에 실제로 그랬다). 컬럼이 전 행
NULL이면 **어느 스크립트를 돌려야 하는지까지 출력**한다.

`user_farm.bjd_code`가 `district`를 FK로 건다. 리 행이 없는 상태로 백엔드가 뜨면
유저가 리를 고르는 순간 등록이 실패한다. 멱등(upsert)이라 여러 번 돌려도 안전하다.
**20,275행이 아니라 5,066행이 나오면 리 시드가 빠진 것이므로 멈춘다.**

**법정동만 넣으면 안 된다.** 나머지 시드는 없어도 예외가 나지 않고 "데이터 부족"·"보정 없음"으로
조용히 degrade하도록 설계돼 있어서(§12, §18-5) **증상이 화면에 뜰 때까지 모른다.** 실제로
2026-08-01 배포에서 3개월전망이 비어 있는 걸 장기 탭 한계 문구를 읽고서야 알았다.
`audit_seeds.py`가 비었다고 표시한 것만 골라 돌린다:

| 스크립트 | 주기 | 비었을 때 증상 |
|---|---|---|
| `load_weather_outlook.py` | **매월**(23일 전후 발표) — 스케줄러가 자동으로 돈다, `docs/outlook-scheduler.md` | 장기 탭에 "3개월전망이 적재되지 않아 보정 없이 평년치만 사용" |
| `load_region_grid.py` | 1회(256행 고정) | 단기 탭 전멸 + 평년치 KNN 거리계산 불가 |
| `load_weather_climatology.py` | 소스 CSV 바뀔 때 | 장기 탭 12칸 "데이터 부족" |
| `load_altitudes.py` | 1회(구역 256 / 법정동 20,275) | 기온 감률 보정(0.65℃/100m)이 전부 미적용. **아래 AWS보다 먼저** — AWS가 고도 필터(±100m)를 쓴다 |
| `load_aws_climatology.py` | 1회 | **야간 최저기온이 전 행 NULL** — 문제정의서가 지목한 A씨 실패 원인을 채점 못 한다. 평년치 커버리지도 116/256에 머문다 |
| `load_observation_points.py` | 1회(752행) | 관측지점 폴백 경로 없음 |
| `load_solar_radiation_normal.py` | 1회 | 일조 지표가 계속 빈다 |
| `embed_corpus.py` | 코퍼스 바뀔 때 | 챗봇 근거 0건 → 전부 "확실치 않음" 폴백. **Ollama가 떠 있어야 한다** |

> **⚠️ `load_altitudes.py`·`load_aws_climatology.py`는 2026-08-03까지 이 표에 없었다.**
> 그래서 아무도 안 돌렸고, 프로덕션은 **야간 최저기온이 0행**인 채로 운영됐다 — 제품의
> 핵심 차별점(A씨 실패 원인 = 봄철 야간 저온)이 한 번도 채점된 적이 없었다. 같은 이유로
> 고도도 0행이라 감률 보정이 통째로 죽어 있었다. `done.md`는 "0행 → 1,668행"을 완료로
> 적어놨는데 그건 로컬/dev 얘기였다. **표에 없으면 아무도 돌리지 않는다** — 새 ETL을
> 만들면 여기부터 추가할 것.

`load_aws_climatology.py`는 처음 실행 시 기상청 API에서 약 180콜(요소 3종 × 60개월,
약 383MB)을 받아 `data/aws_daily_cache/`에 캐시한다. 몇 분 걸리고 중간에 끊겨도 재실행하면
이어받는다. 캐시는 리포에 커밋하지 않는다(용량). `--dry-run`으로 집계만 먼저 볼 수 있다.

`load_weather_outlook.py`만 주기적이다 — 매월 발표를 안 받으면 **에러 없이 조용히** 낡은
예보로 남는다. 그래서 Cloud Scheduler가 매일 `POST /api/v1/admin/weather-outlooks`를
불러 자동 갱신한다. **신규 프로젝트/신규 백엔드 서비스에는 그 스케줄러와
`ADMIN_TASK_TOKEN`을 한 번 세팅해야 한다** — `docs/outlook-scheduler.md`.

### ⑤ 백엔드 빌드·배포 — **env 플래그를 붙이지 않는다**

```bash
gcloud builds submit --config cloudbuild.yaml --project <PROJECT_ID> .
gcloud run deploy foryourfarm-backend \
  --image gcr.io/<PROJECT_ID>/foryourfarm-backend \
  --project <PROJECT_ID> --region asia-northeast3
```

`--set-env-vars`를 쓰면 **기존 환경변수 전체가 교체된다.** 서비스에 이미 들어 있는
`JWT_SECRET`·`CORS_ORIGINS`·`LLM_BASE_URL`·공공 API 키 7종이 전부 삭제되고, 그러면
CORS가 `localhost:3000`으로 돌아가 **프론트의 모든 요청이 차단**되고 토양 API는 401이 된다.
갱신 배포에서는 env 플래그를 **아무것도 붙이지 않는 것이 정답**이다 — 이미지만 바꾸면
나머지 설정은 그대로 유지된다. `--add-cloudsql-instances`도 이미 붙어 있어 다시 줄 필요 없다.

일부만 바꿔야 하면 `--set-env-vars`가 아니라 `--update-env-vars`를 쓴다(지정한 것만 덮어씀).

#### ⑤-b 카카오 로그인 env — **서비스에 없으면 한 번만 넣는다**

`0037`로 카카오 로그인이 들어왔다. 백엔드는 인가코드를 카카오에 교환하므로 세 값이 필요하고,
없으면 콜백이 실패한다. 위 ⑤는 env를 아예 붙이지 않으므로 **이 단계가 따로 있어야 한다.**

```bash
gcloud run services describe foryourfarm-backend --region asia-northeast3 \
  --format='value(spec.template.spec.containers[0].env)' | tr ',' '\n' | grep -i kakao
```

비어 있으면 넣는다(`--update-env-vars` — 지정한 것만 덮으므로 기존 env는 안전하다):

```bash
gcloud run services update foryourfarm-backend --region asia-northeast3 --update-env-vars \
KAKAO_REST_API_KEY=<REST API 키>,KAKAO_CLIENT_SECRET=<client secret>,KAKAO_REDIRECT_URI=https://<프론트URL>/login/kakao
```

`KAKAO_REDIRECT_URI`는 **프론트** 주소다(백엔드가 아니다) — 카카오가 FE 콜백 페이지로
돌려보내고 FE가 인가코드를 백엔드에 POST한다(`docs/auth-security.md` §카카오). 이 값은
카카오 개발자센터의 **Redirect URI 등록값과 문자 단위로 같아야** 한다(끝 슬래시 포함).

`--tag` 방식은 쓸 수 없다. 그건 컨텍스트 루트의 `Dockerfile`만 찾는데 우리 것은
`backend/Dockerfile`이고 컨텍스트는 리포 루트여야 한다(`backend/Dockerfile` 주석 참고).
그 조합을 만들려고 `cloudbuild.yaml`을 둔다.

### ⑥ 프론트 빌드·배포 — 백엔드 URL을 **빌드 시점에** 넣는다

```bash
export BE=$(gcloud run services describe foryourfarm-backend --region asia-northeast3 --format='value(status.url)')
export FE=$(gcloud run services describe foryourfarm-frontend --region asia-northeast3 --format='value(status.url)')
gcloud builds submit --config cloudbuild.frontend.yaml --project <PROJECT_ID> \
  --substitutions=_API_BASE=$BE,_KAKAO_REST_API_KEY=<REST API 키>,_KAKAO_REDIRECT_URI=$FE/login/kakao frontend
gcloud run deploy foryourfarm-frontend \
  --image gcr.io/<PROJECT_ID>/foryourfarm-frontend \
  --project <PROJECT_ID> --region asia-northeast3
```

**카카오 두 값을 빠뜨리면 로그인 버튼이 조용히 사라진다.** `NEXT_PUBLIC_KAKAO_*`도
`NEXT_PUBLIC_API_BASE`와 같이 빌드 시점에 굳는 값인데, 비면 `isKakaoEnabled`가 false가 되어
버튼을 숨긴다(`frontend/lib/kakao.ts` — 눌러도 실패하는 버튼을 보여주지 않는 의도적 동작).
에러가 아니라 **없어짐**이라 배포 로그에는 아무것도 안 남는다. `_KAKAO_REDIRECT_URI`는
⑤-b의 `KAKAO_REDIRECT_URI`와 **같은 값**이어야 한다.

`NEXT_PUBLIC_*`은 `next build` 때 클라이언트 번들에 굳는다. **`gcloud run deploy
--set-env-vars`로는 못 바꾼다** — 런타임에 주입해도 이미 빌드된 번들은 기본값
(`http://localhost:8000`)을 들고 있어서, 배포는 성공하는데 브라우저가 localhost를 부른다.
백엔드 URL이 바뀌면 프론트를 **다시 빌드**해야 한다.

서비스명을 그대로 두면 URL이 안 바뀌므로 `CORS_ORIGINS`를 손댈 필요가 없다.

### ⑦ 배포 확인 — 조용히 깨지는 것들을 짚는다

먼저 시드를 센다(프록시 탭이 아직 떠 있어야 한다):

```bash
backend/.venv/bin/python scripts/audit_seeds.py
```

비어 있거나 부분 적재면 exit 1로 알려준다. 통과하면 브라우저에서 프론트를 열고 콘솔에서:

```js
// (1) 번들에 백엔드 URL이 박혔는가 — localhost가 나오면 ⑥ 실패
[...document.querySelectorAll('script[src]')].map(s=>s.src)
// (2) CORS + 리 단위 데이터가 살아있는가 — 고창군(255)은 189개 전부 리여야 한다
fetch('<백엔드URL>/api/v1/regions/255/districts',{credentials:'include'})
  .then(r=>r.json()).then(d=>console.log(d.data.length, d.data[0].name))
```

화면으로는 **밭 등록에서 리 선택**(예: `고수면 남산리`)과 **장기 탭 12개월**이 뜨는지 본다.
전자는 ④, 후자는 평년치 적재를 검증한다.

- 로컬에서 이미지를 확인하려면:
  `docker build -f backend/Dockerfile .` / `docker build -f frontend/Dockerfile frontend`

### 왜 스크립트로 감싸지 않는가

`scripts/deploy.sh`가 있었지만 지웠다. 첫 배포용으로 짜여 있어 **갱신 배포에서 위험했다** —
`--set-env-vars`로 프로덕션 env를 전부 지우는 경로가 스크립트 안에 박혀 있었고, 그건
성공으로 끝나고 나서야 브라우저에서 발견된다. 손으로 하면 ⑤에서 env 플래그를 아예 안 쓰게 되어
그 위험이 구조적으로 사라진다. 단계 수가 적고(6개) 자주 하지도 않아 자동화 이득이 작다.

> `[확인 필요]` 브랜치 전략(§아래)은 배포를 `main` 기준으로 하라고 되어 있으나, 현재 `main`은
> 초기 커밋 하나뿐이고 실제 배포는 `dev`에서 나갔다. `dev → main` 승격을 먼저 할지, 배포
> 기준을 `dev`로 명문화할지 팀에서 정해야 한다.

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
