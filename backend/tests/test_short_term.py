"""단기 탭 지속 위험 판정 검증(DB 없는 순수부).

"봄철 야간저온 3일 지속"이 A씨 사례의 실패 원인이라, 하루짜리 노이즈와 지속 위험을
구분하는 규칙이 이 탭의 핵심이다(PRD.md §4.5, §7-4).
"""
import unittest
from datetime import date, datetime
from decimal import Decimal

from app.infra.public_api.forecast_client import KST, DailyForecast
from app.services.short_term_service import (
    _merge_publications,
    _to_snapshot_rows,
    persistent_risks,
)


def _day(d: str, *flags: str) -> dict[str, object]:
    return {"target_date": d, "risk_flags": list(flags)}


def _forecast(**over: object) -> DailyForecast:
    base: dict[str, object] = {
        "target_date": date(2026, 8, 4),
        "temp_avg": Decimal("31.3"),
        "temp_max": Decimal("38"),
        "temp_night_min": Decimal("27"),
        "rainfall": Decimal("0"),
        "precip_prob_max": 20,
        "humidity_max": 80,
        "hourly_temp": [{"h": 15, "t": "38"}],
        "is_partial": False,
    }
    base.update(over)
    return DailyForecast(**base)  # type: ignore[arg-type]


class TestToSnapshotRows(unittest.TestCase):
    """DailyForecast → weather_snapshot 행 매핑. 컬럼을 빠뜨리면 조용히 NULL로 저장된다."""

    def test_maps_new_temperature_columns(self):
        row = _to_snapshot_rows(7, datetime(2026, 8, 4, 14, tzinfo=KST), [_forecast()])[0]
        self.assertEqual(row["temp_avg"], Decimal("31.3"))
        self.assertEqual(row["temp_max"], Decimal("38"))
        self.assertEqual(row["temp_night_min"], Decimal("27"))
        self.assertEqual(row["hourly_temp"], [{"h": 15, "t": "38"}])

    def test_partial_flag_lands_in_is_imputed(self):
        """부분 표본으로 낸 집계는 §12의 "대체됨"이다 — 기존 컬럼을 재사용한다."""
        rows = _to_snapshot_rows(
            7,
            datetime(2026, 8, 4, 14, tzinfo=KST),
            [_forecast(is_partial=True), _forecast(target_date=date(2026, 8, 5))],
        )
        self.assertEqual([r["is_imputed"] for r in rows], [True, False])

    def test_sunlight_stays_null(self):
        """단기예보는 일조를 주지 않는다 — 0으로 채우면 '일조 없음'으로 오해된다."""
        row = _to_snapshot_rows(7, datetime(2026, 8, 4, 14, tzinfo=KST), [_forecast()])[0]
        self.assertIsNone(row["sunlight"])


