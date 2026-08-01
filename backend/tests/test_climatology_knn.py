"""평년치 KNN 대체(거리역수 가중평균) 검증.

전부 DB 없이 돈다 — CI에 Postgres를 띄우지 않으므로(`.github/workflows/ci.yml`) 순수
계산부만 테스트한다. DB가 필요한 조회 경로는 `test_climatology_service.py` 담당.

교체 근거 수치는 `docs/ml/climatology_knn_validation.json`,
재현은 `scripts/validate_climatology_knn.py`.
"""
import unittest
from decimal import Decimal

from app.services.climatology_service import (
    BLENDED_FIELDS,
    ClimatologySource,
    MonthlyNormals,
    _apply_lapse_rate,
    _rank_donors,
    _weighted_normals,
    lapse_limitation,
    substitution_limitation,
)


class FakeGrid:
    def __init__(self, nx: int, ny: int, region_id: int = 0):
        self.nx = nx
        self.ny = ny
        self.region_id = region_id


class FakeRow:
    """WeatherClimatology 대역 — 가중평균이 읽는 필드만 갖는다.

    필드 목록을 베껴 적지 않고 `BLENDED_FIELDS`에서 가져온다. 종전엔 5개를 하드코딩해서
    `reference_altitude_m`이 추가됐을 때 대역만 뒤처져 AttributeError로 죽었다.
    """

    def __init__(self, **fields: Decimal | None):
        for name in BLENDED_FIELDS:
            setattr(self, name, fields.get(name))


def _weight(distance_km: float) -> float:
    """런타임과 같은 거리역수 가중."""
    return 1.0 / max(distance_km, 0.001)


class TestWeightedMean(unittest.TestCase):
    def test_two_donors_weighted_by_inverse_distance(self):
        """10km·20km 도너 → 가중 2:1. 손계산과 일치해야 한다."""
        near = FakeRow(temp_avg_normal=Decimal("10"), rainfall_normal=Decimal("100"))
        far = FakeRow(temp_avg_normal=Decimal("20"), rainfall_normal=Decimal("40"))

        result = _weighted_normals([(near, _weight(10)), (far, _weight(20))])

        # (10*(1/10) + 20*(1/20)) / (1/10 + 1/20) = 2.0 / 0.15 = 13.3333
        self.assertAlmostEqual(float(result.temp_avg_normal), 13.3333, places=3)
        # (100*(1/10) + 40*(1/20)) / 0.15 = 12.0 / 0.15 = 80.0
        self.assertAlmostEqual(float(result.rainfall_normal), 80.0, places=3)

    def test_returns_value_object_not_orm(self):
        """합성값은 비영속 값 객체여야 한다 — ORM이면 세션에 붙어 없는 행이 DB로 샌다."""
        result = _weighted_normals([(FakeRow(temp_avg_normal=Decimal("5")), 1.0)])
        self.assertIsInstance(result, MonthlyNormals)

    def test_decimal_type_preserved(self):
        """호출부가 ORM Numeric과 같은 타입을 기대한다 — float로 새면 하류 거동이 달라진다."""
        result = _weighted_normals([(FakeRow(rainfall_normal=Decimal("3.5")), 1.0)])
        self.assertIsInstance(result.rainfall_normal, Decimal)


class TestFieldIndependence(unittest.TestCase):
    def test_missing_field_renormalizes_only_that_field(self):
        """도너 하나가 한 필드만 결측이면 그 필드만 남은 도너로 재정규화된다.

        도너 행 전체를 버리면 그 도너가 가진 다른 필드 정보까지 잃는다.
        """
        near = FakeRow(temp_avg_normal=Decimal("10"), rainfall_normal=Decimal("100"))
        far = FakeRow(temp_avg_normal=None, rainfall_normal=Decimal("40"))  # 기온만 결측

        result = _weighted_normals([(near, _weight(10)), (far, _weight(20))])

        # 기온: near 하나뿐이라 그 값 그대로 (재정규화 → 가중치 1.0)
        self.assertAlmostEqual(float(result.temp_avg_normal), 10.0, places=3)
        # 강수: 두 도너 다 사용 → 2:1 가중평균 80.0. far가 통째로 버려지지 않았다는 증거.
        self.assertAlmostEqual(float(result.rainfall_normal), 80.0, places=3)

    def test_all_donors_missing_field_yields_none(self):
        """모든 도너가 결측인 필드는 None — 값을 지어내지 않는다(§18-4). 예외도 안 난다."""
        rows = [
            (FakeRow(rainfall_normal=Decimal("100")), _weight(10)),
            (FakeRow(rainfall_normal=Decimal("40")), _weight(20)),
        ]
        result = _weighted_normals(rows)

        self.assertIsNone(result.temp_avg_normal)
        self.assertIsNone(result.sunlight_normal)
        self.assertIsNotNone(result.rainfall_normal)  # 있는 필드는 정상 산출

    def test_empty_donor_list_is_all_none(self):
        """도너가 없어도 죽지 않는다(§18-5)."""
        result = _weighted_normals([])
        self.assertIsNone(result.temp_avg_normal)
        self.assertIsNone(result.rainfall_normal)


