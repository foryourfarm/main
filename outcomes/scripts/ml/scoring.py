"""문헌 밴드 → 0~100 점수 변환. 채점 스크립트가 공유한다.

메인 프로젝트 룰 엔진(`backend/app/services/suitability_service.py`의 `_indicator_score`)과
**같은 곡선**이다. 이 산출물은 그쪽으로 이관되는 계약이라 두 구현의 점수가 갈리면 안 된다 —
곡선을 바꿀 땐 양쪽을 같이 바꾼다.

곡선(2026-07-27 사용자 결정, 선형·이차·로그 중 로그 채택):

    최적구간 안                  100
    최적경계 벗어나는 순간        95   (이탈 자체에 붙는 고정 감점)
    허용구간                     95 → 60, 최적 근처는 완만하고 허용경계에 다가갈수록 급락
    허용경계                      60   (B등급 하한)
    허용경계 밖                  60 → 0, 급락 후 완만한 꼬리
    최적경계에서 완충폭 2배 밖      0

허용구간과 위험구간에 같은 로그 곡률을 반대로 걸어 전체가 정규분포 한쪽 날개 모양이 된다.
감쇠 거리는 새 상수를 만들지 않고 지침에 이미 있는 완충폭(허용~최적 간격)을 그대로 쓴다.

이전 곡선과의 차이(산출 CSV 숫자가 전부 바뀐다): 예전엔 허용경계가 0점이고 허용구간이
0→100 선형이었다. 즉 허용구간 안이어도 경계 근처면 0점에 가까웠고, 경계를 조금만 넘어도
즉시 0점이었다. 지금은 허용구간이 60~95, 경계 밖도 완충폭 1배에 걸쳐 점진 감점된다.
"""
from math import log1p

import numpy as np
import pandas as pd

ALLOWED_BOUNDARY_SCORE = 60.0
OPTIMAL_EXIT_SCORE = 95.0
DECAY_CURVATURE = 9.0


def _log_falloff(x):
    """x=1 → 1, x=0 → 0인 로그 계수. 1 근처는 평평하고 0 근처에서 가파르다."""
    return log1p(DECAY_CURVATURE * x) / log1p(DECAY_CURVATURE)


def _allowed_score(nearness):
    """허용구간 점수. `nearness`는 최적경계에 얼마나 가까운지(1=최적경계, 0=허용경계)."""
    return ALLOWED_BOUNDARY_SCORE + (OPTIMAL_EXIT_SCORE - ALLOWED_BOUNDARY_SCORE) * _log_falloff(
        nearness
    )


def _risk_score(overshoot, buffer):
    """허용구간 밖 감쇠. 완충폭이 없으면 척도를 정할 수 없으므로 종전대로 0점."""
    if buffer <= 0:
        return 0.0
    t = overshoot / buffer
    if t >= 1:
        return 0.0
    return ALLOWED_BOUNDARY_SCORE * (1 - _log_falloff(t))


def band_score(value, rule):
    """문헌 밴드 대비 편차 점수(0~100). 결측·규칙없음은 NaN — 강제 대체 금지."""
    if value is None or rule is None or pd.isna(value):
        return np.nan
    lo, hi = rule["optimal_min"], rule["optimal_max"]
    alo, ahi = rule.get("allowed_min"), rule.get("allowed_max")
    if lo <= value <= hi:
        return 100.0
    if value < lo:
        if alo is None:
            return 0.0
        if value >= alo:
            return _allowed_score((value - alo) / (lo - alo))
        return _risk_score(alo - value, lo - alo)
    if ahi is None:
        return 0.0
    if value <= ahi:
        return _allowed_score((ahi - value) / (ahi - hi))
    return _risk_score(value - ahi, ahi - hi)
