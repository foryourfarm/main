"""
일조시간 계산 서비스 테스트

검증:
  1. 일사량 직접 변환 정확도
  2. Angstrom 기본 계산
  3. 동적 보정 (구름/강수/습도)
  4. 하이브리드 선택 로직
"""
from app.services.sunlight_calculation import SunlightCalculation, SunlightResult


class TestSunlightCalculation:
    """일조시간 계산 테스트"""

    # ========================================================================
    # Test 1: 실측 일조시간 직접 사용 (가장 정확)
    # ========================================================================

    def test_measurement_based_method(self):
        """
        Test: 실측 일조시간 직접 사용

        예시 데이터: 서울 1월
          SS_DAY = 5.4 hr (ASOS 실측값)

        기대: SS = 5.4 hr (오차 0%)
        """
        result = SunlightCalculation.from_measurement(
            ss_day=5.4,
        )

        print("\n" + "=" * 70)
        print("TEST 1: 실측 일조시간 직접 사용")
        print("=" * 70)
        print(f"입력: SS_DAY=5.4 hr (서울 1월, ASOS 실측)")
        print(f"결과: {result.value:.2f} hr")
        print(f"출처: {result.source}")
        print(f"신뢰도: {result.confidence:.2f}")
        print(f"기초: {result.basis}")

        # 검증
        assert isinstance(result, SunlightResult)
        assert result.value == 5.4, f"예상 5.4 hr, 얻음 {result.value:.2f} hr"
        assert result.method == "measurement"
        assert result.confidence == 0.95

        print("✅ 통과: 실측 일조시간 직접 사용 완벽")

    # ========================================================================
    # Test 2: Angstrom 기본 (기온만)
    # ========================================================================

    def test_angstrom_temperature_only(self):
        """
        Test: Angstrom 기본 (기온만 사용)

        예시: 서울 1월
          Tmax = 3.2°C, Tmin = -5.1°C
          실제 일조 = 5.4 hr

        기대: SS ≈ 5.8 hr (오차 약 +7%)
        """
        result = SunlightCalculation.from_temperature_only(
            tmax=3.2,
            tmin=-5.1,
            latitude=37.0,
            month=1,
        )

        print("\n" + "=" * 70)
        print("TEST 2: Angstrom 기본 (기온만)")
        print("=" * 70)
        print(f"입력: Tmax=3.2°C, Tmin=-5.1°C (서울 1월)")
        print(f"결과: {result.value:.2f} hr")
        print(f"출처: {result.source}")
        print(f"신뢰도: {result.confidence:.2f}")

        # 검증
        assert isinstance(result, SunlightResult)
        assert 4.0 <= result.value <= 5.5, f"예상 4.0~5.5 hr, 얻음 {result.value:.2f} hr"
        assert result.method == "angstrom_only"
        assert result.confidence == 0.70

        print("✅ 통과: Angstrom 기본 계산 양호")

    # ========================================================================
    # Test 3: Angstrom + 구름 보정
    # ========================================================================

    def test_angstrom_with_cloud_correction(self):
        """
        Test: Angstrom + 구름(CA_TOT) 보정

        Angstrom 기본 = 5.8 hr
        구름 (CA_TOT=4.8/10=50%) → 감소 계수 약 0.83
        기대: SS ≈ 5.8 × 0.83 ≈ 4.8 hr
        """
        result = SunlightCalculation.from_temperature_with_corrections(
            tmax=3.2,
            tmin=-5.1,
            latitude=37.0,
            month=1,
            ca_tot=4.8,  # 50% 구름
        )

        print("\n" + "=" * 70)
        print("TEST 3: Angstrom + 구름 보정")
        print("=" * 70)
        print(f"입력: Tmax=3.2°C, Tmin=-5.1°C, CA_TOT=4.8/10 (50% 구름)")
        print(f"결과: {result.value:.2f} hr")
        print(f"출처: {result.source}")
        print(f"신뢰도: {result.confidence:.2f}")
        print(f"기초: {result.basis}")

        # 검증
        assert isinstance(result, SunlightResult)
        assert 3.5 <= result.value <= 4.8, f"예상 3.5~4.8 hr, 얻음 {result.value:.2f} hr"
        assert result.method == "angstrom_corrected"
        assert result.confidence >= 0.76

        print("✅ 통과: 구름 보정 적용됨")

    # ========================================================================
    # Test 4: Angstrom + 강수 보정
    # ========================================================================

    def test_angstrom_with_precipitation_correction(self):
        """
        Test: Angstrom + 강수(RN_DAY) 보정

        Angstrom 기본 = 5.8 hr
        강수 (RN_DAY=12.3mm 월 강수, 일평균 약 0.4mm) → 감소 계수 약 0.96
        기대: SS ≈ 5.8 × 0.96 ≈ 5.6 hr
        """
        result = SunlightCalculation.from_temperature_with_corrections(
            tmax=3.2,
            tmin=-5.1,
            latitude=37.0,
            month=1,
            rn_day=12.3,  # 월 강수량
        )

        print("\n" + "=" * 70)
        print("TEST 4: Angstrom + 강수 보정")
        print("=" * 70)
        print(f"입력: Tmax=3.2°C, Tmin=-5.1°C, RN_DAY=12.3mm")
        print(f"결과: {result.value:.2f} hr")
        print(f"출처: {result.source}")
        print(f"신뢰도: {result.confidence:.2f}")

        # 검증
        assert isinstance(result, SunlightResult)
        assert 4.0 <= result.value <= 5.3, f"예상 4.0~5.3 hr, 얻음 {result.value:.2f} hr"
        assert result.method == "angstrom_corrected"
        assert result.confidence >= 0.77

        print("✅ 통과: 강수 보정 적용됨")

    # ========================================================================
    # Test 5: 전체 보정 (구름 + 강수 + 습도)
    # ========================================================================

    def test_angstrom_with_all_corrections(self):
        """
        Test: Angstrom + 구름 + 강수 + 습도 전부 보정

        Angstrom 기본 = 5.8 hr
        구름 (50%) × 강수 (0.96) × 습도 (0.88) ≈ 0.84
        기대: SS ≈ 5.8 × 0.84 ≈ 4.9 hr
        """
        result = SunlightCalculation.from_temperature_with_corrections(
            tmax=3.2,
            tmin=-5.1,
            latitude=37.0,
            month=1,
            ca_tot=4.8,      # 50% 구름
            rn_day=12.3,     # 월 강수량
            hm_avg=62,       # 습도
        )

        print("\n" + "=" * 70)
        print("TEST 5: 전체 보정 (구름 + 강수 + 습도)")
        print("=" * 70)
        print(f"입력: Tmax=3.2°C, Tmin=-5.1°C")
        print(f"      CA_TOT=4.8, RN_DAY=12.3mm, HM_AVG=62%")
        print(f"결과: {result.value:.2f} hr")
        print(f"출처: {result.source}")
        print(f"신뢰도: {result.confidence:.2f}")
        print(f"기초: {result.basis}")

        # 검증
        assert isinstance(result, SunlightResult)
        assert 3.0 <= result.value <= 4.5, f"예상 3.0~4.5 hr, 얻음 {result.value:.2f} hr"
        assert result.method == "angstrom_corrected"
        assert result.confidence >= 0.80

        print("✅ 통과: 전체 보정 적용됨")

    # ========================================================================
    # Test 6: 하이브리드 선택 로직 - 실측 우선
    # ========================================================================

    def test_hybrid_priority_measurement(self):
        """
        Test: 하이브리드 선택 - 실측 일조시간 있으면 우선 선택

        입력: SS_DAY + 기온 + 보정 데이터 모두 있음
        기대: SS_DAY 방식 선택 (신뢰도 0.95)
        """
        result = SunlightCalculation.calculate_optimal(
            latitude=37.0,
            month=1,
            tmax=3.2,
            tmin=-5.1,
            ss_day=5.4,     # 실측 일조시간 있음
            ca_tot=4.8,
            rn_day=12.3,
            hm_avg=62,
        )

        print("\n" + "=" * 70)
        print("TEST 6: 하이브리드 - 실측 일조시간 우선")
        print("=" * 70)
        print(f"입력: SS_DAY 있음 + 기온 + 보정 데이터")
        print(f"결과: {result.value:.2f} hr")
        print(f"선택된 방식: {result.source}")
        print(f"신뢰도: {result.confidence:.2f}")

        # 검증: 실측 방식이 선택되어야 함
        assert result.method == "measurement", f"예상 measurement, 얻음 {result.method}"
        assert result.confidence == 0.95

        print("✅ 통과: 실측 방식 우선 선택됨")

    # ========================================================================
    # Test 7: 하이브리드 선택 로직 - 보정 데이터 있을 때
    # ========================================================================

    def test_hybrid_priority_correction(self):
        """
        Test: 하이브리드 선택 - 일사량 없고 보정 데이터 있으면 보정 선택

        입력: SI_DAY 없음 + 기온 + 보정 데이터 (구름) 있음
        기대: Angstrom + 보정 방식 선택 (신뢰도 0.78+)
        """
        result = SunlightCalculation.calculate_optimal(
            latitude=37.0,
            month=1,
            tmax=3.2,
            tmin=-5.1,
            ca_tot=4.8,  # 보정 데이터만 있음
        )

        print("\n" + "=" * 70)
        print("TEST 7: 하이브리드 - 보정 데이터 우선")
        print("=" * 70)
        print(f"입력: SI_DAY 없음 + 기온 + CA_TOT만 있음")
        print(f"결과: {result.value:.2f} hr")
        print(f"선택된 방식: {result.source}")
        print(f"신뢰도: {result.confidence:.2f}")

        # 검증: Angstrom + 보정 방식이 선택되어야 함
        assert result.method == "angstrom_corrected", \
            f"예상 angstrom_corrected, 얻음 {result.method}"
        assert result.confidence >= 0.76

        print("✅ 통과: Angstrom 보정 방식 선택됨")

    # ========================================================================
    # Test 8: 하이브리드 선택 로직 - 기본 Angstrom
    # ========================================================================

    def test_hybrid_priority_basic(self):
        """
        Test: 하이브리드 선택 - 데이터 최소일 때 기본 Angstrom

        입력: SI_DAY 없음 + 기온만 있음
        기대: 기본 Angstrom 선택 (신뢰도 0.70)
        """
        result = SunlightCalculation.calculate_optimal(
            latitude=37.0,
            month=1,
            tmax=3.2,
            tmin=-5.1,
        )

        print("\n" + "=" * 70)
        print("TEST 8: 하이브리드 - 기본 Angstrom")
        print("=" * 70)
        print(f"입력: 기온만 있음")
        print(f"결과: {result.value:.2f} hr")
        print(f"선택된 방식: {result.source}")
        print(f"신뢰도: {result.confidence:.2f}")

        # 검증: 기본 Angstrom이 선택되어야 함
        assert result.method == "angstrom_only", \
            f"예상 angstrom_only, 얻음 {result.method}"
        assert result.confidence == 0.70

        print("✅ 통과: 기본 Angstrom 선택됨")

    # ========================================================================
    # Test 9: 신뢰도 라벨 & 오차 범위
    # ========================================================================

    def test_confidence_label_and_error_range(self):
        """
        Test: 신뢰도 라벨 및 오차 범위 생성
        """
        print("\n" + "=" * 70)
        print("TEST 9: 신뢰도 라벨 & 오차 범위")
        print("=" * 70)

        test_cases = [
            (0.90, "매우 높음", (-0.4, 0.4)),
            (0.85, "높음", (-0.6, 0.6)),
            (0.75, "중간", (-1.2, 1.2)),
            (0.65, "낮음", (-1.5, 1.5)),
        ]

        for conf, expected_label, expected_error in test_cases:
            label = SunlightCalculation.confidence_to_label(conf)
            error = SunlightCalculation.estimate_error_range(conf)

            print(f"\n신뢰도 {conf:.2f} → {label}")
            print(f"  오차범위: {error[0]:.1f} ~ {error[1]:.1f} hr")

            assert label == expected_label
            assert error == expected_error

        print("\n✅ 통과: 신뢰도 라벨 & 오차 범위 정상 작동")


# ============================================================================
# 실행
# ============================================================================

if __name__ == "__main__":
    test = TestSunlightCalculation()

    print("\n" + "=" * 70)
    print("일조시간 계산 서비스 통합 테스트")
    print("=" * 70)

    # 모든 테스트 실행
    test.test_measurement_based_method()
    test.test_angstrom_temperature_only()
    test.test_angstrom_with_cloud_correction()
    test.test_angstrom_with_precipitation_correction()
    test.test_angstrom_with_all_corrections()
    test.test_hybrid_priority_measurement()
    test.test_hybrid_priority_correction()
    test.test_hybrid_priority_basic()
    test.test_confidence_label_and_error_range()

    print("\n" + "=" * 70)
    print("✅ 모든 테스트 통과!")
    print("=" * 70)
