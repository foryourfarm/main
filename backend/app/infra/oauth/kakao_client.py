"""카카오 로그인 REST API 클라이언트 (kauth/kapi.kakao.com).

문서: https://developers.kakao.com/docs/latest/ko/kakaologin/rest-api

이 모듈은 **인가코드를 카카오 회원번호로 바꾸는 일만** 한다. 토큰 발급·쿠키·계정 생성은
우리 인증 계층(`auth_service`·`api/auth.py`)이 이미 갖고 있으므로 건드리지 않는다.

카카오 액세스 토큰은 **저장하지 않는다.** 카카오 API를 대신 호출해줄 기능이 없어서(우리는
로그인 확인만 한다) 저장하면 쓰지도 않는 장기 크리덴셜을 들고 있는 것이 된다(§17).

경계 방어(§12): 응답이 200이어도 우리가 필요한 필드가 없을 수 있고, 카카오는 실패를 200에
`error` 필드로 싣는 경우가 있다. 그래서 상태코드만 보지 않고 필드 존재를 확인한다.
"""

import httpx

TOKEN_URL = "https://kauth.kakao.com/oauth/token"
PROFILE_URL = "https://kapi.kakao.com/v2/user/me"

TIMEOUT_S = 10.0
"""사람이 로그인 버튼을 누르고 기다리는 동기 경로다 — 길게 잡으면 화면이 멈춘 것처럼 보인다.
재시도도 넣지 않는다(유저가 다시 누르는 것이 더 빠르고, 인가코드는 1회용이라 재시도가 무의미하다)."""

# 닉네임 동의를 받지 못했을 때 쓸 이름. 로그인 자체를 막지 않는다 — 닉네임은 표시용일 뿐이다.
DEFAULT_NICKNAME = "카카오 사용자"
NICKNAME_MAX_LEN = 50  # users.nickname 스키마 상한과 맞춘다


class KakaoError(Exception):
    """카카오 연동 실패. 호출부가 HTTP 상태로 매핑한다."""


class KakaoAuthError(KakaoError):
    """인가코드가 잘못됐거나 이미 사용됐다 — 유저가 다시 로그인해야 한다(401로 매핑)."""


def exchange_code_for_token(
    code: str, client_id: str, redirect_uri: str, client_secret: str = ""
) -> str:
    """인가코드 → 카카오 액세스 토큰.

    `redirect_uri`는 인가 요청 때 쓴 값과 **정확히 같아야** 한다(카카오가 대조한다). 그래서
    클라이언트가 보내온 값을 쓰지 않고 서버 설정값을 쓴다 — 클라이언트가 정하게 하면 값이
    갈릴 때 원인을 찾기 어렵고, 신뢰 경계 밖 입력이 외부 호출에 그대로 실린다(§17).
    """
    data = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code": code,
    }
    if client_secret:
        # 카카오 앱에서 "보안 → Client Secret"을 활성화한 경우에만 필수다. 껐으면 보내지 않는다
        # (빈 값을 보내면 카카오가 invalid_client로 거절한다).
        data["client_secret"] = client_secret

    try:
        resp = httpx.post(TOKEN_URL, data=data, timeout=TIMEOUT_S)
        body = resp.json()
    except httpx.HTTPError as exc:
        raise KakaoError(f"카카오 토큰 요청 실패: {exc}") from exc
    except ValueError as exc:  # JSON이 아닌 응답(장애 페이지 등)
        raise KakaoError("카카오 토큰 응답을 해석할 수 없음") from exc

    if not isinstance(body, dict):
        raise KakaoError("카카오 토큰 응답 형식이 예상과 다름")
    # 인가코드 문제는 4xx + error 코드로 온다. 유저 조치(재로그인)로 풀리는 것이므로 구분한다.
    if resp.status_code >= 400 or "error" in body:
        error = str(body.get("error") or resp.status_code)
        if resp.status_code < 500:
            raise KakaoAuthError(f"카카오 인가 실패: {error}")
        raise KakaoError(f"카카오 토큰 요청 실패: {error}")

    token = body.get("access_token")
    if not isinstance(token, str) or not token:
        raise KakaoError("카카오 응답에 access_token이 없음")
    return token


def fetch_kakao_account(access_token: str) -> tuple[int, str]:
    """카카오 액세스 토큰 → (회원번호, 닉네임).

    **이메일·성별 등 다른 정보는 받지 않는다.** 우리가 쓰는 것은 회원번호(계정 식별)와
    닉네임(표시)뿐이고, 안 쓰는 개인정보를 받아두면 보관 책임만 늘어난다(§17).
    닉네임은 동의 항목이라 없을 수 있어 기본값으로 폴백한다.
    """
    try:
        resp = httpx.get(
            PROFILE_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=TIMEOUT_S,
        )
        body = resp.json()
    except httpx.HTTPError as exc:
        raise KakaoError(f"카카오 사용자 조회 실패: {exc}") from exc
    except ValueError as exc:
        raise KakaoError("카카오 사용자 응답을 해석할 수 없음") from exc

    if not isinstance(body, dict):
        raise KakaoError("카카오 사용자 응답 형식이 예상과 다름")
    if resp.status_code == 401:
        raise KakaoAuthError("카카오 액세스 토큰이 유효하지 않음")
    if resp.status_code >= 400:
        raise KakaoError(f"카카오 사용자 조회 실패: {body.get('msg') or resp.status_code}")

    # 회원번호는 정수로 오지만 JSON 수치는 문자열로 오는 사례가 있어 둘 다 받는다.
    raw_id = body.get("id")
    try:
        kakao_id = int(raw_id)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise KakaoError("카카오 응답에 회원번호(id)가 없음") from exc

    return kakao_id, _nickname_of(body)


def _nickname_of(body: dict[str, object]) -> str:
    """`properties.nickname` → `kakao_account.profile.nickname` → 기본값 순으로 찾는다.

    두 경로를 다 보는 이유: 동의 항목·앱 설정에 따라 어느 한쪽만 채워져 온다.
    """
    properties = body.get("properties")
    if isinstance(properties, dict):
        name = properties.get("nickname")
        if isinstance(name, str) and name.strip():
            return name.strip()[:NICKNAME_MAX_LEN]

    account = body.get("kakao_account")
    if isinstance(account, dict):
        profile = account.get("profile")
        if isinstance(profile, dict):
            name = profile.get("nickname")
            if isinstance(name, str) and name.strip():
                return name.strip()[:NICKNAME_MAX_LEN]

    return DEFAULT_NICKNAME