class TestZeroNotTreatedAsMissing(unittest.TestCase):
    """회귀 테스트: 0.0을 결측으로 떨어뜨리면 강원 산간 1월 평년기온이 사라진다."""

    def test_zero_temperature_is_a_value(self):
        rows = [
            (FakeRow(temp_avg_normal=Decimal("0.0")), _weight(10)),
            (FakeRow(temp_avg_normal=Decimal("2.0")), _weight(10)),
        ]
        result = _weighted_normals(rows)
        # 0.0이 결측 취급됐다면 2.0이 나온다. 값으로 셌다면 1.0.
        self.assertAlmostEqual(float(result.temp_avg_normal), 1.0, places=3)

    def test_lone_zero_donor_is_not_none(self):
        result = _weighted_normals([(FakeRow(temp_avg_normal=Decimal("0.0")), 1.0)])
        self.assertIsNotNone(result.temp_avg_normal)
        self.assertEqual(float(result.temp_avg_normal), 0.0)


class TestSingleDonorMatchesLegacy(unittest.TestCase):
    """도너가 1곳이면 종전(최근접 1개 복사)과 같은 값이어야 한다.

    검증 스크립트에서 knn_k1의 MAE가 nearest_1과 소수점까지 일치한 것과 같은 성질이다.
    """

    def test_single_donor_copies_values(self):
        row = FakeRow(
            temp_avg_normal=Decimal("12.34"),
            rainfall_normal=Decimal("56.78"),
            solar_radiation_normal=Decimal("9.01"),
        )
        result = _weighted_normals([(row, _weight(7.5))])

        self.assertAlmostEqual(float(result.temp_avg_normal), 12.34, places=4)
        self.assertAlmostEqual(float(result.rainfall_normal), 56.78, places=4)
        self.assertAlmostEqual(float(result.solar_radiation_normal), 9.01, places=4)


class TestDeterminism(unittest.TestCase):
    def test_same_input_same_output(self):
        rows = [
            (FakeRow(temp_avg_normal=Decimal("10"), rainfall_normal=Decimal("3")), _weight(4)),
            (FakeRow(temp_avg_normal=Decimal("13"), rainfall_normal=Decimal("8")), _weight(11)),
        ]
        self.assertEqual(_weighted_normals(rows), _weighted_normals(rows))

    def test_equidistant_donors_break_tie_by_region_id(self):
        """격자가 5km 단위라 동거리 동점이 흔하다. 순서가 흔들리면 같은 밭이 날마다
        다른 점수를 받는다."""
        me = FakeGrid(60, 127)
        # 상하좌우 4방향 — 전부 정확히 5km로 동거리다.
        candidates = [
            (FakeGrid(61, 127, region_id=40), "가", None),
            (FakeGrid(59, 127, region_id=10), "나", None),
            (FakeGrid(60, 128, region_id=30), "다", None),
            (FakeGrid(60, 126, region_id=20), "라", None),
        ]
        picked = [name for _, name, _ in _rank_donors(me, candidates, k=2)]
        self.assertEqual(picked, ["나", "라"])  # region_id 10, 20

        # 입력 순서를 뒤집어도 같은 결과여야 한다.
        picked_reversed = [
            name for _, name, _ in _rank_donors(me, list(reversed(candidates)), k=2)
        ]
        self.assertEqual(picked_reversed, ["나", "라"])

    def test_nearer_donor_ranks_first(self):
        me = FakeGrid(0, 0)
        candidates = [
            (FakeGrid(4, 0, region_id=1), "먼곳", None),
            (FakeGrid(1, 0, region_id=2), "가까운곳", None),
        ]
        self.assertEqual(_rank_donors(me, candidates, k=1)[0][1], "가까운곳")


