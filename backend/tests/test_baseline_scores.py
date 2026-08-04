"""장기 탭 월별 전망(build_monthly_rows)의 v6 이전 baseline 점수 스냅샷 테스트.

**목적** (finalplan.md P0): 이후 P2(경계 성격별 점수)·P3(장기 총점 min 구조)에서 점수가
바뀐다. 그 변동이 의도한 것인지 회귀인지 구분하려면 변경 전 점수를 고정 스냅샷으로 남겨야
한다.

**DB 없이 돈다** — `CropGrowthGuide`·`CropGrowthStage`·`SoilState`·`WeatherClimatology`를
이 파일에서 코드로 직접 만든다(`test_monthly_outlook.py`와 같은 방식). 5작물의 지침·단계
값은 전부 마이그레이션 0001~0037을 직접 replay해 재확인한 값이다(추측 없음) — 근거는 각
상수 옆 주석의 마이그레이션 번호. `source_ref`·`confidence`는 스냅샷 점수에 영향이 없어 생략.

**대표 지역 3개는 실제 DB 지역이 아니라 테스트용 고정 프로파일이다**(DB 없이 돌리기 위한
불가피한 선택, 실제 지역 데이터가 아님을 여기 명시한다). 선정 근거:
- 기온 곡선 3종은 한국 기후 곡선(겨울 -2~2도, 여름 24~27도)을 흉내내면서, 오이 기온
  허용구간 하단(5~25도)·상추 기온 허용구간 하단(2.5~22도)·감자 tuber 단계 허용상한(27도)
  근처를 실제로 지나가게 잡았다(봄·가을철 값들이 그 구간에 들어간다) — P2가 바꾸는 지점이
  정확히 여기라, 스냅샷이 이 구간을 지나지 않으면 P2 변동을 못 잡는다.
- 토양 프로파일 3종은 최적구간(central)/허용구간(coastal)/허용경계 밖(mountain)을 각각
  대표한다. 작물마다 최적구간이 달라 5작물 전부에 대해 완벽히 그 등급으로 떨어지는 것은
  아니다(예: central 토양도 오이 p2o5·k는 risk로 나온다) — 실제 밭 데이터의 다양성과 같은
  성격이라 그대로 둔다.

**`corrections`는 비운다** — 장기예보 보정은 DB·발표시각에 의존해 스냅샷을 비결정론으로
만든다(이번 스냅샷의 목적은 보정 없는 평년치 baseline).

**스냅샷 재생성** (값 변동은 반드시 사람이 리뷰한 뒤 커밋할 것 — 회귀를 조용히 덮으면 안
된다):

    cd backend
    .venv/Scripts/python.exe -m tests.test_baseline_scores

pytest는 이 파일을 절대 덮어쓰지 않는다 — 재생성은 `if __name__ == "__main__"` 블록에서만
실행된다.
"""
import json
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from app.models import CropGrowthGuide, CropGrowthStage, SoilState, WeatherClimatology
from app.services.suitability_service import build_monthly_rows

SNAPSHOT_PATH = Path(__file__).parent / "fixtures" / "baseline_scores_pre_v6.json"

PLANTING = date(2026, 3, 20)
# outlook_window()를 쓰지 않는다 — 오늘 날짜에 묶이면 스냅샷이 재현 불가능해진다. 12개월을
# 직접 명시해 넘긴다(요구사항 §2).
FULL_YEAR = [(2026, m) for m in range(1, 13)]


def _guide(
    crop_id: int,
    stage: str | None,
    indicator: str,
    optimal_min: float | None,
    optimal_max: float | None,
    allowed_min: float | None,
    allowed_max: float | None,
    weight: float,
    risk_width: float | None = None,
) -> CropGrowthGuide:
    return CropGrowthGuide(
        crop_id=crop_id,
        growth_stage=stage,
        indicator=indicator,
        optimal_min=optimal_min,
        optimal_max=optimal_max,
        allowed_min=allowed_min,
        allowed_max=allowed_max,
        weight=weight,
        risk_width=risk_width,
    )


def _stage(crop_id: int, stage: str, mode: str, start: int, end: int, priority: int) -> CropGrowthStage:
    return CropGrowthStage(
        crop_id=crop_id, growth_stage=stage, mode=mode, range_start=start, range_end=end, priority=priority
    )


