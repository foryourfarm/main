"""chat_message 영속화(로드/저장/소유권)의 결정론 경계 검증.

Postgres/pgvector 없이 sqlite 인메모리에 chat_message 테이블만 만들어 돌린다
(로직은 (user_id, session_id) 필터라 DB 종류와 무관).

실행: backend/.venv/Scripts/python.exe -m unittest tests.test_chat_persistence   (backend/ 에서)
"""

import unittest
from datetime import UTC, datetime

from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.models import ChatMessage
from app.services.chat_service import (
    delete_session,
    list_sessions,
    load_history,
    prune_old_messages,
    save_turn,
)


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

    def test_list_sessions_newest_first_with_title_from_first_question(self):
        save_turn(self.db, 1, "s1", "물 언제 줘요?", "아침에요")
        save_turn(self.db, 1, "s1", "비료는요?", "주 1회요")
        save_turn(self.db, 1, "s2", "진딧물 어떡해요?", "제거하세요")
        sessions = list_sessions(self.db, 1, limit=10)
        self.assertEqual([s["session_id"] for s in sessions], ["s2", "s1"])  # 최근 활동 순
        # 제목은 그 스레드의 첫 질문(두 번째 질문이 아니다)
        self.assertEqual(sessions[1]["title"], "물 언제 줘요?")
        self.assertEqual(sessions[1]["message_count"], 4)

    def test_list_sessions_scoped_to_owner(self):
        save_turn(self.db, 1, "s1", "내 것", "답")
        self.assertEqual(list_sessions(self.db, 2, limit=10), [])

    def test_delete_session_removes_only_that_thread(self):
        save_turn(self.db, 1, "s1", "q1", "a1")
        save_turn(self.db, 1, "s2", "q2", "a2")
        self.assertEqual(delete_session(self.db, 1, "s1"), 2)
        self.assertEqual([s["session_id"] for s in list_sessions(self.db, 1, limit=10)], ["s2"])

    def test_delete_session_of_other_user_is_noop(self):
        save_turn(self.db, 1, "s1", "비밀", "답")
        self.assertEqual(delete_session(self.db, 2, "s1"), 0)  # 남의 것은 못 지운다(§11)
        self.assertEqual(len(load_history(self.db, 1, "s1", limit=6)), 2)

    def test_prune_deletes_only_older_than_cutoff(self):
        old = datetime(2025, 1, 1, tzinfo=UTC)
        save_turn(self.db, 1, "old", "작년 질문", "작년 답")
        # created_at은 server_default라 직접 과거로 되돌려 "오래된 행"을 만든다.
        self.db.query(ChatMessage).update({ChatMessage.created_at: old})
        self.db.commit()
        save_turn(self.db, 1, "new", "오늘 질문", "오늘 답")

        deleted = prune_old_messages(self.db, datetime(2025, 6, 1, tzinfo=UTC))
        self.assertEqual(deleted, 2)
        self.assertEqual([s["session_id"] for s in list_sessions(self.db, 1, limit=10)], ["new"])

    def test_prune_with_nothing_old_deletes_nothing(self):
        save_turn(self.db, 1, "s1", "q", "a")
        self.assertEqual(prune_old_messages(self.db, datetime(2020, 1, 1, tzinfo=UTC)), 0)
        self.assertEqual(len(load_history(self.db, 1, "s1", limit=6)), 2)


if __name__ == "__main__":
    unittest.main()
