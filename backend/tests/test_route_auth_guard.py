"""모든 라우트가 인증 가드를 거치는지 구조적으로 검증 (CLAUDE.md §11).

**왜 필요한가**: 지금까지 인증은 `Depends(get_current_user)`를 **각 엔드포인트가 직접 적는**
방식이다. 한 줄 빠뜨리면 그 엔드포인트만 조용히 열린다 — 테스트도 통과하고 앱도 뜨고
화면도 정상이라 **아무도 못 잡는다**(nexttodo 인프라 §2 "배선 회귀는 아무도 못 잡는다").
서비스 계층 테스트는 이걸 원리적으로 못 잡는다. 서비스는 `user_id`를 인자로 받으므로
라우터가 그 값을 어디서 가져오는지(인증된 유저인지, 아니면 아무나인지)를 모른다.

**설계**: 공개 라우트를 **화이트리스트로 명시**하고, 나머지는 전부 자격증명 없이 401이어야
한다. 새 엔드포인트를 추가하면 둘 중 하나를 강제로 선택하게 된다 — 화이트리스트에 넣고
근거를 적거나, 인증을 붙이거나. **잊는 것이 기본값이 되지 않게 하는 것**이 이 파일의 목적이다.

DB는 타지 않는다. `get_current_user`가 자격증명 부재를 확인하는 시점이 서비스 호출보다
앞이라 401 경로는 DB에 닿지 않는다 — CI에 Postgres가 없어도 돈다.
"""

import unittest

from fastapi.testclient import TestClient

from app.main import app

# 인증 없이 접근 가능한 라우트 — **의도적으로 공개된 것만** 여기 적는다.
# 새 엔드포인트가 401을 안 내면 이 목록에 없어서 테스트가 실패한다. 그때 "정말 공개해도
# 되는가"를 판단하고, 공개가 맞으면 근거와 함께 여기 추가할 것.
PUBLIC_ROUTES: dict[tuple[str, str], str] = {
    ("GET", "/openapi.json"): "FastAPI 기본 스키마",
    ("GET", "/docs"): "FastAPI 기본 문서",
    ("GET", "/docs/oauth2-redirect"): "FastAPI 기본 문서",
    ("GET", "/redoc"): "FastAPI 기본 문서",
    ("GET", "/api/v1/health"): "헬스체크 — Cloud Run이 인증 없이 부른다",
    ("POST", "/api/v1/auth/signup"): "가입은 인증 전 행위",
    ("POST", "/api/v1/auth/login"): "로그인은 인증 전 행위",
    # 카카오 인가코드를 받는 자리라 우리 토큰이 있을 수 없다. 대신 **카카오가 발급한 1회용
    # 인가코드**가 자격증명 역할을 한다 — 코드 검증에 실패하면 401(test_kakao_login.py).
    ("POST", "/api/v1/auth/kakao"): "카카오 로그인도 인증 전 행위(인가코드가 자격증명)",
    ("POST", "/api/v1/auth/refresh"): "httpOnly 쿠키로 자체 검증(Bearer 아님)",
    ("POST", "/api/v1/auth/logout"): "쿠키 삭제만 — 토큰 없어도 안전하게 동작해야 한다",
    # `/api/v1/chat`은 **여기 없다.** 종전에는 "게스트 허용(PRD 챗봇 게스트 모드)"라는 근거로
    # 열려 있었는데, 그 조항은 PRD에 존재하지 않는다 — §4.1이 오히려 "로그인 필수 / 비로그인
    # 접근 시 로그인으로 리다이렉트"라고 적고 §4.6(챗봇)은 게스트를 언급하지 않는다. 구현 쪽에서
    # 자란 기능에 화이트리스트 주석이 사후 정당성을 붙여준 경우다(§18-7). 게다가 그 경로는
    # **비인증으로 GPU를 태울 수 있는 유일한 엔드포인트**였다. 2026-08-05 보안 점검에서 닫았다.
    # 온보딩 선택지. 유저 소유 데이터가 아니라 전국 공통 마스터다(farms.py docstring).
    ("GET", "/api/v1/regions"): "공개 마스터 데이터",
    ("GET", "/api/v1/regions/{region_id}/districts"): "공개 마스터 데이터",
    ("GET", "/api/v1/crops"): "공개 마스터 데이터",
    # 유저 인증이 아니라 공유 시크릿 헤더로 막는다. 그 가드는
    # test_admin_outlook_endpoint.py가 따로 검증한다(미설정 시 503 fail-closed 포함).
    ("POST", "/api/v1/admin/weather-outlooks"): "X-Admin-Token 가드(별도 테스트)",
    ("POST", "/api/v1/admin/chat-retention"): "X-Admin-Token 가드(유저 인증 아님)",
}

