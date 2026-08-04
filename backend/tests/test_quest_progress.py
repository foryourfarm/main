"""퀘스트 로그 → 경험치/레벨/펫단계 파생 계산 검증(PRD.md §14.5).

경험치를 저장하지 않고 로그에서 계산하는 구조라, 여기서 깨지면 화면의 레벨이 조용히 틀린다.
Postgres 없이 sqlite 인메모리에 필요한 테이블만 만들어 돌린다(로직은 DB 종류와 무관).

실행: backend/.venv/Scripts/python.exe -m unittest tests.test_quest_progress   (backend/ 에서)
"""

import unittest
from datetime import date

from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import User, UserDailyQuest
from app.services import quest_service as qs


@compiles(BigInteger, "sqlite")
def _bigint_as_integer_on_sqlite(element, compiler, **kw):
    # BIGINT PK는 sqlite에서 자동증가하지 않는다(Postgres는 BIGSERIAL로 정상).
    return "INTEGER"


DAY = date(2026, 8, 4)
NEXT_DAY = date(2026, 8, 5)


class TestQuestProgress(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        User.__table__.create(self.engine)
        UserDailyQuest.__table__.create(self.engine)
        self.db = Session(self.engine)
        self.user = User(email="a@b.c", password_hash="x", nickname="농부")
        self.db.add(self.user)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_completing_all_quests_gives_expected_exp(self):
        for q in qs.QUESTS:
            qs.complete(self.db, self.user.id, q.code, DAY)
        self.assertEqual(qs.total_exp(self.db, self.user.id), sum(q.exp for q in qs.QUESTS))

    def test_repeat_same_day_is_idempotent(self):
        qs.complete(self.db, self.user.id, "view_short", DAY)
        qs.complete(self.db, self.user.id, "view_short", DAY)  # 다시 눌러도 경험치는 그대로
        self.assertEqual(qs.total_exp(self.db, self.user.id), 10)

    def test_same_quest_next_day_counts_again(self):
        qs.complete(self.db, self.user.id, "view_short", DAY)
        qs.complete(self.db, self.user.id, "view_short", NEXT_DAY)
        self.assertEqual(qs.total_exp(self.db, self.user.id), 20)

    def test_unknown_quest_rejected(self):
        with self.assertRaises(AppError):
            qs.complete(self.db, self.user.id, "hack", DAY)

    def test_level_boundaries(self):
        # 100exp마다 1레벨. 경계 바로 아래/위가 갈리는지가 핵심.
        self.assertEqual((qs.level_of(0), qs.level_of(99)), (1, 1))
        self.assertEqual((qs.level_of(100), qs.level_of(199)), (2, 2))
        self.assertEqual(qs.level_of(1000), 11)
        self.assertEqual((qs.exp_into_level(0), qs.exp_into_level(150)), (0, 50))

    def test_pet_stage_boundaries(self):
        # 단계 경계(1/3/6/10)에서 정확히 갈려야 한다 — 오프바이원이 나면 외형이 하루 늦게 바뀐다.
        self.assertEqual([qs.stage_of(lv).label for lv in (1, 2)], ["씨앗", "씨앗"])
        self.assertEqual([qs.stage_of(lv).label for lv in (3, 5)], ["새싹", "새싹"])
        self.assertEqual([qs.stage_of(lv).label for lv in (6, 9)], ["자람", "자람"])
        self.assertEqual([qs.stage_of(lv).label for lv in (10, 99)], ["열매", "열매"])

    def test_pet_defaults_and_whitelist(self):
        self.assertEqual(qs.pet_of(self.user)[0], qs.DEFAULT_PET_CODE)  # 미선택 → 기본 펫
        qs.set_pet(self.db, self.user, "pup")
        self.assertEqual(qs.pet_of(self.user)[0], "pup")
        with self.assertRaises(AppError):
            qs.set_pet(self.db, self.user, "dragon")

    def test_progress_marks_today_only(self):
        qs.complete(self.db, self.user.id, "view_short", DAY)
        today = qs.progress(self.db, self.user, DAY)
        tomorrow = qs.progress(self.db, self.user, NEXT_DAY)
        done_today = {q["code"] for q in today["quests"] if q["is_done"]}
        self.assertEqual(done_today, {"view_short"})
        # 날이 바뀌면 퀘스트는 다시 미완료지만 경험치는 유지된다.
        self.assertEqual([q for q in tomorrow["quests"] if q["is_done"]], [])
        self.assertEqual(tomorrow["exp"], 10)

    def test_unknown_code_in_log_does_not_break_exp(self):
        # 카탈로그가 개편돼 사라진 코드가 로그에 남아도 조회가 죽지 않는다.
        self.db.add(UserDailyQuest(user_id=self.user.id, quest_date=DAY, quest_code="retired"))
        self.db.commit()
        self.assertEqual(qs.total_exp(self.db, self.user.id), 0)


if __name__ == "__main__":
    unittest.main()
