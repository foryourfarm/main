"""단기 탭 읽기 경로(`_cached_rows`) — 3일 창 + 발표분 병합의 DB 경계 검증.

Postgres 없이 sqlite 인메모리에 `weather_snapshot` 테이블만 만들어 돌린다. 검증 대상이
"어느 행을 골라 어떻게 합치나"라 DB 종류와 무관하다.

여기서 잡는 회귀 두 개:
  1. 카드가 4~5장 나오던 것(기상청 한 발표가 +4일까지 준다) → 오늘·내일·모레 3장.
  2. 새 발표를 받으면 오늘 값이 퇴화하던 것 → 지난 시간대를 이전 발표에서 살려온다.

실행: backend/.venv/Scripts/python.exe -m unittest tests.test_short_term_cache_window
"""

import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.infra.public_api.forecast_client import KST
from app.models import WeatherSnapshot
from app.services.short_term_service import KIND_FORECAST, _cached_rows


# JSONB는 Postgres 전용이다 — 테스트 엔진에서만 TEXT로 컴파일한다(운영 스키마엔 영향 없음).
# hourly_temp는 이 테스트에서 파이썬 리스트로 넣고 읽으므로 직렬화 형식은 상관없다.
@compiles(JSONB, "sqlite")
def _jsonb_as_text_on_sqlite(element, compiler, **kw):
    return "TEXT"


TODAY = date(2026, 8, 4)
REGION = 7


def _hours(start: int, end: int, temp: str) -> list[dict[str, object]]:
    """[start, end] 시각 슬롯. 실제 예보와 같은 `{"h": 시각, "t": "기온"}` 형태."""
    return [{"h": h, "t": temp} for h in range(start, end + 1)]


