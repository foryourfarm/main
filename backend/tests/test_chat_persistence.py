"""chat_message 영속화(로드/저장/소유권)의 결정론 경계 검증.

Postgres/pgvector 없이 sqlite 인메모리에 chat_message 테이블만 만들어 돌린다
(로직은 (user_id, session_id) 필터라 DB 종류와 무관).

실행: backend/.venv/Scripts/python.exe -m unittest tests.test_chat_persistence   (backend/ 에서)
"""

import unittest

from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.models import ChatMessage
from app.services.chat_service import load_history, save_turn


# BIGINT PK는 sqlite에서 rowid로 autoincrement되지 않는다(Postgres는 BIGSERIAL로 정상).
# 테스트 엔진에서만 INTEGER로 컴파일해 PK 자동증가를 살린다(운영 스키마엔 영향 없음).
@compiles(BigInteger, "sqlite")
def _bigint_as_integer_on_sqlite(element, compiler, **kw):
    return "INTEGER"


class TestChatPersistence(unittest.TestCase):
    def setUp(self):
        # chat_message 테이블만 생성(users FK는 sqlite에서 미강제라 유저 행 없이도 됨).
        self.engine = create_engine("sqlite://")
        ChatMessage.__table__.create(self.engine)
        self.db = Session(self.engine)

    def tearDown(self):
        self.db.close()

    def test_save_then_load_roundtrip_in_order(self):
        save_turn(self.db, user_id=1, session_id="s1", question="물 언제?", answer="아침에요")
        save_turn(self.db, user_id=1, session_id="s1", question="비료는?", answer="주 1회요")
        hist = load_history(self.db, user_id=1, session_id="s1", limit=6)
        self.assertEqual(
            hist,
            [
                ("user", "물 언제?"),
                ("assistant", "아침에요"),
                ("user", "비료는?"),
                ("assistant", "주 1회요"),
            ],
        )

    def test_limit_keeps_most_recent_in_chronological_order(self):
        for i in range(5):
            save_turn(self.db, 1, "s1", f"q{i}", f"a{i}")  # 10개 메시지
        hist = load_history(self.db, 1, "s1", limit=3)  # 최근 3개(오래된 순)
        self.assertEqual(hist, [("assistant", "a3"), ("user", "q4"), ("assistant", "a4")])

    def test_ownership_other_user_cannot_read(self):
        save_turn(self.db, user_id=1, session_id="s1", question="비밀", answer="답")
        # 다른 유저가 같은 session_id를 넣어도 빈 히스토리(§11 소유권)
        self.assertEqual(load_history(self.db, user_id=2, session_id="s1", limit=6), [])

    def test_sessions_isolated_within_same_user(self):
        save_turn(self.db, 1, "s1", "q1", "a1")
        save_turn(self.db, 1, "s2", "q2", "a2")
        self.assertEqual(load_history(self.db, 1, "s2", limit=6), [("user", "q2"), ("assistant", "a2")])

    def test_empty_history_when_none(self):
        self.assertEqual(load_history(self.db, 1, "nope", limit=6), [])


if __name__ == "__main__":
    unittest.main()
