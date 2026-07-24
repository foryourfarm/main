from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict

# `model_version` 등 model_ 접두 필드가 pydantic 보호 네임스페이스와 겹쳐 경고나므로 해제.
_CONFIG = ConfigDict(protected_namespaces=())


class TargetPrediction(BaseModel):
    """목표(pH/유기물/유효인산) 하나의 추론 결과(핸드오프 §4.1).

    projected_value = t0 + delta. lo/hi는 conformal 구간(유효인산·폴백은 null).
    available=false면 delta_regression이 아니라 unavailable(폴백/미채택)이다.
    """

    model_config = _CONFIG

    delta: float
    projected_value: float | None
    lo: float | None
    hi: float | None
    available: bool
    prediction_type: Literal["delta_regression", "unavailable"]
    fallback_used: bool


class SoilDeltaPrediction(BaseModel):
    """토양변화 추론 내부 계약(핸드오프 §4.1). shadow 로그·향후 노출의 단일 표현.

    P0에서는 사용자에게 노출하지 않는다. pH 구간(lo/hi)은 재보정 전이라
    노출 시에도 숨겨야 하지만(가이드 §2.2), 이 DTO(내부/로그용)에는 담는다.
    """

    model_config = _CONFIG

    model_version: str
    data_version: str
    feature_as_of: date
    target_date: date
    # keys: "ph" | "organic_matter" | "available_p"
    predictions: dict[str, TargetPrediction]
    imputed_features: list[str]
    limitations: list[str]
