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

### `GET /api/v1/auth/me`
- `Authorization: Bearer <access>` 필요. 성공 `data: { id, email, nickname }`. FE 로그인 상태·유저 표시용.
- 실패: `401` `UNAUTHORIZED`(토큰 없음)/`INVALID_TOKEN`(무효)

## FE가 해야 할 것 (요약)
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
