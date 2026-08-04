"""퀘스트·펫 엔드포인트 계약 검증 — docs/quest-pet-api.md.

**test_quest_progress.py와 역할이 다르다.** 저기는 서비스 함수의 파생 계산을 보고, 여기는
**응답 JSON**을 본다. 펫이 한 마리로 바뀌면서 `pet.code` → `pet.stage_code`로 필드명이
갈렸는데, pydantic 스키마(`PetState`)가 필드를 빠뜨리면 서비스는 멀쩡한데 화면에서만 그림이
사라진다 — 그 구간은 서비스 테스트로 잡히지 않는다.

로그인은 타지 않는다: 비밀번호 없이 `get_current_user` 의존성만 갈아끼운다
(tests/test_auth_endpoint.py의 dependency_overrides 패턴).

실행: backend/.venv/Scripts/python.exe -m unittest tests.test_quest_endpoint   (backend/ 에서)
"""

import unittest
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.db.session import get_db
from app.main import app
from app.models import User, UserDailyQuest
from app.services import quest_service as qs


@compiles(BigInteger, "sqlite")
def _bigint_as_integer_on_sqlite(element, compiler, **kw):
    return "INTEGER"


PET_ASSETS = Path(__file__).parents[2] / "frontend" / "public" / "assets" / "pet"


class TestQuestEndpoint(unittest.TestCase):
    def setUp(self):
        # TestClient는 앱을 **다른 스레드**에서 돌린다. sqlite:// 인메모리는 기본 풀이 스레드마다
        # 새 연결을 만들어 그쪽에서는 빈 DB가 보인다(no such table) — StaticPool로 한 연결을 공유한다.
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        User.__table__.create(self.engine)
        UserDailyQuest.__table__.create(self.engine)
        self.db = Session(self.engine)
        self.user = User(email="a@b.c", password_hash="x", nickname="농부")
        self.db.add(self.user)
        self.db.commit()
        self.next_day = date(2020, 1, 1)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()

    def pet(self) -> dict:
        r = self.client.get("/api/v1/quests/today")
        self.assertEqual(r.status_code, 200)
        return r.json()["data"]

    def grant(self, exp: int) -> None:
        """경험치를 로그로 적립. 같은 퀘스트는 하루 한 번(UNIQUE)이라 날짜를 밀어가며 넣는다 —
        커서를 인스턴스에 둬야 여러 번 불러도 같은 날짜를 다시 쓰지 않는다."""
        for _ in range(exp // 10):
            self.db.add(
                UserDailyQuest(
                    user_id=self.user.id, quest_date=self.next_day, quest_code="view_short"
                )
            )
            self.next_day = date.fromordinal(self.next_day.toordinal() + 1)
        self.db.commit()

    def test_response_shape(self):
        data = self.pet()
        # 구 필드가 남아 있으면 FE가 옛 경로로 그림을 찾다 조용히 실패한다.
        self.assertIn("stage_code", data["pet"])
        self.assertNotIn("code", data["pet"])
        self.assertNotIn("pets", data)
        self.assertEqual(data["pet"]["name"], "텃밭이")

    def test_stage_code_follows_level(self):
        for exp, code in ((0, "egg"), (240, "chick"), (520, "fledgling"), (900, "swallow")):
            self.grant(exp - qs.total_exp(self.db, self.user.id))
            self.assertEqual(self.pet()["pet"]["stage_code"], code, f"{exp}exp")

    def test_every_stage_code_has_an_illustration(self):
        # 단계 코드가 곧 파일명이다(frontend/lib/pet.ts STAGE_IMAGE).
        for stage in qs.PET_STAGES:
            self.assertTrue((PET_ASSETS / f"{stage.code}.png").is_file(), stage.code)

    def test_pet_change_endpoint_is_gone(self):
        # 캐릭터가 한 마리라 고를 것이 없다. 405가 아니라 404 — 경로가 통째로 없다.
        self.assertEqual(self.client.put("/api/v1/pet", json={"code": "pup"}).status_code, 404)
        self.assertFalse([p for p in app.openapi()["paths"] if "pet" in p])


if __name__ == "__main__":
    unittest.main()
