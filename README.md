# 🌾 For Your Farm

귀농 사전 시뮬레이션 게임 — 실제 공공데이터(토양·기상) 기반으로, 재배를 시작하기 전에 시행착오를 미리 경험하는 턴제 관리 시뮬레이션.

> "박제된 매뉴얼이 아니라, 내 땅과 날씨에 맞는 맞춤형 예방 가이드."
> 전국 표준 재배 지침만으로는 정착지 고유의 토양·기후 차이를 알 수 없다. 재배 희망 지역과 작물을 고르면 실제 데이터로 적합도를 분석하고, 위험 요소를 게임처럼 미리 보여준다.

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

| Lobby (탑뷰) | 밭 상세 (라디얼 UI) | 결과 리포트 |
|---|---|---|
| _(스크린샷 자리)_ | _(스크린샷 자리)_ | _(스크린샷 자리)_ |

---

## 기술 스택

**대상 작물 (5종 고정)**: 사과, 배, 오이, 감자, 상추

| 영역 | 스택 |
|---|---|
| Frontend | Next.js (App Router), TypeScript, React |
| Backend | Spring Boot, Spring Data JPA, Java |
| Database | PostgreSQL (GCP Cloud SQL) |
| Infra | GCP Cloud Run |
| AI | 로컬 LLM (멘토링 리포트 생성) |
| 외부 데이터 | 농진청 흙토람(토양), 기상청(기상) — 실시간 호출 아님, 사전 배치 적재 |

자세한 코딩 규칙은 [`CLAUDE.md`](./CLAUDE.md), 제품 명세는 [`PRD.md`](./PRD.md), DB 설계는 [`DB.md`](./DB.md) 참고.

---

## 아키텍처

```
                    ┌──────────────────────┐
                    │   Frontend (Next.js) │
                    │  탑뷰 UI · 라디얼 UI  │
                    │  도트 스프라이트 렌더  │
                    └──────────┬───────────┘
                               │ REST API
                    ┌──────────▼───────────┐
                    │  Backend (Spring Boot)│
                    │  ─ 적합도 룰 엔진      │
                    │  ─ 위험신호 판정       │
                    │  ─ 로컬 LLM 프롬프트   │
                    │  ─ 인증/인가          │
                    └──────────┬───────────┘
                               │ JPA
                    ┌──────────▼───────────┐
                    │ PostgreSQL (Cloud SQL)│
                    │ 마스터: 지역/작물/생육 │
                    │ 지침/토양/작년 기상   │
                    │ 유저: 계정/세이브/밭  │
                    └───────────────────────┘
                               ▲
                     배치(사전 적재, 실시간 아님)
                    ┌──────────┴───────────┐
                    │ 흙토람 / 기상청 원본  │
                    └───────────────────────┘
```

- 클라이언트는 DB에 직접 접속하지 않는다. 모든 접근은 Spring Boot를 경유.
- 공공데이터는 유저 요청 시점에 호출하지 않고 배치로 미리 적재한다(작년 1년치 기상 CSV, 시/군 토양).
- 게임의 "주간 위험신호"는 실시간 예보가 아니라 **평년(작년 동일 주차) 데이터** 기반 — 클릭으로 여러 주가 즉시 진행되는 게임 구조상 실시간 예보 연동이 불가능하기 때문(자세한 이유는 `PRD.md` §9).

---

## 폴더 구조

```
foryourfarm/
├── CLAUDE.md            # 개발 헌법 (컨벤션, 협업 규칙, 금지사항)
├── PRD.md               # 제품 요구사항 명세
├── DB.md                # DB 설계
├── README.md            # 본 문서
├── docs/
│   └── seed/            # 생육 지침 시드 (작물별 JSON/YAML)
├── frontend/            # Next.js (App Router)
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── hooks/
│   ├── types/
│   └── public/assets/   # 도트 스프라이트, 사운드
└── backend/             # Spring Boot (Gradle)
    ├── build.gradle
    ├── src/main/java/com/foryourfarm/backend/
    │   ├── BackendApplication.java
    │   ├── domain/      # Entity, 도메인 로직 (예: region/)
    │   ├── application/ # Service (유스케이스)
    │   ├── api/         # Controller, DTO, ApiResponse, 예외 핸들러
    │   ├── infra/       # 공공 API 클라이언트, 배치, JPA Repository
    │   └── config/      # SecurityConfig 등
    ├── src/main/resources/
    │   ├── application.yml
    │   └── db/migration/  # Flyway (V1__init_schema.sql)
    └── src/test/java/...
```

---

## 설치

**요구 사항**
- Node.js 20+
- Java 21+, Gradle (또는 Maven)
- Docker Desktop (로컬 PostgreSQL 구동용)
- 로컬 LLM 런타임 (모델 확정 후 갱신 예정)

```bash
git clone <repo-url>
cd foryourfarm

# frontend
cd frontend
npm install

# backend — Gradle 설치 없이 wrapper가 알아서 내려받아 실행한다
cd ../backend
./gradlew build
```

