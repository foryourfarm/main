# 인증·보안 설계 (FE 연동 계약)

> 상태: **설계 확정 · 구현 예정** (결정일 2026-07-24). 구현이 이 계약을 따라간다.
> 근거: `CLAUDE.md` §9(미들웨어 게이팅) §11(인가) §17(보안). 채택 이유는 커밋 메시지 참조.

## 토큰 모델 — 분리 토큰 JWT

| | access token | refresh token |
|---|---|---|
| 수명 | 짧음 (`config` 기본 30분) | 긺 (`config` 기본 14일) |
| 용도 | 실제 API 인가 | 새 access 발급 전용 |
| 저장(FE) | **메모리** (JS 변수/상태, `localStorage` 금지) | **httpOnly 쿠키** (FE가 직접 못 만짐) |
| 전송 | `Authorization: Bearer <access>` 헤더 | 브라우저가 쿠키 자동 첨부 (`/api/v1/auth/refresh`에만) |
| 쿠키 속성 | — | `HttpOnly; Secure(prod); SameSite=Lax; Path=/api/v1/auth/refresh` |

JWT payload는 서명일 뿐 암호화 아님 → 민감정보 없음(`sub=user_id`, `exp`만).

## 엔드포인트 계약

> 모든 응답은 공통 래퍼(§6): 성공 `{ "success": true, "data": ..., "error": null }`,
> 실패 `{ "success": false, "data": null, "error": { "code": str, "message": str } }`.
> 아래 "data"는 래퍼의 `data` 필드 내용. (스트리밍 챗봇만 래퍼 예외 — §6)

### `POST /api/v1/auth/signup`
- 요청: `{ "email": str, "password": str(8~128), "nickname": str(1~50) }`
- 성공: `201`, `data: { id, email, nickname }`. **토큰 발급 안 함.** → FE는 로그인 화면으로 이동시킨다.
- 실패: `409` `EMAIL_EXISTS`(이메일 중복), `422` `VALIDATION_ERROR`(형식·길이)

### `POST /api/v1/auth/login`
- 요청: `{ "email": str, "password": str }`
- 성공: `200`
  - `data: { access_token: str, user: { id, email, nickname } }` → FE는 `data.access_token`을 **메모리에 저장**
  - 응답 헤더: `Set-Cookie`로 refresh 쿠키 세팅 (FE가 손댈 필요 없음)
- 실패: `401` `INVALID_CREDENTIALS` — 문구 일반화. 어느 필드가 틀렸는지 구분 안 줌(계정 열거 방지).

### `POST /api/v1/auth/refresh`
- 요청: 본문 없음. 브라우저가 refresh 쿠키 자동 첨부.
- 성공: `200`, `data: { access_token: str }` → FE는 메모리의 access 교체
- 실패: `401` `UNAUTHORIZED`(쿠키 없음)/`INVALID_TOKEN`(만료·위조) → FE는 **재로그인 강제**

### `POST /api/v1/auth/logout`
- refresh 쿠키 삭제(`Max-Age=0`). `data: "logged out"`. FE는 메모리 access 폐기.

### `POST /api/v1/auth/kakao` (카카오 로그인, 2026-08-05 추가)
- 요청: `{ "code": str }` — 카카오가 콜백으로 준 **인가코드**. `redirect_uri`는 보내지 않는다(서버 설정값을 쓴다).
- 성공: `200` — **`/login`과 응답이 같다**(`data: { access_token, user, is_new_user }` + refresh 쿠키). FE 토큰 처리 코드를 그대로 재사용한다.
  - `is_new_user`: 이 로그인에서 계정이 **새로 만들어졌나**. 카카오는 로그인이 곧 가입이라 이 값으로 "처음 온 사람"을 구분해 닉네임 화면으로 보낸다(아래 `PATCH /me` 참고). 이메일 로그인은 항상 `false`.
- 실패:
  - `401` `KAKAO_AUTH_FAILED` — 인가코드 만료·재사용·위조. **재시도로 풀린다**(코드는 1회용) → FE는 로그인 화면으로.
  - `502` `UPSTREAM_UNAVAILABLE` — 카카오 장애·네트워크. 유저가 할 게 없다 → "잠시 후 다시" 안내.
  - `503` `KAKAO_NOT_CONFIGURED` — 서버에 카카오 키가 없다(fail closed). 이메일 로그인은 정상 동작.
  - `422` `VALIDATION_ERROR` — `code` 누락·빈 값.
- **가입 절차가 없다**: 처음 로그인하면 서버가 계정을 만든다(`kakao_id` 기준). 두 번째부터는 같은 계정을 재사용한다.
- **카카오 계정은 `user.email`이 `null`이다** — 카카오에서 이메일을 받지 않는다(아래 이유). FE 타입이 `string | null`이어야 한다.

#### 카카오 로그인 FE 흐름 (`frontend/lib/kakao.ts`, `app/login/kakao/page.tsx`)

