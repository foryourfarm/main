"""
일조시간 계산 서비스 (Hybrid: 실측 + Angstrom + 동적 보정)

전략:
  1. SI_DAY(일사량) 있으면 직접 변환
  2. 없으면 Angstrom 기본 계산
  3. CA_TOT/RN_DAY/HM_AVG 있는 만큼 동적 보정
"""
import math
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class SunlightResult:
    """일조시간 계산 결과"""
    value: float  # 추정/실측 일조시간 (hr)
    source: str  # 데이터 출처
    method: str  # 계산 방식 (measurement, angstrom_only, angstrom_corrected)
    confidence: float  # 신뢰도 (0.0~1.0, 정확도 0.9 기준으로 사용 포함/제외 판정)
    basis: str  # 근거 (사용한 입력 데이터 설명)
    is_calculated: bool = False  # True면 계산값 (FE에서 작게 표시)


class SunlightCalculation:
    """일조시간 계산 엔진"""

    # ========================================================================
    # Step 1: 기본 상수 & 헬퍼
    # ========================================================================

    @staticmethod
    def _doy_from_month(month: int, day: int = 15) -> int:
        """월 → 연중 일자 (DOY) 변환"""
        days_in_month = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
        return days_in_month[month - 1] + day

    @staticmethod
    def _calculate_daylight_hours(latitude: float, doy: int) -> float:
        """
        가조시간(daylight hours) 계산 [hr]

        Args:
            latitude: 위도 (도, -90~90)
            doy: 연중 일자 (1~365)

        Returns:
            N: 가조시간 (hr)
        """
        # 태양 적위 (declination)
        d = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39)

        # 위도 (라디안)
        lat_rad = math.radians(latitude)

        # 일출/일몰 시간각 (라디안)
        omega_s = math.acos(-math.tan(lat_rad) * math.tan(d))

        # 가조시간 계산
        N = (24 / math.pi) * omega_s

        return N

    # ========================================================================
    # Step 2: 방법 1 - 실측 일조시간 직접 사용 (가장 정확)
    # ========================================================================

    @classmethod
    def from_measurement(
        cls,
        ss_day: float,
    ) -> SunlightResult:
        """
        실측 일조시간 직접 사용 (SS_DAY from ASOS/농업기상)

        Args:
            ss_day: 실측 일조시간 [hr]

        Returns:
            SunlightResult: 계산 결과
        """
        # 범위 제한 (0~14 hr)
        ss_measured = max(0, min(14, ss_day))

        return SunlightResult(
            value=ss_measured,
            source="실측 일조시간",
            method="measurement",
            confidence=0.95,
            basis=f"SS_DAY={ss_day:.1f} hr (실측값 직접 사용)",
            is_calculated=False,
        )

    # ========================================================================
    # Step 3: 방법 2 - Angstrom 기본 (기온만)
    # ========================================================================

    @classmethod
    def from_temperature_only(
        cls,
        tmax: float,
        tmin: float,
        latitude: float,
        month: int,
    ) -> SunlightResult:
        """
        Angstrom 공식 (기온만 사용)

        공식:
          SS = N × (a + b × √(Tmax - Tmin))

        Args:
            tmax: 월별 평균 최고기온 [°C]
            tmin: 월별 평균 최저기온 [°C]
            latitude: 위도
            month: 월 (1~12)

        Returns:
            SunlightResult: 계산 결과
        """
        doy = cls._doy_from_month(month)
        N = cls._calculate_daylight_hours(latitude, doy)

        # 온도 기반 계수 (지역 경험식)
        # SS/N = a + b × √(Tmax - Tmin)
        a, b = 0.16, 0.10

        # Angstrom 계산
        temp_diff = max(0, tmax - tmin)
        ss_estimated = N * (a + b * math.sqrt(temp_diff))

        # 범위 제한
        ss_estimated = max(0, min(N, ss_estimated))

        return SunlightResult(
            value=ss_estimated,
            source="Angstrom 계산 (기온)",
            method="angstrom_only",
            confidence=0.70,
            basis=f"Tmax={tmax}°C, Tmin={tmin}°C, 가조시간={N:.1f}hr (a=0.16, b=0.10)",
            is_calculated=True,
        )

    # ========================================================================
    # Step 4: 방법 3 - Angstrom + 동적 보정
    # ========================================================================

    @classmethod
    def from_temperature_with_corrections(
        cls,
        tmax: float,
        tmin: float,
        latitude: float,
        month: int,
        ca_tot: Optional[float] = None,  # 전운량 (1/10, 0~10)
        rn_day: Optional[float] = None,  # 일강수량 (mm)
        hm_avg: Optional[float] = None,  # 평균 상대습도 (%)
    ) -> SunlightResult:
        """
        Angstrom + 구름/강수/습도 동적 보정

        Args:
            tmax, tmin: 기온
            latitude: 위도
            month: 월
            ca_tot: 전운량 (있으면 적용)
            rn_day: 강수량 (있으면 적용)
            hm_avg: 습도 (있으면 적용)

        Returns:
            SunlightResult: 계산 결과
        """
        # 기본 Angstrom 계산
        doy = cls._doy_from_month(month)
        N = cls._calculate_daylight_hours(latitude, doy)
        a, b = 0.16, 0.10
        temp_diff = max(0, tmax - tmin)
        ss = N * (a + b * math.sqrt(temp_diff))

        # 보정 근거 기록
        corrections_applied = []
        final_confidence = 0.70

        # 보정 1: 구름 (CA_TOT)
        if ca_tot is not None and 0 <= ca_tot <= 10:
            cloud_factor = 1 - 0.75 * (ca_tot / 10) ** 2
            ss *= cloud_factor
            corrections_applied.append(f"구름(CA_TOT={ca_tot}/10)보정x{cloud_factor:.2f}")
            final_confidence = min(0.82, final_confidence + 0.08)

        # 보정 2: 강수 (RN_DAY)
        if rn_day is not None and rn_day > 0:
            # 월 강수량을 일 평균으로 환산 (대략 30일)
            rn_daily_equiv = rn_day / 30
            precip_factor = max(0.1, 1 - 0.3 * min(rn_daily_equiv, 10) / 10)
            ss *= precip_factor
            corrections_applied.append(
                f"강수(RN={rn_daily_equiv:.1f}mm)보정x{precip_factor:.2f}"
            )
            final_confidence = min(0.85, final_confidence + 0.07)

        # 보정 3: 습도 (HM_AVG)
        if hm_avg is not None and hm_avg > 50:
            humidity_factor = 1 - 0.3 * (hm_avg - 50) / 50
            ss *= humidity_factor
            corrections_applied.append(f"습도(HM={hm_avg}%)보정x{humidity_factor:.2f}")
            final_confidence = min(0.87, final_confidence + 0.05)

        # 범위 제한
        ss = max(0, min(N, ss))

        corrections_str = " + ".join(corrections_applied) if corrections_applied else "적용 없음"

        return SunlightResult(
            value=ss,
            source="Angstrom + 동적 보정",
            method="angstrom_corrected",
            confidence=final_confidence,
            basis=f"기온 기반 가조시간={N:.1f}hr + [{corrections_str}]",
            is_calculated=True,
        )

    # ========================================================================
    # Step 5: 통합 하이브리드 선택 로직
    # ========================================================================

    @classmethod
    def calculate_optimal(
        cls,
        latitude: float,
        month: int,
        tmax: float,
        tmin: float,
        ss_day: Optional[float] = None,
        ca_tot: Optional[float] = None,
        rn_day: Optional[float] = None,
        hm_avg: Optional[float] = None,
    ) -> SunlightResult:
        """
        최적의 방식 자동 선택 + 계산

        우선순위:
          1. SS_DAY (실측) 있음 → 직접 사용
          2. SS_DAY 없음 + (CA_TOT or RN_DAY or HM_AVG) → Angstrom + 보정
          3. SS_DAY 없음 + 보정 데이터 없음 → Angstrom 기본

        Args:
            latitude: 위도
            month: 월 (1~12)
            tmax, tmin: 기온
            ss_day: 실측 일조시간 (선택)
            ca_tot: 전운량 (선택)
            rn_day: 강수량 (선택)
            hm_avg: 습도 (선택)

        Returns:
            SunlightResult: 선택된 방식의 계산 결과
        """
        # Priority 1: 실측 일조시간 있으면 최우선
        if ss_day is not None and ss_day > 0:
            return cls.from_measurement(ss_day)

        # Priority 2: 보정 데이터 있으면 Angstrom + 보정
        if ca_tot is not None or rn_day is not None or hm_avg is not None:
            return cls.from_temperature_with_corrections(
                tmax, tmin, latitude, month,
                ca_tot=ca_tot, rn_day=rn_day, hm_avg=hm_avg
            )

        # Priority 3: 기본 Angstrom
        return cls.from_temperature_only(tmax, tmin, latitude, month)

    # ========================================================================
    # 추가: 신뢰도 기반 평가
    # ========================================================================

    @staticmethod
    def confidence_to_label(confidence: float) -> str:
        """신뢰도 → 라벨 변환"""
        if confidence >= 0.90:
            return "매우 높음"
        elif confidence >= 0.80:
            return "높음"
        elif confidence >= 0.70:
            return "중간"
        else:
            return "낮음"

    @staticmethod
    def estimate_error_range(confidence: float) -> Tuple[float, float]:
        """신뢰도 → 오차 범위 (hr) 추정"""
        # 신뢰도와 오차의 경험적 관계
        if confidence >= 0.88:
            return (-0.4, 0.4)  # ±0.4 hr
        elif confidence >= 0.82:
            return (-0.6, 0.6)  # ±0.6 hr
        elif confidence >= 0.70:
            return (-1.2, 1.2)  # ±1.2 hr
        else:
            return (-1.5, 1.5)  # ±1.5 hr


