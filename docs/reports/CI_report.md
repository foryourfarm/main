# CI 도입 계획 보고서

> **상태: 완료** — 2026-07-29 계획, 2026-07-30 도입(PR #56, `27195b3`·`9638a36`).
> 계획 시점 문서를 그대로 보존한다. 남은 후속(§8)은 `nexttodo.md`로 옮겼다.

---

## 1. 왜 하는가

### 문제

테스트 실행이 **사람의 성실성에 의존**하고 있다.

`.github/workflows/` 디렉터리 자체가 없다. 백엔드 테스트 237개(2,620 LOC)가 존재하지만
**누가 기억하고 손으로 돌릴 때만** 실행된다.

실제 사례 — PR #52 본문:

> 백엔드 pytest (23파일) — 237 passed + 2117 subtests

이 수치는 작성자가 자기 로컬에서 돌리고 손으로 적은 것이다. 검증할 방법이 없었고,
오늘 필자가 수동으로 재실행해서야 사실임이 확인됐다. 여기서 나오는 문제 셋:

| 질문 | 현재 답 |
|---|---|
| 작성자가 안 돌리고 표만 적었다면? | 알 방법 없음 |
| 작성자 로컬에서만 통과하는 거라면? | 알 방법 없음 (로컬 3.14 / 배포 3.13로 실제 다름) |
| 다음 PR은 누가 확인하나? | 미정 — 기억하는 사람이 하면 함 |

성실성은 마감이 다가올 때 가장 먼저 무너지는 자원이다. CI는 이걸 **구조**로 바꾼다.

### 왜 지금이 적기인가

CI의 가치는 **테스트가 이미 있을 때** 나온다. 테스트가 없으면 CI를 붙여도 검사할 게 없다.

우리는 이미 2,620줄의 테스트를 갖고 있다. 자산은 다 만들어놨는데 자동으로 안 도는 상태다.
**약 60줄짜리 파일 하나로 그 2,620줄이 상시 자산으로 바뀐다.** 투입 대비 회수가 가장 큰 작업이다.

부수 효과로 해커톤 배점의 **운영 가능성 25점**에 그대로 제시할 수 있는 항목이기도 하다.

---

## 2. 사전 조사 결과 (실측)

설계 결정의 근거가 된 확인 사항이다. 전부 추측이 아니라 실행해서 얻었다.

| # | 확인 항목 | 결과 | 설계에 미친 영향 |
|---|---|---|---|
| 1 | `.github/workflows/` 존재 | **없음** | 신규 생성 |
| 2 | 백엔드 테스트가 DB를 요구하는가 | **아니오** — 237개 전부 DB 없이 통과 (2.4초) | Postgres 컨테이너 불필요 |
| 3 | `.env` 없이 앱이 import 되는가 | **예** — `Settings(_env_file=None)` 로드 성공, 전 필드 기본값 보유 | **CI에 시크릿 0개** |
| 4 | 배포 Python 버전 | `backend/Dockerfile` → `python:3.13-slim` (로컬은 3.14) | CI를 3.13으로 고정 |
| 5 | `backend/`에 pytest 설정 파일 | `conftest.py`·`pytest.ini`·`pyproject.toml` **전부 없음** | `working-directory: backend` 필수 |
| 6 | 리포 루트에서 pytest 실행 | **실패** — 23 collection errors / `No module named 'app'` | 위 항목의 실증 |
| 7 | `requirements.txt`에 pytest | **없음** (런타임 의존성만) | `requirements-dev.txt` 신규 필요 |
| 8 | subTest에 플러그인 필요한가 | **아니오** — stdlib `unittest.subTest`, pytest가 기본 집계 | 추가 의존성 없음 |
| 9 | 프론트 패키지 매니저 | npm + `package-lock.json` 존재 | `npm ci` 사용 가능 |
| 10 | 프론트에 lint/typecheck 스크립트 | **없음** (`dev`/`build`/`start`만) | `npx tsc --noEmit` 직접 호출 |
| 11 | 빌드에 환경변수가 필요한가 | **아니오** — `lib/auth.ts:6`·`lib/chat.ts:7`이 `?? "http://localhost:8000"` 폴백 | CI에 env 주입 불필요 |

**핵심 결론**: 이 프로젝트는 CI를 붙이기에 조건이 매우 좋다. **시크릿도, DB도, 환경변수도 필요 없다.**
그만큼 워크플로가 단순해지고 유출 경로도 생기지 않는다.

---

## 3. 설계 결정과 근거

YAML 문법은 검색하면 나온다. 프로젝트마다 달라지는 건 **왜 이 값인가**이므로 그것만 기록한다.

### D1. 트리거 — `pull_request` + **제한적** `push`

```yaml
on:
  pull_request:
    branches: [dev, main]
  push:
    branches: [dev, main]
```

`push`를 조건 없이 걸면 feature 브랜치 푸시마다 **PR 검사와 중복으로 2회** 돈다.
시간과 무료 사용량이 절반씩 낭비되는 흔한 실수다.

현 설정의 동작:

| 상황 | 실행 횟수 |
|---|---|
| feature 브랜치 푸시 | PR 검사 1회 |
| `dev`로 머지 | 머지 결과물 1회 |

겹치지 않으면서 필요한 지점만 덮는다.

base를 `dev`로 두는 것은 `CLAUDE.md §14`(PR 대상은 항상 `dev`, `main`은 배포 전용) 반영이다.

### D2. Job을 backend / frontend 둘로 분리

- **병렬 실행** — 가상머신 2대가 동시에 돈다. 합치면 순차 대기가 생긴다.
- **실패 지점 가시화** — PR 화면에 `backend ✅ / frontend ❌`로 분리 표시된다.
  하나로 묶으면 "CI 실패"만 뜨고 로그를 열어야 안다.

### D3. Python **3.13** (로컬 3.14 아님)

로컬 venv는 3.14, 배포는 `python:3.13-slim`이다.

> **CI는 개발 환경이 아니라 배포 환경을 흉내내야 한다.**

3.14에서만 통과하고 3.13에서 깨지는 코드를 CI가 통과시키면 CI가 거짓말을 하는 것이다.
"내 컴퓨터에선 되는데요"는 CI가 잡아야 할 대표 버그 유형이다.

### D4. DB 컨테이너 없음 (조사 #2, #3 근거)

GitHub Actions는 `services:` 문법으로 Postgres를 띄울 수 있다. **쓰지 않는다.**

전 테스트가 DB 없이 통과하고, `config.py`가 `.env` 없이 import되는 것을 확인했다.
그 결과 **CI에 API 키를 하나도 등록하지 않아도 된다** — 시크릿 관리 부담과 유출 경로가 아예 없다.

**한계는 §6에 명시한다.**

### D5. `working-directory: backend` (필수, 조사 #5·#6)

`backend/`에 pytest 설정 파일이 없어 작업 디렉터리가 곧 import 경로다.
이 암묵적 규칙을 명시하지 않으면 **첫 실행부터 빨간불**이다.

### D6. `pytest`를 `requirements-dev.txt`로 분리 (조사 #7)

워크플로에 `pip install pytest`를 직접 박을 수도 있으나, 그러면 **필요한 도구가 YAML 안에 숨는다.**
새 팀원이 로컬 환경을 만들 때 알 방법이 없다. 의존성은 의존성 파일에 선언한다.

런타임(`requirements.txt`)과 분리하는 이유는 배포 이미지에 테스트 도구가 들어가면
이미지가 커지고 공격면도 넓어지기 때문이다.

### D7. 의존성 캐시

`setup-python`/`setup-node`에 내장된 캐시를 한 줄로 켠다. 락파일이 안 바뀌면 재사용, 바뀌면 자동 갱신.

**함정 주의**: `working-directory`는 `run:`에만 적용된다. action 입력인
`cache-dependency-path`는 **리포 루트 기준**이라 `backend/`를 붙여야 한다.

### D8. `npm ci` (`npm install` 아님)

| | 동작 | CI 적합성 |
|---|---|---|
| `npm install` | 락파일을 **수정할 수도** 있음 | ❌ 실행마다 다른 버전 가능 |
| `npm ci` | 락파일 **그대로** 설치, 어긋나면 실패 | ✅ 재현 가능 |

`ci`는 clean install의 약자로 정확히 이 용도의 명령이다. `package-lock.json` 존재를 확인했다(조사 #9).

### D9. 부가 설정 2개

```yaml
permissions:
  contents: read          # 최소 권한 — 이 워크플로는 읽기만 하면 된다 (§17)

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true   # 새 커밋 오면 낡은 실행 취소 — 사용량 절약
```

---

## 4. 만들 파일

### 4-1. `.github/workflows/ci.yml` (신규, 약 60줄)

**구조**

```
Event: PR(→dev,main) 또는 push(dev,main)
├─ Job: backend   (ubuntu, working-directory: backend)
│   ├─ checkout
│   ├─ setup-python 3.13 (+pip 캐시)
│   ├─ pip install -r requirements.txt -r requirements-dev.txt
│   └─ pytest tests -q
└─ Job: frontend  (ubuntu, working-directory: frontend)   ※ backend와 병렬
    ├─ checkout
    ├─ setup-node 22 (+npm 캐시)
    ├─ npm ci
    ├─ npx tsc --noEmit
    └─ npm run build
```

`tsc --noEmit`과 `build`를 **둘 다** 두는 이유: 타입 검사는 빠르고 strict 위반을 먼저 잡고,
빌드는 tsc가 못 보는 것(RSC/CSR 경계 위반, 라우트 규약 오류)을 잡는다. 성격이 다르다.

### 4-2. `backend/requirements-dev.txt` (신규, 1줄 + 주석)

```
pytest>=9.1
```

---

## 5. 검증 계획

**푸시 전 로컬에서 동일 명령을 먼저 돌린다.** 첫 CI 실행이 빨간불이면 팀의 신뢰를 잃는다.

| # | 검증 | 방법 | 통과 기준 |
|---|---|---|---|
| 1 | 백엔드 테스트 | `cd backend && pytest tests -q` | 237 passed (이미 확인됨) |
| 2 | 프론트 타입 검사 | `cd frontend && npx tsc --noEmit` | exit 0 |
| 3 | 프론트 빌드 | `cd frontend && npm run build` | exit 0 |
| 4 | YAML 문법 | 푸시 후 Actions 탭에서 워크플로 인식 여부 | 파싱 오류 없음 |
| 5 | 실제 동작 | PR 생성 → 두 Job 초록 확인 | backend ✅ / frontend ✅ |
| 6 | **실패 감지력** | 일부러 테스트 하나를 깨서 빨간불 확인 후 되돌림 | ❌가 떠야 함 |

**6번이 중요하다.** 초록불만 확인하면 "CI가 아무것도 안 하고 통과시키는" 상태를
구분할 수 없다. 실패를 실제로 잡는지 한 번은 봐야 한다.

⚠️ 2·3번은 아직 실행하지 않았다. **로컬 빌드가 깨져 있을 가능성이 남아 있다** —
PR #52는 `tsc --noEmit` exit 0을 주장했지만 `npm run build`는 이 세션에서 아무도 안 돌렸다.

---

## 6. 이 CI가 검사하지 **않는** 것 (한계 명시)

숨기지 않고 적는다. CI가 초록이어도 아래는 여전히 수동이다.

| 미검사 항목 | 이유 | 현재 대응 |
|---|---|---|
| 마이그레이션 실 DB 적용 | Postgres를 띄우지 않음 (D4) | `alembic upgrade head` 수동 — 오늘 0020·0021 수동 검증함 |
| 로컬 LLM(Ollama) 연동 | CI에 모델을 띄우지 않음 | 관련 테스트는 전부 스텁 기반 |
| 공공 API 실호출 | 키 없음 + rate limit | 클라이언트 테스트는 응답 고정값 기반 |
| HTTP 엔드포인트 계약 | **테스트 자체가 없음** (TestClient 0건) | 2순위 과제 — 별도 작업 |
| E2E / 브라우저 | 범위 밖 | 없음 |

**즉 이 CI는 "서비스 계층 로직의 회귀"를 막는다.** 배선·인프라는 여전히 사람이 본다.
그것만으로도 지금의 0보다 크게 낫지만, 만능이 아니라는 점을 팀이 알아야 한다.

---

## 7. 예상 리스크

| 리스크 | 가능성 | 대응 |
|---|---|---|
| 첫 실행부터 실패 | 중 | §5의 2·3번을 푸시 전 실행 |
| `requirements.txt`가 `>=`만 써서 상류 릴리스로 갑자기 빨간불 | 중 | 인지만 하고 이번엔 미대응 (§8-3) |
| Python 3.13에서만 나는 문제 발견 | 중 | 발견되면 그게 CI의 성과다 — 고치면 됨 |
| Next 16 빌드가 CI 메모리 초과 | 낮 | 발생 시 `NODE_OPTIONS` 조정 |
| 무료 사용량 초과 | 매우 낮 | 공개 저장소는 무제한. concurrency로 낭비도 차단 |

---

## 8. 다음 단계 (이번 범위 밖)

순서대로 가치가 크다.

1. **브랜치 보호 규칙** — CI를 만들어도 **빨간불인 PR을 머지할 수 있다.**
   GitHub Settings → Branches에서 `dev`에 "Require status checks to pass"를 걸어야
   비로소 강제력이 생긴다. **저장소 관리자 권한이 필요해 필자가 못 한다 — 팀에 요청 필요.**
2. **HTTP 엔드포인트 테스트** (백엔드 2순위 과제) — 붙이면 CI가 자동으로 함께 돌린다.
3. **의존성 버전 고정** — `requirements.txt`가 전부 `>=`라 상류가 새 버전을 내면
   코드를 안 바꿔도 CI가 깨질 수 있다. `pip-tools`로 락파일 생성이 정석.
4. **마이그레이션 검증 Job** — `services:`로 Postgres를 띄워 `alembic upgrade head` + `downgrade` 왕복.
   오늘 수동으로 한 검증을 자동화하는 것.
5. **ruff 린트 추가** — 현재 로컬 venv에 ruff가 설치돼 있지도 않다(`CLAUDE.md §4`는 권장 중).

---

## 9. 승인 요청

- [ ] §3 설계 결정 9개에 이견 없는가
- [ ] §6 한계(특히 마이그레이션·엔드포인트 미검사)를 팀이 수용하는가
- [ ] §8-1 브랜치 보호 규칙을 **누가** 설정할 것인가
- [ ] 진행 브랜치명: `chore/github-actions-ci` — PR 대상 `dev` (§14)

승인되면 §5 검증 → 커밋 → PR 순으로 진행한다.
