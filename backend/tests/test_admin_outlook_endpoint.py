"""운영 갱신 엔드포인트의 인증·실패 처리 (app/api/admin.py).

공개 서비스에 붙는 적재 경로라 **인증이 뚫리는 회귀가 가장 비싸다.** 그래서 통과 경로
하나보다 거절 경로를 더 촘촘히 잡는다. 특히:

- 토큰 env 미설정이 "누구나 통과"로 바뀌면 배포 실수 하나가 곧 공개 적재 경로가 된다.
- 인증이 적재보다 늦게 돌면 무단 호출이 기상청 RSS·DB 비용을 만든다 — 401에서도
  `ingest_latest_outlook`이 불리지 않았는지 확인한다.

리포 최초의 HTTP 엔드포인트 테스트다(종전 0건 — nexttodo 인프라 §2). DB는 타지 않는다:
CI에 Postgres가 없고, 여기서 검증할 것은 배선과 가드지 적재 SQL이 아니다.
"""

import unittest
from datetime import date
from unittest import mock

from fastapi.testclient import TestClient

from app.api import admin
from app.core.config import settings
from app.db.session import get_db
from app.infra.public_api.outlook_client import OutlookFetchError
from app.main import app
from app.schemas.admin import OutlookIngestResult

URL = "/api/v1/admin/weather-outlooks"
TOKEN = "0123456789abcdef0123456789abcdef"

RESULT = OutlookIngestResult(
    published_at=date(2026, 7, 22),
    rows=1536,
    target_months=[date(2026, 8, 1), date(2026, 9, 1), date(2026, 10, 1)],
    unmapped_zones=["평안남도"],
)


class TestAdminOutlookEndpoint(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_db] = lambda: None
        # raise_server_exceptions=False — 예기치 못한 500이 트레이스백이 아니라 상태코드로
        # 드러나야 "401이어야 하는데 500이다" 같은 실패가 읽힌다.
        self.client = TestClient(app, raise_server_exceptions=False)
        self._saved_token = settings.admin_task_token
        settings.admin_task_token = TOKEN

    def tearDown(self) -> None:
        settings.admin_task_token = self._saved_token
        app.dependency_overrides.clear()

    def test_missing_header_is_rejected_before_any_ingest(self):
        with mock.patch.object(admin, "ingest_latest_outlook") as ingest:
            resp = self.client.post(URL)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["error"]["code"], "UNAUTHORIZED")
        ingest.assert_not_called()  # 무단 호출이 상류·DB 비용을 만들면 안 된다

    def test_wrong_token_is_rejected(self):
        with mock.patch.object(admin, "ingest_latest_outlook") as ingest:
            resp = self.client.post(URL, headers={"X-Admin-Token": "wrong"})
        self.assertEqual(resp.status_code, 401)
        ingest.assert_not_called()

    def test_token_prefix_is_not_enough(self):
        # 접두 일치만으로 통과하면 한 글자씩 늘려가며 토큰을 복원할 수 있다.
        with mock.patch.object(admin, "ingest_latest_outlook") as ingest:
            resp = self.client.post(URL, headers={"X-Admin-Token": TOKEN[:-1]})
        self.assertEqual(resp.status_code, 401)
        ingest.assert_not_called()

    def test_non_ascii_header_is_401_not_500(self):
        # secrets.compare_digest에 str을 그대로 넘기면 비ASCII에서 TypeError → 500이 된다.
        # 헤더는 bytes로 보낸다: httpx는 비ASCII **str**을 아예 거부하지만, 실제 공격자는
        # 소켓에 바이트를 그대로 쓴다. starlette이 latin-1로 디코드해 비ASCII str이 되므로
        # 클라이언트 제약과 무관하게 서버는 이 입력을 받는다.
        with mock.patch.object(admin, "ingest_latest_outlook") as ingest:
            resp = self.client.post(URL, headers={b"X-Admin-Token": b"\xff\xfe"})
        self.assertEqual(resp.status_code, 401)
        ingest.assert_not_called()

    def test_unset_token_disables_endpoint(self):
        # 미설정이 "누구나 통과"가 되면 env를 빠뜨린 배포가 공개 적재 경로가 된다.
        settings.admin_task_token = ""
        with mock.patch.object(admin, "ingest_latest_outlook") as ingest:
            resp = self.client.post(URL, headers={"X-Admin-Token": TOKEN})
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.json()["error"]["code"], "ADMIN_TASKS_DISABLED")
        ingest.assert_not_called()

    def test_empty_header_does_not_match_unset_token(self):
        # 빈 문자열끼리 비교하면 compare_digest가 참이 된다 — 위 503 가드가 그 앞을 막는다.
        settings.admin_task_token = ""
        with mock.patch.object(admin, "ingest_latest_outlook") as ingest:
            resp = self.client.post(URL)
        self.assertNotEqual(resp.status_code, 200)
        ingest.assert_not_called()

    def test_valid_token_ingests_and_returns_result(self):
        with mock.patch.object(admin, "ingest_latest_outlook", return_value=RESULT) as ingest:
            resp = self.client.post(URL, headers={"X-Admin-Token": TOKEN})
        self.assertEqual(resp.status_code, 200)
        ingest.assert_called_once()
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["rows"], 1536)
        self.assertEqual(body["data"]["published_at"], "2026-07-22")
        self.assertEqual(body["data"]["target_months"][0], "2026-08-01")
        self.assertEqual(body["data"]["unmapped_zones"], ["평안남도"])

    def test_upstream_failure_returns_502(self):
        # 200으로 삼키면 스케줄러가 재시도·알림을 못 해 "에러 없이 조용히 낡는" 상태로 돌아간다.
        with mock.patch.object(
            admin, "ingest_latest_outlook", side_effect=OutlookFetchError("없음")
        ):
            resp = self.client.post(URL, headers={"X-Admin-Token": TOKEN})
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(resp.json()["error"]["code"], "UPSTREAM_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