class TestPersistentRisks(unittest.TestCase):
    def test_flags_repeated_risk(self):
        days = [
            _day("2026-04-01", "temp_night_min:outside_allowed"),
            _day("2026-04-02", "temp_night_min:outside_allowed"),
            _day("2026-04-03", "temp_night_min:outside_allowed"),
        ]
        risks = persistent_risks(days)
        self.assertEqual(len(risks), 1)
        self.assertEqual(risks[0]["flag"], "temp_night_min:outside_allowed")
        self.assertEqual(risks[0]["days"], 3)
        self.assertEqual(risks[0]["dates"], ["2026-04-01", "2026-04-02", "2026-04-03"])

    def test_single_day_risk_is_not_persistent(self):
        """하루만 스치는 값으로 경보를 울리면 신뢰를 잃는다."""
        days = [_day("2026-04-01", "rainfall_daily:outside_allowed"), _day("2026-04-02")]
        self.assertEqual(persistent_risks(days), [])

    def test_only_outside_allowed_counts(self):
        """결측(missing)은 위험이 아니라 데이터 없음이다 — 경보 대상이 아니다."""
        days = [
            _day("2026-04-01", "temp_night_min:missing", "sunlight:missing"),
            _day("2026-04-02", "temp_night_min:missing", "sunlight:missing"),
        ]
        self.assertEqual(persistent_risks(days), [])

    def test_soil_risks_are_excluded(self):
        """토양은 며칠 안에 변하지 않아 매일 뜬다 — "유기물 5일 지속"은 정보가 없는 경보다.

        실측 사례: 순천 사과밭 조회 시 organic/p2o5만 5일 지속으로 올라와 기상 위험을 가렸다.
        """
        days = [
            _day("2026-07-25", "organic:outside_allowed", "p2o5:outside_allowed"),
            _day("2026-07-26", "organic:outside_allowed", "p2o5:outside_allowed"),
            _day("2026-07-27", "organic:outside_allowed", "p2o5:outside_allowed"),
        ]
        self.assertEqual(persistent_risks(days), [])

    def test_weather_risk_survives_alongside_soil_risk(self):
        days = [
            _day("2026-04-01", "organic:outside_allowed", "temp_night_min:outside_allowed"),
            _day("2026-04-02", "organic:outside_allowed", "temp_night_min:outside_allowed"),
        ]
        risks = persistent_risks(days)
        self.assertEqual([r["flag"] for r in risks], ["temp_night_min:outside_allowed"])

    def test_multiple_risks_sorted_by_duration(self):
        days = [
            _day("2026-04-01", "temp_night_min:outside_allowed", "rainfall_daily:outside_allowed"),
            _day("2026-04-02", "temp_night_min:outside_allowed", "rainfall_daily:outside_allowed"),
            _day("2026-04-03", "temp_night_min:outside_allowed"),
        ]
        risks = persistent_risks(days)
        self.assertEqual([r["flag"] for r in risks], [
            "temp_night_min:outside_allowed",
            "rainfall_daily:outside_allowed",
        ])
        self.assertEqual([r["days"] for r in risks], [3, 2])

    def test_duplicate_flags_within_a_day_count_once(self):
        """같은 날 같은 플래그가 중복돼도 하루로 센다(지속 일수가 부풀지 않게)."""
        days = [
            _day("2026-04-01", "temp_night_min:outside_allowed", "temp_night_min:outside_allowed"),
            _day("2026-04-02", "temp_night_min:outside_allowed"),
        ]
        self.assertEqual(persistent_risks(days)[0]["days"], 2)

    def test_empty_input_is_safe(self):
        self.assertEqual(persistent_risks([]), [])

    def test_is_deterministic(self):
        days = [
            _day("2026-04-01", "temp_night_min:outside_allowed"),
            _day("2026-04-02", "temp_night_min:outside_allowed"),
        ]
        self.assertEqual(persistent_risks(days), persistent_risks(days))


class _Snap:
    """`weather_snapshot` 행 대역. 병합은 순수 함수라 DB 없이 검증한다."""

    def __init__(self, hour: int, **over: object):
        self.base_at = datetime(2026, 8, 4, hour, tzinfo=KST)
        self.target_date = date(2026, 8, 4)
        self.temp_avg: Decimal | None = None
        self.temp_max: Decimal | None = None
        self.temp_night_min: Decimal | None = None
        self.rainfall: Decimal | None = None
        self.sunlight: Decimal | None = None
        self.hourly_temp: list[dict[str, object]] | None = None
        self.is_imputed = False
        for key, value in over.items():
            setattr(self, key, value)


def _hours(*pairs: tuple[int, str]) -> list[dict[str, object]]:
    return [{"h": h, "t": t} for h, t in pairs]