class TestSubstitutionMessage(unittest.TestCase):
    def test_lists_every_donor_when_few(self):
        """§18-4: 섞인 출처를 밝힌다. 하나만 적으면 근사의 성격을 감추는 문구가 된다."""
        source = ClimatologySource(
            by_month={},
            substituted_from="문경시",
            distance_km=15.0,
            donors=(("문경시", 15.0), ("상주시", 22.4), ("예천군", 31.6)),
        )
        msg = substitution_limitation(source)

        for name in ("문경시", "상주시", "예천군"):
            self.assertIn(name, msg)
        self.assertIn("15", msg)  # 최근접 거리
        self.assertIn("32", msg)  # 최원거리(반올림)
        self.assertIn("가중", msg)

    def test_many_donors_summarized_but_count_and_range_kept(self):
        """도너 10곳 이름을 다 적으면 200자가 넘어 화면에서 안 읽힌다.

        가까운 3곳만 이름으로 밝히고 나머지는 개수로 요약하되, **몇 곳을 섞었는지와
        거리 범위는 반드시 남긴다** — 그게 빠지면 근사 규모를 감추는 것이다.
        """
        donors = tuple((f"지역{i}", 10.0 + i * 4) for i in range(10))
        source = ClimatologySource(
            by_month={}, substituted_from="지역0", distance_km=10.0, donors=donors
        )
        msg = substitution_limitation(source)

        self.assertIn("지역0", msg)
        self.assertIn("지역2", msg)  # 이름으로 밝히는 상위 3곳
        self.assertNotIn("지역9", msg)  # 나머지는 요약
        self.assertIn("외 7곳", msg)
        self.assertIn("10곳", msg)  # 총 개수는 유지
        self.assertIn("46", msg)  # 최원거리도 유지
        self.assertLess(len(msg), 130, "한계 문구가 화면에서 읽을 수 없을 만큼 길다")

    def test_full_donor_list_available_on_source(self):
        """문구는 요약해도 구조화 데이터에는 전부 남는다.

        API 응답에는 아직 안 싣는다 — 지금 계약은 `limitations: string[]`뿐이고 FE가
        펼치기 UI를 요구한 적이 없다(YAGNI). 필요해지면 여기서 꺼내 쓰면 된다.
        """
        donors = tuple((f"지역{i}", 10.0 + i) for i in range(10))
        source = ClimatologySource(by_month={}, substituted_from="지역0", donors=donors)
        self.assertEqual(len(source.donors), 10)

    def test_single_donor_keeps_singular_wording(self):
        source = ClimatologySource(
            by_month={}, substituted_from="순천시", distance_km=12.3, donors=(("순천시", 12.3),)
        )
        msg = substitution_limitation(source)
        self.assertIn("순천시", msg)
        self.assertIn("가장 가까운", msg)

    def test_not_substituted_returns_none(self):
        self.assertIsNone(substitution_limitation(ClimatologySource(by_month={})))


class TestAltitudeDonorFilter(unittest.TestCase):
    """고도가 동떨어진 도너를 걷어내는지. 수평거리만 보면 한라산 지점과 해안 지점이
    같은 후보에 든다(적재 실측: 서귀포시 도너 고도 산포 1,524m)."""

    def test_high_altitude_donor_dropped_even_when_nearest(self):
        me = FakeGrid(60, 127)
        candidates = [
            (FakeGrid(60, 128, region_id=1), "산중턱", 900),  # 5km, +880m
            (FakeGrid(62, 127, region_id=2), "저지대A", 40),  # 10km, +20m
            (FakeGrid(63, 127, region_id=3), "저지대B", 60),  # 15km, +40m
            (FakeGrid(64, 127, region_id=4), "저지대C", 10),  # 20km, -10m
        ]
        picked = [name for _, name, _ in _rank_donors(me, candidates, my_altitude=20, k=3)]
        self.assertNotIn("산중턱", picked)
        self.assertEqual(picked, ["저지대A", "저지대B", "저지대C"])

    def test_filter_abandoned_when_it_would_empty_the_pool(self):
        """고립된 고지대 구역이 통째로 '데이터 없음'이 되면 안 된다 — 근사가 없는 것보단 낫다."""
        me = FakeGrid(0, 0)
        candidates = [
            (FakeGrid(1, 0, region_id=1), "먼고도A", 900),
            (FakeGrid(2, 0, region_id=2), "먼고도B", 950),
        ]
        picked = [name for _, name, _ in _rank_donors(me, candidates, my_altitude=20, k=5)]
        self.assertEqual(picked, ["먼고도A", "먼고도B"])

    def test_unknown_altitude_donor_is_kept(self):
        """없는 정보로 도너를 버리면 그 구역이 통째로 비어버린다."""
        me = FakeGrid(0, 0)
        candidates = [
            (FakeGrid(1, 0, region_id=1), "고도미상", None),
            (FakeGrid(2, 0, region_id=2), "같은고도", 25),
            (FakeGrid(3, 0, region_id=3), "같은고도2", 30),
        ]
        picked = [name for _, name, _ in _rank_donors(me, candidates, my_altitude=20, k=3)]
        self.assertIn("고도미상", picked)


