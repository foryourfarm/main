"""`memory/indicator_dispersion.json` 로더 — 채점 규칙에 `risk_width`를 붙인다.

`scoring.py`를 순수 곡선 모듈로 유지하기 위해 파일 I/O를 여기로 분리했다. scoring.py는
백엔드 룰 엔진(`suitability_service._indicator_score`)과 점수가 갈리면 안 되는 계약이라
데이터 로딩 책임을 섞지 않는다.

파일이 없으면 예외를 던진다(조용히 종전 완충폭으로 되돌아가지 않는다) — 산출물 숫자가
어떤 감쇠폭으로 나온 것인지 모르는 상태를 만들지 않기 위함이다.
산포도 생성이 선행 단계다: `python build_indicator_dispersion.py` → 채점 스크립트.
"""
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "memory" / "indicator_dispersion.json"


@lru_cache(maxsize=1)
def load() -> dict:
    if not PATH.exists():
        raise FileNotFoundError(
            f"{PATH.name} 없음 — 먼저 build_indicator_dispersion.py를 실행한다. "
            "감쇠폭을 모르는 채로 채점하지 않는다."
        )
    return json.loads(PATH.read_text(encoding="utf-8"))


def _with_width(rule: dict, width: float | None) -> dict:
    """규칙 복사본에 risk_width 주입. 산포도가 없는 지표는 원본 그대로(완충폭 폴백)."""
    return rule if width is None else {**rule, "risk_width": width}


def soil_rule(rule: dict, indicator: str) -> dict:
    """토양 지표 규칙 + risk_width. `indicator`는 ph/organic_matter/available_p/k/ca/mg."""
    return _with_width(rule, load()["soil"].get(indicator, {}).get("risk_width"))


def temp_rule(rule: dict, crop_code: str) -> dict:
    """기온 규칙 + risk_width. 작물마다 앵커월이 달라 산포도도 작물별이다."""
    return _with_width(rule, load()["temp_by_crop"].get(crop_code, {}).get("risk_width"))
