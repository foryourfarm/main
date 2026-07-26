"""일조시간 산출 (실측 → 일사량 환산 → 기온 폴백).

**왜 일사량 경로가 중심인가**: 일조시간은 실측이 가장 정확하지만 국내 월평년 소스에 거의
없다. 대신 농업기상 V3가 일사량(srqty)을 준다. 일사량은 물리적으로 일조시간과 직결되므로
(구름이 가리면 둘이 함께 준다) 환산 정확도가 기온 기반 추정보다 압도적으로 높다 —
실측 7,244행 홀드아웃 검증에서 R²=0.904 / MAE 0.845h(일별), MAE 0.587h(월평균)로
기온 경로(R²=0.496 / MAE 2.219h)를 크게 앞선다.

관계식은 Ångström–Prescott을 역으로 푼 것이다:
    Rs/Ra = a + b·(n/N)   →   n = N·((Rs/Ra) − a)/b
Ra(지구외 일사량)와 N(가조시간)은 위도·연중일자만으로 **정확히** 계산된다(FAO-56).
따라서 오차는 계수(a, b)와 일사량 실측 오차에서만 온다.

계수·신뢰도·오차범위는 전부 `docs/seed/sunlight_calibration.json`에서 읽는다 — 농업
기준값을 코드에 박지 않는다(CLAUDE.md §18-2). 재보정은 `scripts/calibrate_sunlight.py`.

한계(§18-4): 일사량 환산값은 실측 일조시간이 아니다. `is_calculated=True`로 표시되며
UI는 추정치임을 병기해야 한다.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_SEED_PATH = Path(__file__).resolve().parents[3] / "docs" / "seed" / "sunlight_calibration.json"

GSC = 0.0820  # 태양상수 MJ/m²/min (FAO-56)

# 관측 가능한 일조시간 상한. 국내 최대 가조시간(하지, 북부)이 약 14.2h라 안전 상한으로 둔다.
MAX_SUNLIGHT_HOURS = 15.0


@dataclass(frozen=True)
class SunlightResult:
    """일조시간 산출 결과. method가 곧 정확도 근거다."""

    value: float  # 일조시간 (hr)
    source: str  # 데이터 출처(사람이 읽는 설명)
    method: str  # measurement | radiation | temperature
    confidence: float  # 신뢰도 — 실측 검증치 기반(시드 참조)
    basis: str  # 근거(사용 입력 요약)
    is_calculated: bool = False  # True면 추정값 → UI에 표기 필요


@lru_cache(maxsize=1)
def calibration() -> dict:
    """보정 시드 로드(1회). 시드가 없으면 서비스가 죽지 않도록 FAO-56 기본값으로 폴백."""
    try:
        return json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # 시드 누락은 배포 사고지만 산출을 죽이지 않는다(§12). 대신 신뢰도를 낮춰
        # 0.90 게이트를 통과하지 못하게 해 검증되지 않은 값이 확정치처럼 쓰이는 것을 막는다.
        return {
            "angstrom_prescott": {"a": 0.25, "b": 0.50},
            "quality_bounds": {"clear_sky_max_ratio": 0.80, "min_ratio": 0.03},
            "confidence": {"measurement": 0.95, "radiation": 0.70, "temperature": 0.50},
            "error_range_hours": {"measurement": 0.1, "radiation": 2.0, "temperature": 2.75},
        }


def day_of_year(month: int, day: int = 15) -> int:
    """월 → 연중일자. 월 대표일은 15일(월평년 계산의 관례)."""
    days_before = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)
    return days_before[month - 1] + day


def _solar_geometry(latitude: float, doy: int) -> tuple[float, float]:
    """(태양시간각 ωs, 태양적위 δ). 백야/극야는 시간각을 π/0으로 자른다."""
    phi = math.radians(latitude)
    declination = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39)
    cos_ws = -math.tan(phi) * math.tan(declination)
    return math.acos(max(-1.0, min(1.0, cos_ws))), declination


def daylight_hours(latitude: float, doy: int) -> float:
    """가조시간 N (hr). FAO-56 Eq.34 — 위도·날짜만으로 정확히 결정된다."""
    ws, _ = _solar_geometry(latitude, doy)
    return (24.0 / math.pi) * ws


def extraterrestrial_radiation(latitude: float, doy: int) -> float:
    """지구외 일사량 Ra (MJ/m²/day). FAO-56 Eq.21 — 대기 밖 이론 일사량."""
    phi = math.radians(latitude)
    ws, declination = _solar_geometry(latitude, doy)
    dr = 1 + 0.033 * math.cos(2 * math.pi * doy / 365)  # 일-지 거리 보정
    return (
        (24 * 60 / math.pi)
        * GSC
        * dr
        * (
            ws * math.sin(phi) * math.sin(declination)
            + math.cos(phi) * math.cos(declination) * math.sin(ws)
        )
    )


class SunlightCalculation:
    """일조시간 산출 엔진. 결정론적 — 같은 입력이면 항상 같은 출력(§2 결정론 우선)."""

    @classmethod
    def from_measurement(cls, ss_day: float) -> SunlightResult:
        """실측 일조시간 그대로 사용. 가장 정확한 경로."""
        return SunlightResult(
            value=max(0.0, min(MAX_SUNLIGHT_HOURS, ss_day)),
            source="실측 일조시간",
            method="measurement",
            confidence=calibration()["confidence"]["measurement"],
            basis=f"실측 {ss_day:.1f}h 직접 사용",
            is_calculated=False,
        )

    @classmethod
    def from_radiation(
        cls, solar_radiation: float, latitude: float, month: int, day: int = 15
    ) -> SunlightResult | None:
        """실측 일사량(MJ/m²/day) → 일조시간 환산. 검증된 주 경로(R²=0.904).

        일사량이 물리 범위를 벗어나면(센서 이상) **None을 반환한다** — 조용히 이상값을
        일조시간으로 바꿔 내보내지 않는다(§12 경계 방어). 이 필터가 정확도의 핵심이다:
        실측 검증에서 범위 밖 값을 남겨두면 R²가 0.904 → 0.742로 떨어졌다.
        """
        cal = calibration()
        a = cal["angstrom_prescott"]["a"]
        b = cal["angstrom_prescott"]["b"]
        bounds = cal["quality_bounds"]

        doy = day_of_year(month, day)
        ra = extraterrestrial_radiation(latitude, doy)
        n_max = daylight_hours(latitude, doy)
        if ra <= 0 or n_max <= 0:
            return None  # 극야 — 환산 불가

        ratio = solar_radiation / ra
        if not (bounds["min_ratio"] <= ratio <= bounds["clear_sky_max_ratio"]):
            return None  # 물리적으로 불가능한 일사량 → 결측 취급

        value = max(0.0, min(n_max, n_max * (ratio - a) / b))  # 가조시간을 넘을 수 없다
        return SunlightResult(
            value=value,
            source="일사량 환산(역 Ångström–Prescott)",
            method="radiation",
            confidence=cal["confidence"]["radiation"],
            basis=(
                f"일사량 {solar_radiation:.1f}MJ/m²/d ÷ 지구외일사량 {ra:.1f} = {ratio:.2f}, "
                f"가조시간 {n_max:.1f}h, 계수 a={a:.3f} b={b:.3f}"
            ),
            is_calculated=True,
        )

    @classmethod
    def from_temperature(
        cls, tmax: float, tmin: float, latitude: float, month: int, day: int = 15
    ) -> SunlightResult:
        """기온 일교차 기반 폴백. **정확도가 낮아 0.90 게이트를 통과하지 못한다.**

        일교차는 맑으면 커지는 경향이 있어 흐림의 대리지표로 쓰이지만, 실측 검증에서
        보정 후에도 R²=0.496 / MAE 2.219h에 그쳤다. 참고용으로만 남긴다 —
        이 값을 적합도 채점에 쓰면 근거 없는 숫자를 확정치처럼 쓰는 셈이다(§18-4).
        """
        doy = day_of_year(month, day)
        n_max = daylight_hours(latitude, doy)
        # 보정된 Hargreaves형 계수(scripts/calibrate_sunlight.py 산출). 채점에 쓰이지
        # 않는 참고용 경로라 시드로 승격하지 않는다.
        ratio = -0.484 + 0.300 * math.sqrt(max(0.0, tmax - tmin))
        return SunlightResult(
            value=max(0.0, min(n_max, n_max * ratio)),
            source="기온 일교차 추정(정확도 낮음)",
            method="temperature",
            confidence=calibration()["confidence"]["temperature"],
            basis=f"일교차 {tmax - tmin:.1f}℃, 가조시간 {n_max:.1f}h — 참고용",
            is_calculated=True,
        )

    @classmethod
    def calculate_optimal(
        cls,
        latitude: float,
        month: int,
        measured_sunlight: float | None = None,
        solar_radiation: float | None = None,
        tmax: float | None = None,
        tmin: float | None = None,
        day: int = 15,
    ) -> SunlightResult | None:
        """가장 정확한 경로를 자동 선택. 어느 경로도 불가하면 None(값을 만들어내지 않는다).

        우선순위: 실측(0.95) → 일사량 환산(0.90) → 기온 폴백(0.50, 게이트 미통과).
        """
        if measured_sunlight is not None and measured_sunlight >= 0:
            return cls.from_measurement(measured_sunlight)

        if solar_radiation is not None and solar_radiation > 0:
            result = cls.from_radiation(solar_radiation, latitude, month, day)
            if result is not None:
                return result  # 일사량이 이상치면 아래 폴백으로 내려간다

        if tmax is not None and tmin is not None:
            return cls.from_temperature(tmax, tmin, latitude, month, day)

        return None

    @staticmethod
    def confidence_to_label(confidence: float) -> str:
        """신뢰도 → 사용자 노출 라벨. 색만으로 구분하지 않도록 라벨을 병기한다(§8)."""
        if confidence >= 0.90:
            return "높음"
        if confidence >= 0.70:
            return "보통"
        return "낮음(참고용)"

    @staticmethod
    def estimate_error_range(method: str) -> tuple[float, float]:
        """method별 ± 오차범위(hr). 홀드아웃 RMSE 실측치(시드 참조)."""
        hours = calibration()["error_range_hours"].get(method, 2.75)
        return (-hours, hours)