# ---------------------------------------------------------------------------
# crop_growth_guide 최종 상태 (0001~0037 replay 재확인, crop_id는 0003 시드 기준
# 1=사과 2=배 3=오이 4=감자 5=상추). 각 지표의 근거 마이그레이션은 옆 주석 참고.
# 삭제된 행 2개는 넣지 않는다 — 사과 coloring temp_night_min(0021 삭제),
# 감자 NULL rainfall_monthly(0013 삭제, 이후 어떤 크롭도 rainfall_monthly 지표가 없다).
# ---------------------------------------------------------------------------

APPLE_GUIDES = [
    _guide(1, "fruit_growth", "temp_day", 18, 24, 15, 31, 2.0, 2.219),  # 0004+0012+0021, rw 0023
    _guide(1, "maturity", "temp_day", 20, 25, 17.5, 27.5, 1.5, 2.219),  # 0004+0021, rw 0023
    _guide(1, "coloring", "temp_day", 12, 13, 11.5, 13.5, 1.0, 2.219),  # 0004+0021, rw 0023
    _guide(1, None, "organic", 25, 35, 20, 40, 1.0, 9.2069),  # 0023 (0004+0021 값을 대체)
    _guide(1, None, "p2o5", 200, 300, 150, 350, 1.0, 275.3322),  # 0023 (0004+0021 값을 대체)
    _guide(1, None, "ph", 6.0, 6.5, 5.75, 6.75, 1.5, 0.4641),  # 0023 (0012 값을 대체)
    _guide(1, None, "rainfall_daily", 0, 30, None, 50, 1.5, None),  # 0012, rw 없음(0020 대상 아님)
    _guide(1, None, "k", 0.3, 0.6, 0.15, 0.75, 1.0, 0.5041),  # 0024 신설 후 0035가 0.6/0.9→0.3/0.6로 교체
    _guide(1, None, "ca", 5.0, 6.0, 4.5, 6.5, 1.0, 3.7777),  # 0024 신설 → 0030 단측화 → 0035가 양측 복귀
    _guide(1, None, "mg", 1.5, 2.0, 1.25, 2.25, 1.0, 1.2632),  # 0024
]

PEAR_GUIDES = [
    _guide(2, "growing", "temp_day", 18.5, 21.5, 17, 23, 2.0, 2.219),  # 0004(0015가 단계 범위만 확장), rw 0023
    _guide(2, None, "ph", 6.0, 6.5, 5.75, 6.75, 1.5, 0.4641),  # 0012 신설 → 0023이 교체
    _guide(2, None, "organic", 25, 35, 20, 40, 1.0, 9.2069),  # 0023 신설
    _guide(2, None, "p2o5", 200, 300, 150, 350, 1.0, 275.3322),  # 0023 신설
    _guide(2, None, "rainfall_daily", 0, 30, None, 50, 1.5, None),  # 0012
    _guide(2, None, "k", 0.3, 0.6, 0.15, 0.75, 1.0, 0.5041),  # 0024
    _guide(2, None, "ca", 5.0, 6.0, 4.5, 6.5, 1.0, 3.7777),  # 0024
    _guide(2, None, "mg", 1.5, 2.0, 1.25, 2.25, 1.0, 1.2632),  # 0024
]

CUCUMBER_GUIDES = [
    _guide(3, "growing", "temp_day", 25, 28, 5, 35, 2.0, 2.219),  # 0019(전기간→growing 이동), rw 0023
    _guide(3, None, "ph", 6.0, 6.5, 5.5, 6.8, 1.5, 0.4641),  # 0019 신설 → 0031이 6.0/6.5/5.5/6.8로 교체
    _guide(3, None, "rainfall_daily", 0, 30, None, 50, 1.5, None),  # 0012
    _guide(3, None, "organic", 20, 30, 15, 35, 1.0, 9.2069),  # 0031 신설
    _guide(3, None, "p2o5", 400, 500, 350, 550, 1.0, 275.3322),  # 0031 신설
    _guide(3, None, "k", 0.7, 0.8, 0.65, 0.85, 1.0, 0.5041),  # 0031 신설
    _guide(3, None, "ca", 5.0, 6.0, 4.5, 6.5, 1.0, 3.7777),  # 0031 신설
    _guide(3, None, "mg", 1.5, 2.0, 1.25, 2.25, 1.0, 1.2632),  # 0031 신설
    _guide(3, None, "ec", 0.0, 2.0, 0.0, 3.0, 1.0, 0.3855),  # 0028 신설
]

