"""상추(07001) 문헌 앵커 — crop_literature_anchor_experiment.py가 import한다.
P11: 최적 22.5(추정)·실측피크 24, 생육정지 2.5~36. 수경·항온 한계."""

ANCHOR = {
    "name": "상추",
    "temp": {"optimal_min": 22.0, "optimal_max": 24.0, "allowed_min": 2.5, "allowed_max": 36.0,
             "months": list(range(1, 13)),
             "flag": "[확인 필요] 수경·항온 챔버 조건(P11), 노지 일교차 직접적용 한계"},
}