class TestLapseRate(unittest.TestCase):
    """밭 고도 감률 보정(0.65℃/100m). 기준선은 평년치가 대표하는 고도다."""

    def _row(self, reference: int | None, temp: str = "20.0") -> MonthlyNormals:
        return MonthlyNormals(
            temp_avg_normal=Decimal(temp),
            temp_night_min_normal=Decimal("12.0"),
            rainfall_normal=Decimal("100.0"),
            reference_altitude_m=reference,
        )

    def test_higher_farm_gets_colder(self):
        # 밭 400m, 기준선 100m → 300m 차이 → -1.95℃
        adjusted, delta = _apply_lapse_rate({7: self._row(100)}, farm_altitude=400)
        self.assertAlmostEqual(delta, 300.0)
        self.assertAlmostEqual(float(adjusted[7].temp_avg_normal), 18.05, places=4)
        self.assertAlmostEqual(float(adjusted[7].temp_night_min_normal), 10.05, places=4)

    def test_lower_farm_gets_warmer(self):
        adjusted, delta = _apply_lapse_rate({7: self._row(500)}, farm_altitude=100)
        self.assertAlmostEqual(delta, -400.0)
        self.assertAlmostEqual(float(adjusted[7].temp_avg_normal), 22.6, places=4)

    def test_rainfall_untouched(self):
        """강수는 고도와 이렇게 단순한 관계가 아니다 — 같은 식으로 보정하면 지어낸 값이 된다."""
        adjusted, _ = _apply_lapse_rate({7: self._row(100)}, farm_altitude=400)
        self.assertEqual(adjusted[7].rainfall_normal, Decimal("100.0"))

    def test_small_delta_not_corrected(self):
        """SRTM 표고 검증 오차가 MAE 8.8m라 그 언저리를 보정하면 잡음만 키운다."""
        original = self._row(100)
        adjusted, delta = _apply_lapse_rate({7: original}, farm_altitude=110)
        self.assertIsNone(delta)
        self.assertIs(adjusted[7], original)

    def test_missing_reference_leaves_row_alone(self):
        """기준선을 모르면 보정할 수 없다 — 보정한 척하지 않는다(§18-4)."""
        original = self._row(None)
        adjusted, delta = _apply_lapse_rate({7: original}, farm_altitude=400)
        self.assertIsNone(delta)
        self.assertIs(adjusted[7], original)

    def test_limitation_states_direction_and_basis(self):
        source = ClimatologySource(
            by_month={}, lapse_delta_m=300.0, farm_altitude_source="emd_point"
        )
        msg = lapse_limitation(source)
        self.assertIn("300m", msg)
        self.assertIn("높아", msg)
        self.assertIn("-1.9℃", msg)  # 300m × 0.65/100 = 1.95 → 소수 1자리 표기
        self.assertIn("읍·면·동", msg)  # 밭 실측이 아님을 밝힌다

    def test_each_altitude_source_gets_its_own_wording(self):
        """출처마다 근사 정도가 다르다 — 뭉뚱그리면 리 단위 정밀도를 시군구 폴백과
        같게 보이게 만든다(§18-4)."""
        seen = set()
        for src, expect in (
            ("ri_polygon", "리(里)"),
            ("emd_polygon", "동 경계"),
            ("emd_point", "읍·면·동"),
            ("region_point", "시·군"),
        ):
            msg = lapse_limitation(
                ClimatologySource(by_month={}, lapse_delta_m=200.0, farm_altitude_source=src)
            )
            self.assertIn(expect, msg)
            seen.add(msg)
        self.assertEqual(len(seen), 4, "출처 4종이 서로 다른 문구를 내야 한다")

    def test_unknown_altitude_source_falls_back_conservatively(self):
        """시드가 새 값을 먼저 쓰더라도 없는 정밀도를 주장하지 않는다."""
        msg = lapse_limitation(
            ClimatologySource(by_month={}, lapse_delta_m=200.0, farm_altitude_source="parcel_xyz")
        )
        self.assertIn("상위 행정구역", msg)

    def test_no_limitation_when_not_corrected(self):
        self.assertIsNone(lapse_limitation(ClimatologySource(by_month={})))


if __name__ == "__main__":
    unittest.main()