POTATO_GUIDES = [
    _guide(4, "early", "temp_day", 14, 23, -3, 27, 1.5, 2.219),  # 0004+0012, rw 0023
    _guide(4, "tuber", "temp_day", 23, 24, None, 27, 2.5, 2.219),  # 0004, rw 0023 (단계 범위는 0026이 46~112로 축소)
    _guide(4, "tuber", "temp_night_min", 10, 14, None, 28, 2.0, None),  # 0004+0012, rw 없음
    _guide(4, None, "rainfall_daily", 0, 30, None, 50, 1.5, None),  # 0012 (0004 rainfall/rainfall_monthly는 0013이 삭제)
    _guide(4, None, "organic", 20, 30, 15, 35, 1.0, 9.2069),  # 0019/0027 신설(30/47/10/55.5) → 0035가 교체
    _guide(4, None, "ph", 5.5, 7.0, 4.75, 7.75, 1.5, 0.4641),  # 0031 신설(5.0/6.0/4.5/6.5) → 0035가 교체
    _guide(4, None, "p2o5", 250, 350, 200, 400, 1.0, 275.3322),  # 0031 신설
    _guide(4, None, "k", 0.5, 0.6, 0.45, 0.65, 1.0, 0.5041),  # 0031 신설
    _guide(4, None, "ca", 4.5, 5.5, 4.0, 6.0, 1.0, 3.7777),  # 0031 신설
    _guide(4, None, "mg", 1.5, 2.0, 1.25, 2.25, 1.0, 1.2632),  # 0031 신설
    _guide(4, None, "ec", 0.0, 2.0, 0.0, 3.0, 1.0, 0.3855),  # 0028 신설
]

LETTUCE_GUIDES = [
    _guide(5, "spring", "temp_day", 22, 24, 2.5, 36, 2.0, 2.219),  # 0019 값을 0025가 spring/fall로 분리, rw 0023
    _guide(5, "fall", "temp_day", 22, 24, 2.5, 36, 2.0, 2.219),
    _guide(5, None, "ph", 6.5, 7.0, 6.25, 7.25, 1.5, 0.4641),  # 0019 신설
    _guide(5, None, "p2o5", 250, 400, 175, 475, 1.0, 275.3322),  # 0019 신설
    _guide(5, None, "rainfall_daily", 0, 30, None, 50, 1.5, None),  # 0012
    _guide(5, None, "k", 0.4, 0.6, 0.3, 0.7, 1.0, 0.5041),  # 0024 신설
    _guide(5, None, "ca", 6.0, 7.0, 5.5, 7.5, 1.0, 3.7777),  # 0024 신설
    _guide(5, None, "mg", 2.0, 2.5, 1.75, 2.75, 1.0, 1.2632),  # 0024 신설
    _guide(5, None, "organic", 20, 30, 15, 35, 1.0, 9.2069),  # 0029 신설
    _guide(5, None, "ec", 0.0, 2.0, 0.0, 2.9, 1.0, 0.3855),  # 0028 신설(5작물 중 상추만 allowed_max 2.9)
]

# ---------------------------------------------------------------------------
# crop_growth_stage 최종 상태 (0007+0015+0019+0025+0026 replay 재확인).
# ---------------------------------------------------------------------------

APPLE_STAGES = [
    _stage(1, "fruit_growth", "day_of_year", 111, 263, 1),
    _stage(1, "coloring", "day_of_year", 233, 293, 2),
    _stage(1, "maturity", "day_of_year", 294, 314, 3),
]
PEAR_STAGES = [_stage(2, "growing", "day_of_year", 91, 304, 1)]  # 0007의 121~293을 0015가 확장
CUCUMBER_STAGES = [_stage(3, "growing", "day_of_year", 91, 273, 1)]  # 0019 신설
POTATO_STAGES = [
    _stage(4, "early", "days_after_planting", 0, 45, 1),
    _stage(4, "tuber", "days_after_planting", 46, 112, 2),  # 0007의 120을 0026이 112로 축소
]
LETTUCE_STAGES = [
    _stage(5, "spring", "day_of_year", 60, 181, 1),  # 0025 신설
    _stage(5, "fall", "day_of_year", 213, 334, 2),
]

# crop_id → (한글명, 단계 행, 지침 행). 0003 시드의 crop_id 배정과 동일.
CROPS: dict[int, tuple[str, list[CropGrowthStage], list[CropGrowthGuide]]] = {
    1: ("사과", APPLE_STAGES, APPLE_GUIDES),
    2: ("배", PEAR_STAGES, PEAR_GUIDES),
    3: ("오이", CUCUMBER_STAGES, CUCUMBER_GUIDES),
    4: ("감자", POTATO_STAGES, POTATO_GUIDES),
    5: ("상추", LETTUCE_STAGES, LETTUCE_GUIDES),
}


