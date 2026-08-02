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


def physical_rule(rule: dict, indicator: str) -> dict:
    """물리성 지표 규칙 + risk_width(2026-08-03). `indicator`는 slope_pct/gravel_pct.

    화학 지표와 달리 원시값이 등급코드를 %로 환산한 것이라 값이 3~6개 수준으로만 이산적이다 —
    MAD가 0이 되어 risk_width가 0으로 나오는 경우가 실제로 생긴다. 그럴 땐 주입하지 않고
    scoring.py의 완충폭 폴백에 맡긴다(조용히 값을 만들어내지 않는다).
    """
    width = load().get("physical", {}).get(indicator, {}).get("risk_width")
    return _with_width(rule, width or None)


@lru_cache(maxsize=1)
def _climate_offset() -> float:
    """문헌 밴드(평년 기준)와 관측(최근 연도 기준)의 척도 차이 보정값.

    문헌 재배적지 기준은 기상청 평년(1991~2020)을 전제로 쓰였는데 우리 채점 입력은 최근
    연도 관측이라 그대로 비교하면 계통 편차가 들어간다. `_shared.json.climate_baseline`에
    **측정된** 차이(관측 전국평균 − 평년 전국평균)를 두고 여기서 읽는다 — 추정값이 아니다.
    필드가 없으면 0.0(보정 안 함)으로 폴백한다: 조용히 값을 만들어내지 않는다.
    """
    shared = json.loads((ROOT / "memory" / "crop_rules" / "_shared.json").read_text(encoding="utf-8"))
    return float(shared.get("climate_baseline", {}).get("offset_c", 0.0))


def temp_rule(rule: dict, crop_code: str) -> dict:
    """기온 규칙 + risk_width + 평년/관측 척도 보정. 작물마다 앵커월이 달라 산포도도 작물별이다.

    보정은 밴드를 offset만큼 **상향 이동**한다(관측이 평년보다 따뜻하므로 문헌 밴드를 같은
    만큼 올려야 같은 척도가 된다). 관측값을 내리지 않는 이유는 `RegionalScore.csv`에 실린
    원시 기온이 실제 관측값 그대로여야 사람이 검증할 수 있기 때문이다.
    """
    offset = _climate_offset()
    if offset:
        rule = {**rule, **{k: rule[k] + offset
                           for k in ("optimal_min", "optimal_max", "allowed_min", "allowed_max")
                           if rule.get(k) is not None}}
    return _with_width(rule, load()["temp_by_crop"].get(crop_code, {}).get("risk_width"))
