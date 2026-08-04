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
    허용경계에서 감쇠폭 밖          0

허용구간과 위험구간에 같은 로그 곡률을 반대로 걸어 전체가 정규분포 한쪽 날개 모양이 된다.

**감쇠폭(2026-07-29 개정)**: 종전엔 완충폭(허용~최적 간격) 1배를 감쇠 거리로 썼다. 완충폭은
`allowed = optimal 폭 ±50%` 휴리스틱에서 나오므로 optimal이 좁은 지표는 완충폭도, 위험구간도
함께 좁아졌다 — 3중 압축이라 채점이 사실상 이진이 됐다(상추 pH 0점 107/150, 사과 기온
0점 92/150). 이제 규칙에 `risk_width`(그 지표의 전국 실측 산포도 기반 절대폭,
`memory/indicator_dispersion.json`)가 있으면 그걸 감쇠 거리로 쓴다. 없으면 종전대로
완충폭 1배로 폴백한다 — 산포도를 낼 수 없는 지표에서 조용히 값을 만들어내지 않는다.

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
# 🔴 이 성격의 허용경계만 0점이 된다(2026-08-04). 백엔드 `suitability_service`의
# 같은 이름 상수와 반드시 같아야 한다 — 두 구현의 점수가 갈리면 안 되는 계약이다.
LITERATURE_LIMIT_KIND = "literature_limit"


def _log_falloff(x):
    """x=1 → 1, x=0 → 0인 로그 계수. 1 근처는 평평하고 0 근처에서 가파르다."""
    return log1p(DECAY_CURVATURE * x) / log1p(DECAY_CURVATURE)


def boundary_score(kind):
    """허용경계에 줄 점수. 그 경계의 **성격**이 정한다.

    종전에는 성격과 무관하게 일괄 60점(B등급 하한)이었다. 그런데 그 칸에는 ±50% 휴리스틱과
    **문헌이 준 생리적 절대한계**가 섞여 있었고, 후자는 생장이 완전히 멈추는 점인데 60점을
    받고 있었다. `literature_limit`만 0점으로 내린다 — 나머지 성격은 60점을 유지한다
    (2026-08-04 사용자 결정: *"literature_limit만 0점, 나머지 60점 유지"*).

    성격은 밴드 JSON의 `allowed_min_kind`/`allowed_max_kind`에 **방향별로** 적혀 있다.
    한 밴드 안에서 두 경계의 성격이 갈리기 때문이다 — 사과 기온은 하한이 arccas 가능지
    문헌값이고 상한은 ±50% 휴리스틱이다.
    """
    return 0.0 if kind == LITERATURE_LIMIT_KIND else ALLOWED_BOUNDARY_SCORE


def _allowed_score(nearness, boundary=ALLOWED_BOUNDARY_SCORE):
    """허용구간 점수. `nearness`는 최적경계에 얼마나 가까운지(1=최적경계, 0=허용경계).

    `boundary`가 0이면 곡선이 0→95로 펴져 척도가 넓어진다(감쇠 척도가 60~95에 압축돼
    너무 납작하다는 지적에 대한 답).
    """
    return boundary + (OPTIMAL_EXIT_SCORE - boundary) * _log_falloff(nearness)


def _risk_score(overshoot, buffer, risk_width=None, boundary=ALLOWED_BOUNDARY_SCORE):
    """허용구간 밖 감쇠. 감쇠폭은 `risk_width`(전국 실측 산포도 기반)를 우선 쓰고,
    없으면 완충폭 1배로 폴백한다. 둘 다 없으면 척도를 정할 수 없어 종전대로 0점.

    `boundary`가 0(생리적 절대한계)이면 이 구간 전체가 0이다 — 생장이 멈춘 지점을 이미
    지났으므로 그 밖에 감쇠할 여지가 없다."""
    width = risk_width if risk_width and risk_width > 0 else buffer
    if width <= 0:
        return 0.0
    t = overshoot / width
    if t >= 1:
        return 0.0
    return boundary * (1 - _log_falloff(t))


def band_score(value, rule):
    """문헌 밴드 대비 편차 점수(0~100). 결측·규칙없음은 NaN — 강제 대체 금지.

    단측 밴드(2026-08-02): `optimal_min`/`optimal_max` 중 하나가 None이면 그 방향엔
    감점을 두지 않는다. 문헌이 한쪽 경계만 주는 지표를 위한 것이다 — 예: RDA 사과 교본
    표5-21 치환성 Ca "5~6 cmol/kg **이상**"은 상한 붕괴점을 주지 않는다. 없는 상한을
    휴리스틱으로 만들면 정상 토양을 근거 없이 감점하게 된다(추측 금지).
    이건 절벽(이진 채점) 도입이 아니다 — 그 방향에 절벽도 taper도 두지 않는 것이다.
    """
    if value is None or rule is None or pd.isna(value):
        return np.nan
    lo, hi = rule["optimal_min"], rule["optimal_max"]
    if lo is None and hi is None:
        raise ValueError("optimal_min·optimal_max가 둘 다 없는 규칙은 채점할 수 없다")
    alo, ahi = rule.get("allowed_min"), rule.get("allowed_max")
    risk_width = rule.get("risk_width")
    if (lo is None or lo <= value) and (hi is None or value <= hi):
        return 100.0
    if lo is not None and value < lo:
        if alo is None:
            return 0.0
        # 경계 점수는 그 **방향**의 성격이 정한다(2026-08-04). 키가 없으면 60점 —
        # 성격 표기가 없는 밴드의 채점을 종전과 동일하게 유지한다.
        boundary = boundary_score(rule.get("allowed_min_kind"))
        if value >= alo:
            return _allowed_score((value - alo) / (lo - alo), boundary)
        return _risk_score(alo - value, lo - alo, risk_width, boundary)
    if ahi is None:
        return 0.0
    boundary = boundary_score(rule.get("allowed_max_kind"))
    if value <= ahi:
        return _allowed_score((ahi - value) / (ahi - hi), boundary)
    return _risk_score(value - ahi, ahi - hi, risk_width, boundary)