# ---------------------------------------------------------------------------
# 대표 지역 3개(테스트용 고정 프로파일 — 실제 DB 지역 아님, 모듈 docstring 참고).
# 월별 배열은 1~12월 순서.
# ---------------------------------------------------------------------------

def _clim_by_month(
    region_id: int, temps: list[float], nights: list[float], rains: list[float], suns: list[float]
) -> dict[int, WeatherClimatology]:
    return {
        month: WeatherClimatology(
            region_id=region_id,
            month=month,
            temp_avg_normal=Decimal(str(temps[month - 1])),
            temp_night_min_normal=Decimal(str(nights[month - 1])),
            rainfall_normal=Decimal(str(rains[month - 1])),  # mm/월
            sunlight_normal=Decimal(str(suns[month - 1])),  # hr/월
            source="test_fixture_baseline_pre_v6",
        )
        for month in range(1, 13)
    }


# 표준형(중부내륙 근사). 겨울 -2~0도·여름 26~27도로 한국 기후 곡선 범위를 훑고, 3~5월·9월이
# 오이 허용구간 하단(5~25도)·상추 허용구간 하단(2.5~22도)을 지나간다.
_CENTRAL_TEMP = [-2, 0, 6, 13, 18, 22, 26, 27, 22, 15, 7, 0]
_CENTRAL_NIGHT = [-7, -5, 1, 8, 13, 17, 21, 22, 17, 10, 2, -5]
_CENTRAL_RAIN = [22, 28, 45, 70, 90, 140, 290, 260, 130, 45, 40, 25]
_CENTRAL_SUN = [180, 170, 190, 200, 210, 150, 120, 140, 180, 200, 180, 170]

# 해안형(남부 근사). 겨울이 더 온화하고 강수가 더 많다.
_COASTAL_TEMP = [2, 3, 8, 14, 19, 22, 25, 26, 23, 17, 10, 4]
_COASTAL_NIGHT = [-2, -1, 3, 9, 14, 17, 20, 21, 18, 12, 5, 0]
_COASTAL_RAIN = [30, 35, 55, 80, 100, 160, 300, 270, 150, 55, 45, 30]
_COASTAL_SUN = [160, 160, 180, 190, 200, 140, 110, 130, 170, 190, 170, 160]

# 산간형(고지 근사). 연교차가 크고 여름 최고기온이 감자 tuber 허용상한(27도) 근처를 지나간다.
_MOUNTAIN_TEMP = [-5, -3, 2, 10, 16, 20, 24, 24, 18, 11, 3, -3]
_MOUNTAIN_NIGHT = [-10, -8, -3, 4, 9, 14, 18, 18, 12, 4, -3, -8]
_MOUNTAIN_RAIN = [15, 20, 35, 55, 70, 110, 220, 200, 100, 35, 30, 18]
_MOUNTAIN_SUN = [190, 185, 200, 210, 215, 160, 130, 150, 190, 210, 195, 185]

# 토양 3종 — 최적구간 / 허용구간 / 허용경계 밖. 작물마다 최적구간이 달라 모든 지표가 그
# 등급대로 떨어지는 건 아니다(모듈 docstring 참고) — 그래도 대다수 지표는 의도한 등급에 든다.
SOIL_OPTIMAL = SoilState(
    user_farm_id=1, ph=Decimal("6.3"), ec=Decimal("1.0"), p2o5=Decimal("280"),
    organic_matter=Decimal("27"), k=Decimal("0.55"), ca=Decimal("5.5"), mg=Decimal("1.8"),
    base_source="test_fixture_baseline_pre_v6",
)
SOIL_ALLOWED = SoilState(
    user_farm_id=2, ph=Decimal("6.7"), ec=Decimal("2.5"), p2o5=Decimal("180"),
    organic_matter=Decimal("33"), k=Decimal("0.65"), ca=Decimal("6.3"), mg=Decimal("1.4"),
    base_source="test_fixture_baseline_pre_v6",
)
SOIL_RISK = SoilState(
    user_farm_id=3, ph=Decimal("4.5"), ec=Decimal("4.0"), p2o5=Decimal("80"),
    organic_matter=Decimal("8"), k=Decimal("1.5"), ca=Decimal("1.0"), mg=Decimal("0.5"),
    base_source="test_fixture_baseline_pre_v6",
)