```
로그인 화면 [카카오로 로그인]
   │ state 생성 → sessionStorage 저장, 인가 URL로 **페이지 이동**
   ↓
kauth.kakao.com 동의 화면
   │ 카카오가 redirect_uri(= FE `/login/kakao`)로 ?code=...&state=... 리다이렉트
   ↓
FE 콜백 페이지
   │ ① state 대조(불일치 → 코드를 서버로 보내지 않는다)
   │ ② POST /api/v1/auth/kakao { code }
   ↓ 성공하면 access를 메모리에 넣고 /dashboard로
```

**리다이렉트를 백엔드가 받지 않는 이유**: access를 메모리에만 두는 정책이라(위 토큰 모델) 서버가
리다이렉트를 받으면 토큰을 FE 메모리로 넘길 길이 없다. 그래서 착지점이 FE다.

**FE가 지켜야 할 것 3개**
1. `state`를 sessionStorage에 넣고 콜백에서 **대조 후 1회용으로 폐기**한다(CSRF). 서버 세션이 없어 브라우저에 묶는 것이 이 방식의 요점이다.
2. **인가코드는 1회용이라 한 번만 보낸다.** React StrictMode는 effect를 두 번 실행하므로 `useRef` 가드가 없으면 두 번째 교환이 반드시 401로 실패한다.
3. 유저가 동의 화면에서 취소하면 `?error=...`로 돌아온다 — 실패가 아니라 정상 흐름이므로 조용히 로그인 화면으로 되돌린다.

#### 환경변수 (BE·FE 양쪽)

| 이름 | 위치 | 비고 |
|---|---|---|
| `KAKAO_REST_API_KEY` | 루트 `.env` | 카카오 개발자센터 → 앱 키 → **REST API 키**. 비밀 아님 |
| `KAKAO_CLIENT_SECRET` | 루트 `.env` | 앱에서 Client Secret을 **켠 경우만**. 껐으면 비워둔다(빈 값 전송 시 `invalid_client`) |
| `KAKAO_REDIRECT_URI` | 루트 `.env` | 카카오 앱에 등록한 값과 **글자 단위로 동일**해야 한다 |
| `NEXT_PUBLIC_KAKAO_REST_API_KEY` | `frontend/.env.local` | 위 REST API 키와 **같은 값** |
| `NEXT_PUBLIC_KAKAO_REDIRECT_URI` | `frontend/.env.local` | 위 redirect URI와 **같은 값** |

같은 값이 BE·FE 양쪽에 있다 — **한쪽만 바꾸면 토큰 교환이 `invalid_client`로 죽는다.** FE 두 값 중
하나라도 비면 로그인 화면의 카카오 버튼이 **숨는다**(눌러도 실패하는 버튼을 보여주지 않는다).

#### 계정 정책 — 같은 이메일이어도 기존 계정에 잇지 않는다

카카오 계정과 이메일 계정은 **별개 계정**이다. 이어붙이지 않는 이유: 카카오가 주는 이메일은
미인증일 수 있어, 이메일이 같다는 것만으로 잇는 순간 **남의 계정에 들어가는 경로**가 된다.
그래서 카카오에서 이메일을 아예 받지 않고 `kakao_id`로만 식별한다(마이그레이션 0037).

**결과**: 같은 사람이 두 방식으로 들어오면 계정이 둘이 되고 밭 목록이 서로 다르다. 필요해지면
"로그인 후 명시적 계정 연결" 화면으로 푼다(§2 YAGNI) — 자동 연결로는 풀지 않는다.

### `GET /api/v1/auth/me`
- `Authorization: Bearer <access>` 필요. 성공 `data: { id, email, nickname }`. FE 로그인 상태·유저 표시용.
  - `email`은 카카오 계정이면 `null`이다.
- 실패: `401` `UNAUTHORIZED`(토큰 없음)/`INVALID_TOKEN`(무효)

### `PATCH /api/v1/auth/me` (닉네임 변경, 2026-08-05 추가)
- `Authorization: Bearer <access>` 필요. 요청: `{ "nickname": str(1~50) }`
- 성공: `200`, `data: { id, email, nickname }` → FE는 이 유저로 상태를 갈아끼운다(헤더의 "○○님"이 따라온다).
- 실패: `401`(미인증), `422` `VALIDATION_ERROR`(빈 값·50자 초과)
- **대상 id를 받지 않는다** — 인증된 유저 자신만 바꾼다(§11 소유권). 이메일·비밀번호는 이 엔드포인트가 다루지 않는다(본문에 넣어도 무시된다).

#### 왜 필요했나 + FE 라우팅 규칙

카카오는 닉네임 동의항목을 요청하지 않으면 이름을 주지 않아 계정이 `"카카오 사용자"`(`DEFAULT_NICKNAME`)로 시작하는데, 그 값이 헤더에 그대로 노출되고 **바꿀 방법이 없었다**(이메일 가입자도 가입 후엔 못 바꿨다). 동의항목을 늘리는 대신(카카오 계정만 해결되는 반쪽) 직접 정하게 한다.