class TestMergePublications(unittest.TestCase):
    """발표분 병합 — "오늘 데이터가 최신화되며 날아간다"의 수정 지점.

    단기예보 첫날은 발표시각 이후만 오므로(14시 발표 → 15~23시) 최신 발표분만 읽으면 이미
    지난 새벽·오전이 사라진다. 지난 시간대는 이전 발표에만 있다.
    """

    def test_keeps_earlier_hours_the_new_publication_dropped(self):
        early = _Snap(2, hourly_temp=_hours((3, "18"), (4, "17")))
        late = _Snap(14, hourly_temp=_hours((15, "31"), (16, "30")))
        merged = _merge_publications([early, late])
        self.assertEqual([s["h"] for s in merged.hourly_temp or []], [3, 4, 15, 16])

    def test_newest_publication_wins_on_overlapping_hour(self):
        """겹치는 시각은 최신 예보가 이긴다 — 오래된 값을 남기면 갱신이 무의미해진다."""
        early = _Snap(2, hourly_temp=_hours((15, "28")))
        late = _Snap(14, hourly_temp=_hours((15, "31")))
        self.assertEqual(_merge_publications([early, late]).hourly_temp, [{"h": 15, "t": "31"}])

    def test_order_of_input_does_not_matter(self):
        """호출 순서가 결과를 바꾸면 안 된다(결정론, CLAUDE.md §2) — base_at으로 정렬한다."""
        early = _Snap(2, hourly_temp=_hours((15, "28")))
        late = _Snap(14, hourly_temp=_hours((15, "31")))
        self.assertEqual(
            _merge_publications([late, early]).hourly_temp,
            _merge_publications([early, late]).hourly_temp,
        )

    def test_extremes_take_the_riskier_side(self):
        """엇갈리면 위험 쪽(최고는 높게·최저는 낮게·강수는 많게). 놓친 경고는 알릴 방법이 없다."""
        early = _Snap(
            2, temp_max=Decimal("35"), temp_night_min=Decimal("12"), rainfall=Decimal("20")
        )
        late = _Snap(
            14, temp_max=Decimal("31"), temp_night_min=Decimal("18"), rainfall=Decimal("2")
        )
        merged = _merge_publications([early, late])
        self.assertEqual(merged.temp_max, Decimal("35"))
        self.assertEqual(merged.temp_night_min, Decimal("12"))
        # 오전에 이미 내린 비가 남은 시간대만 담은 최신 발표로 덮이면 일누적이 줄어든다.
        self.assertEqual(merged.rainfall, Decimal("20"))

    def test_temp_avg_is_mean_of_merged_hours(self):
        """채점 입력(temp_day)은 합친 표본의 평균이다 — 최신 발표분 평균은 오후로 편향돼 있다."""
        early = _Snap(2, temp_avg=Decimal("17.5"), hourly_temp=_hours((3, "17"), (4, "18")))
        late = _Snap(14, temp_avg=Decimal("30.5"), hourly_temp=_hours((15, "30"), (16, "31")))
        self.assertEqual(_merge_publications([early, late]).temp_avg, Decimal("24.0"))

    def test_coverage_is_rejudged_after_merge(self):
        """발표분 각각은 부분이어도 합치면 온전할 수 있다 — 그때 '일부 시간대'를 떼야 한다."""
        early = _Snap(2, is_imputed=True, hourly_temp=_hours(*[(h, "20") for h in range(0, 15)]))
        late = _Snap(14, is_imputed=True, hourly_temp=_hours(*[(h, "25") for h in range(15, 24)]))
        self.assertFalse(_merge_publications([early, late]).is_imputed)

    def test_still_partial_when_early_hours_are_missing_everywhere(self):
        """자정~첫 수집 시각은 어느 발표에도 없다 — 그 결손은 숨기지 않는다(§18-4)."""
        late = _Snap(14, is_imputed=True, hourly_temp=_hours(*[(h, "25") for h in range(15, 24)]))
        self.assertTrue(_merge_publications([late]).is_imputed)

    def test_single_publication_is_not_flagged_as_merged(self):
        self.assertFalse(_merge_publications([_Snap(14)]).is_merged)
        self.assertTrue(_merge_publications([_Snap(2), _Snap(14)]).is_merged)

    def test_base_at_is_the_newest_publication(self):
        """화면의 "○시 발표"와 신선도 판정이 이 값을 쓴다 — 오래된 쪽을 쓰면 캐시가 매번 만료된다."""
        merged = _merge_publications([_Snap(2), _Snap(14)])
        self.assertEqual(merged.base_at, datetime(2026, 8, 4, 14, tzinfo=KST))

    def test_broken_hourly_slots_are_skipped_not_fatal(self):
        """JSONB는 타입이 느슨하다 — 슬롯 하나가 깨져도 산출이 죽지 않아야 한다(§12)."""
        junk = _Snap(
            2,
            hourly_temp=[
                {"h": 3, "t": "18"},
                {"h": "네시", "t": "17"},
                {"h": 5, "t": "없음"},
                "이건 dict가 아니다",
                {"h": 99, "t": "20"},
            ],
        )
        merged = _merge_publications([junk])
        self.assertEqual(merged.hourly_temp, [{"h": 3, "t": "18"}])

    def test_no_hourly_anywhere_falls_back_to_newest_values(self):
        """0032 이전 캐시는 hourly_temp가 NULL이다 — 그 구역에서도 값이 나와야 한다."""
        merged = _merge_publications(
            [_Snap(2, temp_avg=Decimal("17")), _Snap(14, temp_avg=Decimal("30"))]
        )
        self.assertEqual(merged.temp_avg, Decimal("30"))
        self.assertIsNone(merged.hourly_temp)


if __name__ == "__main__":
    unittest.main()