REGIONS: list[dict[str, object]] = [
    {
        "key": "central_soil_optimal",
        "clim": _clim_by_month(101, _CENTRAL_TEMP, _CENTRAL_NIGHT, _CENTRAL_RAIN, _CENTRAL_SUN),
        "soil": SOIL_OPTIMAL,
    },
    {
        "key": "coastal_soil_allowed",
        "clim": _clim_by_month(102, _COASTAL_TEMP, _COASTAL_NIGHT, _COASTAL_RAIN, _COASTAL_SUN),
        "soil": SOIL_ALLOWED,
    },
    {
        "key": "mountain_soil_risk",
        "clim": _clim_by_month(103, _MOUNTAIN_TEMP, _MOUNTAIN_NIGHT, _MOUNTAIN_RAIN, _MOUNTAIN_SUN),
        "soil": SOIL_RISK,
    },
]

RECORD_KEY_FIELDS = ("crop_id", "region", "year", "month")


def _build_records() -> list[dict[str, object]]:
    """corrections 없이(장기예보 보정 비결정론 배제) 5작물 x 3지역 x 12개월을 계산한다."""
    records: list[dict[str, object]] = []
    for crop_id, (name, stages, guides) in CROPS.items():
        for region in REGIONS:
            rows = build_monthly_rows(stages, guides, region["clim"], region["soil"], PLANTING, FULL_YEAR)
            for row in rows:
                records.append(
                    {
                        "crop_id": crop_id,
                        "crop_name": name,
                        "region": region["key"],
                        "year": row["year"],
                        "month": row["month"],
                        "growth_stage": row["growth_stage"],
                        "status": row["status"],
                        "score": row["score"],
                        "grade": row["grade"],
                        "risk_flags": row["risk_flags"],
                        # 지표별 점수 — P2·P3가 어느 지표를 바꿨는지 스냅샷에서 읽을 수 있게.
                        "indicator_scores": {
                            indicator: entry.get("score")
                            for indicator, entry in row["breakdown"].items()
                        },
                    }
                )
    return records


def build_snapshot() -> dict[str, object]:
    return {
        "meta": {
            "note": (
                "v6 이전 baseline 스냅샷(finalplan.md P0). DB 없이 코드 픽스처로 산출 "
                "(test_baseline_scores.py 모듈 docstring 참고). 3개 지역은 테스트용 고정 "
                "프로파일이며 corrections는 비웠다(장기예보 보정 없음)."
            ),
            "window": [f"{y}-{m:02d}" for y, m in FULL_YEAR],
            "regions": [r["key"] for r in REGIONS],
        },
        "records": _build_records(),
    }


def _index(records: list[dict[str, object]]) -> dict[tuple[object, ...], dict[str, object]]:
    return {tuple(record[f] for f in RECORD_KEY_FIELDS): record for record in records}


class TestBaselineSnapshotExists(unittest.TestCase):
    def test_snapshot_file_exists_and_is_not_empty(self):
        """없으면 나머지 검증이 조용히 통과하는 것을 막는다."""
        self.assertTrue(
            SNAPSHOT_PATH.exists(),
            f"{SNAPSHOT_PATH} 없음 — 모듈 docstring의 재생성 명령을 먼저 실행할 것.",
        )
        data = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        self.assertIn("records", data)
        self.assertGreater(len(data["records"]), 0)


class TestBaselineSnapshotMatches(unittest.TestCase):
    def test_current_output_matches_snapshot(self):
        """현행 산출과 스냅샷이 완전 일치해야 한다. 불일치는 (작물,지역,연,월)별로 어느 필드가
        어떻게 달라졌는지 실패 메시지에 담는다 — P2·P3에서 이 메시지가 변동 설명서가 된다."""
        data = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        expected = _index(data["records"])
        current = _index(_build_records())

        mismatches: list[str] = []
        for key in sorted(set(expected) | set(current), key=lambda k: (k[0], k[1], k[2], k[3])):
            exp = expected.get(key)
            cur = current.get(key)
            crop_id, region, year, month = key
            label = f"crop={crop_id} region={region} {year}-{month:02d}"
            if exp is None:
                mismatches.append(f"{label}: 스냅샷에 없음(현행에만 존재)")
                continue
            if cur is None:
                mismatches.append(f"{label}: 현행에 없음(스냅샷에만 존재)")
                continue
            diffs = [
                f"{field}: {exp.get(field)!r} -> {cur.get(field)!r}"
                for field in ("score", "grade", "status", "growth_stage", "risk_flags", "indicator_scores")
                if exp.get(field) != cur.get(field)
            ]
            if diffs:
                mismatches.append(f"{label}: " + "; ".join(diffs))

        self.assertEqual([], mismatches, "\n" + "\n".join(mismatches))


if __name__ == "__main__":
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(json.dumps(build_snapshot(), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {SNAPSHOT_PATH} ({len(build_snapshot()['records'])} records)")
