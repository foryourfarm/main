"""밭 수정/삭제(설정 화면)의 경계 검증 — 소유권 + 토양 기준값 재초기화 판단.

Postgres 없이 sqlite 인메모리에 필요한 테이블만 만들어 돌린다(로직은 필터·분기라 DB 종류 무관).
외부 API(흙토람)는 `get_or_fetch`를 스텁으로 갈아 호출하지 않는다.

실행: backend/.venv/Scripts/python.exe -m unittest tests.test_farm_update   (backend/ 에서)
"""

import unittest
from datetime import date
from decimal import Decimal

from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Crop, District, DistrictSoil, Region, SoilState, UserFarm
from app.services import farm_service


# BIGINT PK는 sqlite에서 autoincrement되지 않는다(Postgres는 BIGSERIAL로 정상).
@compiles(BigInteger, "sqlite")
def _bigint_as_integer_on_sqlite(element, compiler, **kw):
    return "INTEGER"


def _stub_get_or_fetch(db, bjd_code, field_type):
    """흙토람 대신. 어떤 (읍면동, 경지구분)으로 조회됐는지 source에 남겨 검증에 쓴다."""
    return DistrictSoil(
        bjd_code=bjd_code,
        field_type=field_type,
        ph=Decimal("6.5"),
        ec=Decimal("0.5"),
        p2o5=Decimal("300"),
        organic_matter=Decimal("25"),
        sample_count=1,
        source=f"stub({bjd_code},{field_type})",
    )


class TestFarmUpdate(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        for model in (Region, District, Crop, UserFarm, SoilState):
            model.__table__.create(self.engine)
        self.db = Session(self.engine)

        self.db.add_all(
            [
                Region(id=1, name="순천시", sido="전남"),
                Region(id=2, name="고창군", sido="전북"),
                District(bjd_code="4615012300", region_id=1, name="삼거동"),
                District(bjd_code="4615012400", region_id=1, name="조례동"),
                District(bjd_code="5279025000", region_id=2, name="고창읍"),
                Crop(id=1, name="사과", exam_field_type="4"),
                Crop(id=2, name="배", exam_field_type="4"),  # 사과와 같은 경지구분(과수)
                Crop(id=4, name="감자", exam_field_type="2"),
            ]
        )
        self.db.commit()

        self._real_get_or_fetch = farm_service.get_or_fetch
        farm_service.get_or_fetch = _stub_get_or_fetch
        self.farm = farm_service.create_farm(
            self.db, 1, 1, "4615012300", 1, date(2026, 3, 1), "내 사과밭"
        )

    def tearDown(self):
        farm_service.get_or_fetch = self._real_get_or_fetch
        self.db.close()

    def _soil_source(self) -> str | None:
        soil = self.db.query(SoilState).filter(SoilState.user_farm_id == self.farm.id).first()
        return soil.base_source if soil else None

    def test_create_stores_bjd_code_and_soil_basis(self):
        self.assertEqual(self.farm.bjd_code, "4615012300")
        self.assertEqual(self._soil_source(), "stub(4615012300,4)")

    def test_planting_date_only_keeps_soil(self):
        # 파종일은 토양 기준값과 무관 → 재조회하지 않는다(불필요한 외부 호출 방지).
        farm_service.update_farm(self.db, 1, self.farm.id, {"planting_date": date(2026, 4, 5)})
        self.assertEqual(self.farm.planting_date, date(2026, 4, 5))
        self.assertEqual(self._soil_source(), "stub(4615012300,4)")

    def test_district_change_reinitializes_soil(self):
        farm_service.update_farm(self.db, 1, self.farm.id, {"bjd_code": "4615012400"})
        self.assertEqual(self._soil_source(), "stub(4615012400,4)")
        # 밭당 1행 유지(unique) — 지우고 다시 넣는다.
        self.assertEqual(self.db.query(SoilState).count(), 1)

    def test_crop_change_to_same_field_type_keeps_soil(self):
        # 사과→배는 둘 다 과수(4) → 같은 (읍면동, 경지구분)이라 값이 동일하다.
        farm_service.update_farm(self.db, 1, self.farm.id, {"crop_id": 2})
        self.assertEqual(self._soil_source(), "stub(4615012300,4)")

    def test_crop_change_to_other_field_type_reinitializes_soil(self):
        # 사과(과수 4)→감자(밭 2): 같은 동네라도 표본이 달라 기준값이 바뀐다.
        farm_service.update_farm(self.db, 1, self.farm.id, {"crop_id": 4})
        self.assertEqual(self._soil_source(), "stub(4615012300,2)")

    def test_region_change_requires_matching_district(self):
        with self.assertRaises(AppError) as ctx:
            farm_service.update_farm(self.db, 1, self.farm.id, {"region_id": 2})
        # 읍면동 없이 시/군만 바꾸면 옛 읍면동이 새 시/군에 속하지 않아 조합이 깨진다.
        self.assertEqual(ctx.exception.code, "DISTRICT_REGION_MISMATCH")

        farm_service.update_farm(
            self.db, 1, self.farm.id, {"region_id": 2, "bjd_code": "5279025000"}
        )
        self.assertEqual(self.farm.region_id, 2)
        self.assertEqual(self._soil_source(), "stub(5279025000,4)")

    def test_unknown_field_rejected(self):
        with self.assertRaises(AppError) as ctx:
            farm_service.update_farm(self.db, 1, self.farm.id, {"user_id": 99})
        self.assertEqual(ctx.exception.code, "FIELD_NOT_EDITABLE")

    def test_other_user_cannot_update_or_delete(self):
        for call in (
            lambda: farm_service.update_farm(self.db, 2, self.farm.id, {"crop_id": 4}),
            lambda: farm_service.delete_farm(self.db, 2, self.farm.id),
        ):
            with self.assertRaises(AppError) as ctx:
                call()
            self.assertEqual(ctx.exception.status_code, 404)  # 존재를 노출하지 않는다(§11)

    def test_delete_removes_farm(self):
        farm_service.delete_farm(self.db, 1, self.farm.id)
        self.assertEqual(self.db.query(UserFarm).count(), 0)


if __name__ == "__main__":
    unittest.main()