# 경로 파라미터 채움값. 인증이 서비스 호출보다 먼저 돌기 때문에 실재하지 않아도 된다.
PATH_PARAM_STUB = "1"


def _iter_routes():
    """(method, path) 전부. FastAPI 0.139는 include_router를 `_IncludedRouter`로 감싸
    `app.routes`가 평평하지 않다 — 한 겹 들어가야 실제 엔드포인트가 나온다."""
    for entry in app.routes:
        original = getattr(entry, "original_router", None)
        targets = original.routes if original is not None else [entry]
        for route in targets:
            methods = getattr(route, "methods", None) or set()
            for method in sorted(methods - {"HEAD", "OPTIONS"}):
                yield method, route.path


def _fill(path: str) -> str:
    """`/farms/{farm_id}` → `/farms/1`."""
    out = path
    while "{" in out:
        start = out.index("{")
        end = out.index("}", start)
        out = out[:start] + PATH_PARAM_STUB + out[end + 1 :]
    return out


class TestRouteAuthGuard(unittest.TestCase):
    def setUp(self) -> None:
        # raise_server_exceptions=False — 401이어야 할 자리에서 500이 나면 트레이스백이
        # 아니라 상태코드로 드러나야 실패 원인이 읽힌다.
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_finds_routes_at_all(self):
        # 열거가 깨지면(FastAPI 내부구조 변경 등) 아래 검증이 0건을 돌며 공허하게 통과한다.
        routes = list(_iter_routes())
        self.assertGreater(len(routes), 15, f"라우트를 {len(routes)}개만 찾았다 — 열거가 깨졌다")

    def test_protected_routes_reject_missing_credentials(self):
        """화이트리스트에 없는 라우트는 자격증명 없이 401이어야 한다."""
        checked = 0
        for method, path in _iter_routes():
            if (method, path) in PUBLIC_ROUTES:
                continue
            checked += 1
            with self.subTest(method=method, path=path):
                resp = self.client.request(method, _fill(path), json={})
                self.assertEqual(
                    resp.status_code,
                    401,
                    f"{method} {path}가 인증 없이 {resp.status_code}를 냈다 — "
                    "인증을 붙이거나, 의도적 공개면 PUBLIC_ROUTES에 근거와 함께 추가할 것",
                )
        # 보호 대상이 0건이면 위 루프가 아무것도 안 하고 통과한다.
        self.assertGreater(checked, 5, f"보호 대상을 {checked}개만 검사했다")

    def test_whitelist_has_no_stale_entries(self):
        """지워진 라우트가 화이트리스트에 남아 있으면, 나중에 같은 경로가 다시 생길 때
        인증 검사를 건너뛴다 — 화이트리스트가 조용히 구멍이 된다."""
        actual = set(_iter_routes())
        stale = sorted(k for k in PUBLIC_ROUTES if k not in actual)
        self.assertEqual(stale, [], f"PUBLIC_ROUTES에 실재하지 않는 라우트가 있다: {stale}")


if __name__ == "__main__":
    unittest.main()