class TestCachedRowsWindow(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        WeatherSnapshot.__table__.create(self.engine)
        self.db = Session(self.engine)

    def tearDown(self):
        self.db.close()

    def _add(self, base_at: datetime, target: date, **over: object) -> None:
        row = WeatherSnapshot(
            region_id=REGION,
            kind=KIND_FORECAST,
            base_at=base_at,
            target_date=target,
            is_imputed=bool(over.pop("is_imputed", False)),
            **over,  # type: ignore[arg-type]
        )
        self.db.add(row)
        self.db.commit()

    def test_returns_three_days_and_drops_the_rest(self):
        """한 발표가 +4일까지 줘도 카드는 오늘·내일·모레 3장이다."""
        base = datetime(2026, 8, 4, 14, tzinfo=KST)
        for offset in range(5):
            self._add(base, TODAY + timedelta(days=offset), temp_avg=Decimal("25"))
        days = _cached_rows(self.db, REGION, TODAY)
        self.assertEqual(
            [d.target_date for d in days],
            [TODAY, TODAY + timedelta(days=1), TODAY + timedelta(days=2)],
        )

    def test_past_dates_are_not_returned(self):
        """어제 날짜 행은 캐시에 남아 있어도 카드로 나가지 않는다."""
        base = datetime(2026, 8, 4, 14, tzinfo=KST)
        self._add(base, TODAY - timedelta(days=1), temp_avg=Decimal("20"))
        self._add(base, TODAY, temp_avg=Decimal("25"))
        self.assertEqual([d.target_date for d in _cached_rows(self.db, REGION, TODAY)], [TODAY])

    def test_today_keeps_morning_hours_after_a_new_publication(self):
        """**핵심 회귀**: 14시 발표로 갈아타도 오전이 살아 있어야 한다.

        어제 23시 발표가 오늘 하루 전체(00~23시)를 예보했고, 오늘 14시 발표는 15~23시만 준다.
        종전 구현은 최신 발표분만 읽어 00~14시를 버렸다.
        """
        self._add(
            datetime(2026, 8, 3, 23, tzinfo=KST),
            TODAY,
            temp_avg=Decimal("24"),
            temp_night_min=Decimal("19"),
            rainfall=Decimal("12"),
            hourly_temp=_hours(0, 23, "24"),
        )
        self._add(
            datetime(2026, 8, 4, 14, tzinfo=KST),
            TODAY,
            temp_avg=Decimal("30"),
            temp_night_min=Decimal("28"),  # 새벽이 표본에서 빠져 "야간 최저"가 오후 최저로 튄다
            rainfall=Decimal("1"),
            hourly_temp=_hours(15, 23, "30"),
            is_imputed=True,
        )
        today = _cached_rows(self.db, REGION, TODAY)[0]

        self.assertEqual([s["h"] for s in today.hourly_temp or []], list(range(24)))
        self.assertEqual(today.temp_night_min, Decimal("19"))  # 새벽값이 살아 있다
        self.assertEqual(today.rainfall, Decimal("12"))  # 오전에 온 비가 남아 있다
        self.assertFalse(today.is_imputed)  # 합치면 하루가 온전해진다
        self.assertTrue(today.is_merged)  # 합쳤다는 사실은 화면에 표기된다
        # 발표시각 표기는 최신 발표를 따른다. sqlite는 tzinfo를 보존하지 않으므로(운영 Postgres는
        # timestamptz로 유지한다) 시각만 비교한다 — 여기서 볼 것은 "둘 중 최신을 골랐나"다.
        self.assertEqual(today.base_at.replace(tzinfo=None), datetime(2026, 8, 4, 14))

    def test_publications_older_than_a_day_from_the_newest_are_excluded(self):
        """최신 발표보다 하루 넘게 오래된 발표는 뺀다 — 위험 쪽 극값 규칙 때문에 낡은 경고가
        되살아난다."""
        self._add(
            datetime(2026, 8, 2, 14, tzinfo=KST), TODAY, temp_max=Decimal("41")
        )  # 이틀 전 발표
        self._add(datetime(2026, 8, 4, 14, tzinfo=KST), TODAY, temp_max=Decimal("30"))
        today = _cached_rows(self.db, REGION, TODAY)[0]
        self.assertEqual(today.temp_max, Decimal("30"))
        self.assertFalse(today.is_merged)

    def test_stale_only_cache_is_still_returned(self):
        """**회귀 방어**: 캐시가 전부 하루보다 낡아도 목록을 비우지 않는다.

        기준을 절대 날짜("어제 00시 이후")로 잡았더니 캐시가 낡은 지역에서 카드가 0장이 됐다
        (실측 region 145). 그러면 외부 API 장애 때 "마지막 캐시 + 최신 아님 고지"로 버티는
        §12 폴백이 사라진다 — 창은 **가장 최신 발표분 기준**으로 잡아야 한다.
        """
        self._add(datetime(2026, 7, 30, 14, tzinfo=KST), TODAY, temp_max=Decimal("33"))
        self._add(
            datetime(2026, 7, 30, 14, tzinfo=KST), TODAY + timedelta(days=1), temp_max=Decimal("34")
        )
        days = _cached_rows(self.db, REGION, TODAY)
        self.assertEqual([d.target_date for d in days], [TODAY, TODAY + timedelta(days=1)])
        self.assertEqual(days[0].temp_max, Decimal("33"))

    def test_other_regions_do_not_leak_in(self):
        base = datetime(2026, 8, 4, 14, tzinfo=KST)
        self._add(base, TODAY, temp_max=Decimal("30"))
        self.db.add(
            WeatherSnapshot(
                region_id=REGION + 1,
                kind=KIND_FORECAST,
                base_at=base,
                target_date=TODAY,
                temp_max=Decimal("40"),
            )
        )
        self.db.commit()
        self.assertEqual(_cached_rows(self.db, REGION, TODAY)[0].temp_max, Decimal("30"))

    def test_empty_cache_is_safe(self):
        self.assertEqual(_cached_rows(self.db, REGION, TODAY), [])


if __name__ == "__main__":
    unittest.main()
