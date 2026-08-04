"""추천 문구를 조립하는 공용 순수 헬퍼 — 단기(`advice_service`)·장기(`long_term_advice_service`) 공용.

**왜 모듈을 나눴나**: 두 서비스가 같은 규칙으로 문장을 만들어야 한다. 받침 조사·경계 표현·소수
표기가 갈리면 같은 제품 안에서 말투가 두 개가 된다. 원래 `advice_service`에 `_` 접두로 있던
것을 장기 쪽이 쓰게 되면서 올렸다 — 모듈 밖에서 `_` 이름을 import하는 것보다 낫다.

**여기 있는 것은 전부 순수 함수다.** DB·설정·LLM을 타지 않으므로 테스트가 값만 보면 된다.
"""

from typing import Protocol

# 지표 단위. 표기용이라 농업 기준값이 아니다(기준값은 crop_growth_guide, CLAUDE.md §18-2).
UNITS: dict[str, str] = {
    "temp_day": "℃",
    "temp_night_min": "℃",
    "rainfall_daily": "mm",
    "rainfall_monthly": "mm",
    "sunlight": "시간",
}

RISK_SUFFIX = ":outside_allowed"


class Bounded(Protocol):
    """`bound_phrase`가 필요로 하는 최소 모양. 두 서비스가 각자의 dataclass를 그대로 넘긴다.

    구조적 타이핑이라 상속이 필요 없다 — 단기의 `RiskLine`과 장기의 `MonthRisk`는 서로를
    몰라도 되고, 알 이유도 없다(한쪽은 날짜, 다른 쪽은 연·월을 갖는다).
    """

    @property
    def value(self) -> float: ...
    @property
    def allowed_min(self) -> float | None: ...
    @property
    def allowed_max(self) -> float | None: ...


def num(value: float) -> str:
    """소수점 꼬리 정리. 3.0 -> "3", 3.20 -> "3.2"."""
    text = f"{value:.1f}"
    return text[:-2] if text.endswith(".0") else text


def subject_josa(word: str) -> str:
    """주격 조사 — 받침 있으면 "이", 없으면 "가".

    "이(가)"로 뭉개지 않는 이유: 규칙 문구는 LLM 실패 시 **그대로 유저에게 나가는** 최종
    문구다. 지표 한글명이 시드가 아니라 코드 상수(INDICATOR_NAMES)라 받침이 고정이므로
    한글 음절 계산으로 정확히 고를 수 있다.
    """
    # 괄호 병기는 떼고 본 이름으로 고른다 — "토양 산도(pH)이"가 아니라 "토양 산도가"다.
    stem = word.split("(")[0].strip() or word
    last = stem[-1]
    if "가" <= last <= "힣":
        return "이" if (ord(last) - 0xAC00) % 28 else "가"
    return "이"  # 숫자·영문으로 끝나면 판정 불가 — 덜 어색한 쪽으로 고정


def bound_phrase(line: Bounded, unit: str) -> str | None:
    """어느 쪽 경계를 벗어났는지. 지침에 그 경계가 없으면 None(범위를 지어내지 않는다)."""
    if line.allowed_min is not None and line.value < line.allowed_min:
        return f"허용 범위({num(line.allowed_min)}{unit} 이상)"
    if line.allowed_max is not None and line.value > line.allowed_max:
        return f"허용 범위({num(line.allowed_max)}{unit} 이하)"
    return None
