"""토양변화 shadow 추론 서비스 — 입력검증 → 추론 → 폴백 → shadow 로그(핸드오프 §4, 가이드 §2).

결정론: 같은 입력이면 항상 같은 출력(Ridge·conformal 랜덤성 없음). 결측/로드실패/이상 입력에도
산출이 예외로 죽지 않는다(§18-5). P0에서는 결과를 사용자에게 노출하지 않고 DB에만 기록한다.
"""
import logging
import math
from datetime import date

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infra.ml.soil_delta import SoilDeltaArtifact, get_artifact, run_inference
from app.models import PredictionShadow, SoilStateSnapshot
from app.schemas.soil_delta import SoilDeltaPrediction, TargetPrediction

logger = logging.getLogger(__name__)

# artifact 미로드/추론 실패 시 로그에 남길 버전(진짜 예측이 아님을 구분).
FALLBACK_VERSION = "unavailable"

# artifact target 이름 → 응답/로그 목표 키 매핑.
_TARGET_KEY = {"delta_ph": "ph", "delta_organic_matter": "organic_matter"}
# 목표 키 → t0 원천 피처 이름(projected_value = t0 + delta 계산용).
_T0_FEATURE = {"ph": "ph_t0", "organic_matter": "organic_matter_t0"}

# 학습 horizon 통계(핸드오프 §2.1): p05 17일 ~ max 1,278일. 모델 메타(농업 기준값 아님).
# 구간 밖 정책은 [확인 필요] — 조용히 외삽하지 않고 limitation 플래그만 붙인다(가이드 §2.2).
HORIZON_MIN_DAYS = 17
HORIZON_MAX_DAYS = 1278

# 한계 문구(항상 응답/로그에 병기 — CLAUDE.md §1-4, §12).
LIMITATION_SHADOW = "shadow 예측 — P0에서는 사용자에게 노출하지 않음"
LIMITATION_PH_INTERVAL_HIDDEN = (
    "pH 90% 구간은 재보정 전이라 노출하지 않음(spatial 포함률 0.873)"
)
LIMITATION_ORGANIC_THEORY = "유기물 변화량은 문헌 기반 이론 추정"
LIMITATION_AVAILABLE_P = "유효인산 변화량은 모델 미채택 — available=false, Δ=0 유지"
LIMITATION_MODEL_UNAVAILABLE = "모델 artifact 미로드 — Δ=0 폴백(최신 아님)"
LIMITATION_HORIZON_OOR = "예측 기간이 학습 구간(17~1,278일)을 벗어남 — 외삽 주의"

_UNSET = object()


def _f(value: object | None) -> float | None:
    return float(value) if value is not None else None  # type: ignore[arg-type]


def _unavailable(projected: float | None) -> TargetPrediction:
    """유효인산 및 폴백 목표 공통 형태: Δ=0, 구간 없음, available=false."""
    return TargetPrediction(
        delta=0.0,
        projected_value=projected,
        lo=None,
        hi=None,
        available=False,
        prediction_type="unavailable",
        fallback_used=True,
    )


