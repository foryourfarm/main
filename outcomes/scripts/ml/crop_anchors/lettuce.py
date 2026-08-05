"""상추(07001) 문헌 앵커 — crop_literature_anchor_experiment.py가 import한다.
P11: 최적 22.5(추정)·실측피크 24, 생육정지 2.5~36. 수경·항온 한계."""

ANCHOR = {
    "name": "상추",
    "temp": {"allowed_min_kind": "literature_limit", "allowed_max_kind": "literature_limit", "optimal_min": 22.0, "optimal_max": 24.0, "allowed_min": 2.5, "allowed_max": 36.0,
             # 2026-08-01 사용자 결정: 연중 12개월 평균은 전국 중앙값 13.37℃로 optimal(22~24) 밖이라
             # 어느 지역도 optimal에 들 수 없었다. 봄·가을 작기로 좁힌다(월 범위는 휴리스틱, 문헌 없음).
             "months": [4, 5, 9, 10],
             "flag": "[확인 필요] 수경·항온 챔버 조건(P11), 노지 일교차 직접적용 한계. "
                     "채점월 4·5·9·10월은 노지 봄·가을 작기 휴리스틱이며 이 월 범위를 준 문헌은 없다(2026-08-01)."},
}
