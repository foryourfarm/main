"""토양변화 경량 추론 — 오프라인 exporter가 만든 artifact JSON을 읽기만 한다.

Ridge 추론은 `intercept + Σ(coef·feature)` 한 줄이라 numpy/sklearn 런타임이 필요 없다
(핸드오프 §3). 앱은 절대 부팅/요청 경로에서 학습하지 않는다. artifact는 배포 단위로 교체되고
백엔드는 버전이 고정된 계수·중앙값·conformal q를 로드해 쓴다(가이드 §2.4).
"""
import hashlib
import json
import logging
from functools import lru_cache

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.config import settings

logger = logging.getLogger(__name__)

# 입력 피처 순서는 학습과 절대 동일해야 한다(핸드오프 §2.1). artifact가 다르면 로드 거부.
EXPECTED_FEATURES: tuple[str, ...] = (
    "ph_t0",
    "organic_matter_t0",
    "available_p_t0",
    "interval_days",
)

# ML 미채택 목표를 제외한, 실제 추론 가능한 목표(핸드오프 §2.1).
EXPECTED_TARGETS: tuple[str, ...] = ("delta_ph", "delta_organic_matter")


class TargetCoef(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    coef: list[float]
    intercept: float
    conformal_q: float


class SoilDeltaArtifact(BaseModel):
    """오프라인 exporter 산출 JSON의 파싱·검증 형태(핸드오프 §3.1)."""

    model_config = ConfigDict(protected_namespaces=())

    model_version: str
    data_version: str
    features: list[str]
    feature_medians: dict[str, float]
    targets: dict[str, TargetCoef]

    @field_validator("features")
    @classmethod
    def _features_must_match_order(cls, v: list[str]) -> list[str]:
        if tuple(v) != EXPECTED_FEATURES:
            raise ValueError(
                f"artifact feature 순서 불일치: {v} != {list(EXPECTED_FEATURES)}"
            )
        return v

    @field_validator("targets")
    @classmethod
    def _targets_present(cls, v: dict[str, TargetCoef]) -> dict[str, TargetCoef]:
        missing = [t for t in EXPECTED_TARGETS if t not in v]
        if missing:
            raise ValueError(f"artifact에 필수 목표 누락: {missing}")
        for name, t in v.items():
            if len(t.coef) != len(EXPECTED_FEATURES):
                raise ValueError(
                    f"목표 {name} 계수 길이 {len(t.coef)} != 피처 수 {len(EXPECTED_FEATURES)}"
                )
        return v


def load_artifact(path: str) -> SoilDeltaArtifact:
    """artifact JSON을 로드·검증한다. 재현성을 위해 sha256과 버전을 로그로 남긴다."""
    with open(path, "rb") as fh:
        raw = fh.read()
    checksum = hashlib.sha256(raw).hexdigest()
    artifact = SoilDeltaArtifact.model_validate(json.loads(raw))
    logger.info(
        "soil_delta artifact 로드: model_version=%s data_version=%s sha256=%s",
        artifact.model_version,
        artifact.data_version,
        checksum,
    )
    return artifact


@lru_cache(maxsize=1)
def get_artifact() -> SoilDeltaArtifact | None:
    """앱 수명 동안 1회 로드(캐시). 미설정/로드 실패 시 None → 서비스가 폴백한다."""
    path = settings.soil_delta_artifact_path
    if not path:
        logger.warning("soil_delta_artifact_path 미설정 — 토양변화 예측은 Δ=0 폴백")
        return None
    try:
        return load_artifact(path)
    except Exception:  # noqa: BLE001 — 로드 실패가 서비스를 막지 않게(§18-5)
        logger.exception("soil_delta artifact 로드 실패 — Δ=0 폴백")
        return None


def run_inference(
    artifact: SoilDeltaArtifact, values: dict[str, float | None]
) -> tuple[dict[str, dict[str, float]], list[str]]:
    """피처 벡터화(결측=학습 중앙값 대치) 후 목표별 point/lo/hi를 계산한다.

    반환: ({target_name: {point, lo, hi}}, imputed_features).
    같은 입력 → 같은 출력(Ridge·conformal은 랜덤성 없음, 핸드오프 §2.3).
    """
    vec: list[float] = []
    imputed: list[str] = []
    for feature in artifact.features:
        v = values.get(feature)
        if v is None:
            v = artifact.feature_medians.get(feature, 0.0)
            imputed.append(feature)
        vec.append(float(v))

    out: dict[str, dict[str, float]] = {}
    for name, t in artifact.targets.items():
        point = t.intercept + sum(c * x for c, x in zip(t.coef, vec))
        out[name] = {"point": point, "lo": point - t.conformal_q, "hi": point + t.conformal_q}
    return out, imputed