- Gradle Wrapper는 **9.6.1**로 고정되어 있다(팀원 로컬 Java 버전이 24처럼 최신이어도 Gradle 8.x는 구버전 JDK를 못 읽어서 깨진다 — 9.x부터 해결됨). 프로젝트 코드 자체는 Java 21 툴체인으로 컴파일되니(`build.gradle`의 `languageVersion`), Gradle을 돌리는 JDK와 코드가 타깃하는 JDK는 별개라고 생각하면 된다.

---

## PostgreSQL 로컬 구축

Postgre를 따로 설치할 필요 없이 Docker로 띄운다. 팀원 전부 동일한 방법으로 구축한다.

```bash
# 1. 레포 루트에서 컨테이너 실행 (최초 1회, 이후엔 docker compose up -d 만 반복)
docker compose up -d

# 2. 떠 있는지 확인
docker ps   # foryourfarm-db 가 보이면 정상
```

- 접속 정보: `host=localhost` `port=5432` `db=foryourfarm` `user=foryourfarm` `password=foryourfarm` — [환경 변수](#환경-변수)의 `DB_URL`/`DB_USERNAME`/`DB_PASSWORD` 기본값과 동일하게 맞춰뒀다.
- **스키마는 수동으로 적용할 필요 없음.** `backend/src/main/resources/db/migration/V1__init_schema.sql`을 Flyway가 관리하며, `./gradlew bootRun`으로 backend를 처음 띄우는 순간 자동으로 적용된다.
- 스키마·컬럼의 의미는 [`DB.md`](./DB.md)에 전부 설명되어 있다. 실제 데이터(작물/지역/생육지침/토양/작년기상)는 아직 안 채워져 있으니, 시드 작업은 `DB.md` §9 참고.
- 컨테이너를 완전히 밀고 새로 시작하고 싶으면: `docker compose down -v` (볼륨까지 삭제, 데이터 날아감 — 로컬 개발 DB에서만).

---

## 환경 변수

**frontend/.env.local**
```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8080/api/v1
```

**backend/.env** (또는 `application-local.yml`)
```
DB_URL=jdbc:postgresql://localhost:5432/foryourfarm
DB_USERNAME=foryourfarm
DB_PASSWORD=foryourfarm
JWT_SECRET=
SOIL_API_KEY=        # 흙토람 등 — 발급 전까지 비워둠 (배치 스크립트만 사용)
WEATHER_API_KEY=      # 기상청 — 배치 스크립트만 사용
LOCAL_LLM_MODEL_PATH=
```

- 비밀값은 절대 커밋하지 않는다. `.env*`는 `.gitignore` 대상.
- 공개해도 되는 값만 `NEXT_PUBLIC_` 접두어(`CLAUDE.md` §9).

---

## 실행

```bash
# 0. DB가 안 떠 있다면 먼저 (PostgreSQL 로컬 구축 참고)
docker compose up -d

# backend (localhost:8080)
cd backend
./gradlew bootRun

# frontend (localhost:3000)
cd frontend
npm run dev
```

- 최초 실행 전 `docs/seed/`의 생육 지침·지역·작년 기상 데이터를 마이그레이션으로 적재해야 정상 동작한다(`DB.md` §9).

---

## Build

```bash
# frontend
cd frontend
npm run build

# backend
cd backend
./gradlew build
```

---

## Deploy

GCP Cloud Run 기준.

```bash
# backend 이미지 빌드 & 배포
cd backend
gcloud builds submit --tag gcr.io/<PROJECT_ID>/foryourfarm-backend
gcloud run deploy foryourfarm-backend \
  --image gcr.io/<PROJECT_ID>/foryourfarm-backend \
  --add-cloudsql-instances <PROJECT_ID>:<REGION>:<INSTANCE> \
  --set-env-vars DB_URL=...,JWT_SECRET=...

# frontend
cd frontend
gcloud builds submit --tag gcr.io/<PROJECT_ID>/foryourfarm-frontend
gcloud run deploy foryourfarm-frontend \
  --image gcr.io/<PROJECT_ID>/foryourfarm-frontend \
  --set-env-vars NEXT_PUBLIC_API_BASE_URL=...
```

- 배포는 `main` 브랜치 기준으로만 진행한다(아래 [브랜치 전략](#브랜치-전략)).

---

## Cloud SQL 연결

로컬 개발:
```bash
cloud-sql-proxy <PROJECT_ID>:<REGION>:<INSTANCE> --port 5432
```

Cloud Run 배포 시에는 `--add-cloudsql-instances`로 연결하며, Spring Boot의 `DB_URL`은 Unix 소켓 경로(`/cloudsql/<INSTANCE_CONNECTION_NAME>`) 형식을 사용한다.

---

## 개발 규칙

코딩 컨벤션, API/JPA/보안/성능 규칙, 절대 금지사항 등은 전부 [`CLAUDE.md`](./CLAUDE.md)에 정리되어 있다. PR 올리기 전 반드시 확인.

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