- **`/onboarding/nickname`** — 이름 정하는 화면. `?next=<내부경로>`로 저장 후 갈 곳을 정한다(기본 `/onboarding`). 외부 URL·`//`로 시작하는 값은 거부한다(열린 리다이렉트 방지).
- **카카오 신규 로그인** → 콜백이 `is_new_user`를 보고 `/onboarding/nickname`으로 보낸다. 이름 저장 후 `/onboarding`(밭 등록)으로 이어진다. `is_new_user`를 서버가 주는 이유: FE가 닉네임 문자열을 `"카카오 사용자"`와 비교해 추측하면, 유저가 실제로 그 이름을 골랐을 때 오판한다.
- **밭이 0개인 유저가 `/dashboard`에 오면 `/onboarding`으로 `replace`** — 가입 직후가 이 경우다. 종전에는 "첫 밭 등록하기" 링크를 눌러야 했다.
- 설정 화면은 같은 페이지를 `?next=/settings`로 링크한다 — 폼을 두 곳에 두면 길이 제약이 갈린다.

## FE가 해야 할 것 (요약)
0. 카카오 로그인은 위 §`POST /api/v1/auth/kakao`의 흐름 3개(state 대조 · 인가코드 1회 전송 · 취소 처리)를 지킨다. 그 외는 이메일 로그인과 동일하다.
1. login 응답의 `access_token`을 **메모리에만** 보관(리로드 시 사라지는 게 정상 — refresh로 복구).
2. 보호된 API 호출마다 `Authorization: Bearer <access>` 헤더 첨부.
3. **401 인터셉터**: access 401 → `POST /auth/refresh` 1회 → 성공 시 새 access로 원요청 **재시도**, 실패(401)면 로그인 화면.
4. fetch/axios는 **`credentials: "include"`**(쿠키 동반 위해). CORS 오리진은 서버가 명시 허용.
5. **미들웨어 게이팅(§9)**: Next middleware는 refresh 쿠키 유무로 라우트 게이팅(비로그인 → `/login`). access는 미들웨어가 못 봄(메모리라서) — 라우트 보호는 쿠키 유무, 실제 인가는 API가.

## 방어 요약 (무엇을 무엇으로)
- **httpOnly** → XSS의 refresh(장기 크레덴셜) 탈취 차단. (httpOnly는 XSS 방어지 CSRF 방어 아님)
- **access를 메모리+헤더** → CSRF 면역(쿠키 자동전송 악용 불가) + access 영구탈취 어렵게(비영속). 단 access 짧게 잡아 노출 최소화.
- **SameSite + Path 한정** → `/auth/refresh`의 CSRF 차단.
- **bcrypt 해시** → 비밀번호 평문 저장/로깅 금지(§11, §18-6).
- **시크릿(`JWT_SECRET`·DB)** → 환경변수 only, 레포/로그/클라 노출 금지(§17).

## 인증 ≠ 인가
- 인증(누구냐): access 검증(`get_current_user`), 라우터 경계.
- 인가(권한 있냐): 소유권 검증(요청유저 == 리소스 소유자), **서비스 계층**. 챗봇 히스토리·밭 접근이 여기 걸림.

## 배포 인시던트: 크로스사이트 배포에서 refresh가 항상 401 (2026-07-26)

**증상**: 로그인 직후엔 정상 동작하다가 새로고침/새 탭을 열면 로그인 상태 복구 불능(재로그인 강제).

**원인**: FE(`foryourfarm.duckdns.org`)와 BE(`*.run.app`)가 등록 도메인(eTLD+1) 자체가 다른
크로스사이트 구성인데, `config.py` 기본값 `cookie_samesite="lax"`가 그대로 운영에 나갔다.
`SameSite=Lax` 쿠키는 top-level GET 네비게이션에만 실리고 `fetch`/`XHR` 같은 서브리퀘스트에는
크로스사이트일 때 절대 첨부되지 않는다(`credentials: "include"`를 붙여도 무관). 그래서
`POST /api/v1/auth/refresh`가 쿠키를 받지 못해 `request.cookies.get(REFRESH_COOKIE)`가 항상
`None` → `401 UNAUTHORIZED`. 로그인 직후엔 응답 바디로 받은 access token이 메모리에 살아있어
증상이 안 보이다가, 메모리가 비는 순간(새로고침 등)부터 복구가 막힌다. 로그인 자체는
CORS(`allow_credentials=True` + 정확한 origin)가 맞게 설정돼 있어 별개로 통과한다.

**수정**: 운영 Cloud Run 서비스 환경변수에 아래를 설정한다(SameSite=None은 Secure 없이는
브라우저가 거부하므로 반드시 같이 켠다). 코드/설정 자체는 이미 env로 오버라이드 가능하게
돼 있었고, 이번 케이스는 값 누락이었다 — 참고로 `.env.example`에 항목과 근거를 추가했다.

```
gcloud run services update <backend-service-name> \
  --region asia-northeast3 \
  --update-env-vars COOKIE_SECURE=true,COOKIE_SAMESITE=none
```

FE·BE를 같은 사이트(서브도메인 등)로 묶으면 `SameSite=Lax`를 유지할 수도 있으나, 지금 구조를
바꾸는 건 별도 결정 사항이라 여기서는 다루지 않는다.