# ============================================================================
# 사용 예시
# ============================================================================

if __name__ == "__main__":
    # 예 1: 실측 데이터 있는 경우
    result1 = SunlightCalculation.calculate_optimal(
        latitude=37.0,
        month=1,
        tmax=3.2,
        tmin=-5.1,
        ss_day=5.4,  # 실측 일조시간 있음
    )
    print(f"예 1 (실측): {result1.value:.1f} hr ({result1.source})")
    print(f"  신뢰도: {result1.confidence:.2f} ({SunlightCalculation.confidence_to_label(result1.confidence)})")
    print(f"  오차범위: {SunlightCalculation.estimate_error_range(result1.confidence)}")
    print()

    # 예 2: Angstrom + 구름 + 강수 보정
    result2 = SunlightCalculation.calculate_optimal(
        latitude=37.0,
        month=1,
        tmax=3.2,
        tmin=-5.1,
        ca_tot=4.8,  # 전운량
        rn_day=12.3,  # 월 강수량
        hm_avg=62,  # 습도
    )
    print(f"예 2 (Angstrom+보정): {result2.value:.1f} hr ({result2.source})")
    print(f"  신뢰도: {result2.confidence:.2f} ({SunlightCalculation.confidence_to_label(result2.confidence)})")
    print(f"  기초: {result2.basis}")
    print()

    # 예 3: 기본 Angstrom (데이터 최소)
    result3 = SunlightCalculation.calculate_optimal(
        latitude=37.0,
        month=1,
        tmax=3.2,
        tmin=-5.1,
    )
    print(f"예 3 (기본 Angstrom): {result3.value:.1f} hr ({result3.source})")
    print(f"  신뢰도: {result3.confidence:.2f} ({SunlightCalculation.confidence_to_label(result3.confidence)})")