def predict_soil_delta(
    snapshot: SoilStateSnapshot,
    target_date: date,
    *,
    artifact: SoilDeltaArtifact | None | object = _UNSET,
) -> SoilDeltaPrediction:
    """스냅샷 + 목표날짜 → 토양변화 추론 DTO. DB 접근 없음(순수·테스트 가능).

    `artifact`를 명시하면 그것을 쓰고, 생략하면 로드된 캐시(`get_artifact()`)를 쓴다.
    """
    feature_as_of = snapshot.measured_at.date()
    interval_days = (target_date - feature_as_of).days

    # 입력 검증 — 모델 호출 전에 차단(핸드오프 §4.1).
    if not math.isfinite(interval_days) or interval_days <= 0:
        raise AppError(
            400,
            "INVALID_HORIZON",
            "예측 기간(target_date - 실측일)은 1일 이상이어야 합니다.",
        )

    ph_t0 = _f(snapshot.ph)
    om_t0 = _f(snapshot.organic_matter)
    ap_t0 = _f(snapshot.available_p)

    limitations = [LIMITATION_SHADOW, LIMITATION_AVAILABLE_P, LIMITATION_PH_INTERVAL_HIDDEN]
    if not (HORIZON_MIN_DAYS <= interval_days <= HORIZON_MAX_DAYS):
        limitations.append(LIMITATION_HORIZON_OOR)

    if artifact is _UNSET:
        artifact = get_artifact()

    predictions: dict[str, TargetPrediction] = {}

    if not isinstance(artifact, SoilDeltaArtifact):
        # artifact 미로드 → pH·유기물 폴백(Δ=0). 서비스는 죽지 않는다.
        model_version = data_version = FALLBACK_VERSION
        limitations.append(LIMITATION_MODEL_UNAVAILABLE)
        predictions["ph"] = _unavailable(ph_t0)
        predictions["organic_matter"] = _unavailable(om_t0)
    else:
        model_version = artifact.model_version
        data_version = artifact.data_version
        values = {
            "ph_t0": ph_t0,
            "organic_matter_t0": om_t0,
            "available_p_t0": ap_t0,
            "interval_days": float(interval_days),
        }
        try:
            inference, imputed = run_inference(artifact, values)
        except Exception:  # noqa: BLE001 — 추론 실패도 폴백(§18-5)
            logger.exception("soil_delta 추론 실패 — Δ=0 폴백")
            model_version = data_version = FALLBACK_VERSION
            limitations.append(LIMITATION_MODEL_UNAVAILABLE)
            predictions["ph"] = _unavailable(ph_t0)
            predictions["organic_matter"] = _unavailable(om_t0)
        else:
            limitations.append(LIMITATION_ORGANIC_THEORY)
            for target_name, result in inference.items():
                key = _TARGET_KEY.get(target_name)
                if key is None:
                    continue
                delta = result["point"]
                t0_used = values[_T0_FEATURE[key]]
                if t0_used is None:
                    t0_used = artifact.feature_medians.get(_T0_FEATURE[key], 0.0)
                predictions[key] = TargetPrediction(
                    delta=delta,
                    projected_value=t0_used + delta,
                    lo=result["lo"],
                    hi=result["hi"],
                    available=True,
                    prediction_type="delta_regression",
                    fallback_used=False,
                )
            return _finalize(
                model_version, data_version, feature_as_of, target_date,
                predictions, imputed, limitations, ap_t0,
            )

    return _finalize(
        model_version, data_version, feature_as_of, target_date,
        predictions, [], limitations, ap_t0,
    )


def _finalize(
    model_version: str,
    data_version: str,
    feature_as_of: date,
    target_date: date,
    predictions: dict[str, TargetPrediction],
    imputed: list[str],
    limitations: list[str],
    ap_t0: float | None,
) -> SoilDeltaPrediction:
    # 유효인산은 정상 상황에서도 항상 미채택(핸드오프 §2.1). projected_value = t0 carry-forward.
    predictions["available_p"] = _unavailable(ap_t0)
    return SoilDeltaPrediction(
        model_version=model_version,
        data_version=data_version,
        feature_as_of=feature_as_of,
        target_date=target_date,
        predictions=predictions,
        imputed_features=imputed,
        limitations=limitations,
    )


def log_shadow(
    db: Session, user_farm_id: int, prediction: SoilDeltaPrediction
) -> list[PredictionShadow]:
    """목표별 1행을 prediction_shadow에 is_exposed=false로 기록(핸드오프 §4.2)."""
    rows = [
        PredictionShadow(
            user_farm_id=user_farm_id,
            target=key,
            point=pred.delta,
            lo=pred.lo,
            hi=pred.hi,
            model_version=prediction.model_version,
            data_version=prediction.data_version,
            feature_as_of=prediction.feature_as_of,
            target_date=prediction.target_date,
            prediction_type=pred.prediction_type,
            fallback_used=pred.fallback_used,
            is_exposed=False,
        )
        for key, pred in prediction.predictions.items()
    ]
    db.add_all(rows)
    db.flush()
    return rows


def predict_and_log(
    db: Session, snapshot: SoilStateSnapshot, target_date: date
) -> SoilDeltaPrediction:
    """서비스 진입점: 추론 후 shadow 로그까지. 트랜잭션 커밋은 호출자(§10)."""
    prediction = predict_soil_delta(snapshot, target_date)
    log_shadow(db, snapshot.user_farm_id, prediction)
    return prediction
