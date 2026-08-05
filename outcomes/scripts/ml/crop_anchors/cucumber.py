"""오이(04009) 문헌 앵커 — crop_literature_anchor_experiment.py가 import한다.
2026-07-25 재설계: 제주특별자치도 농업기술원 과채류(오이) 재배기술서(노지 실제값,
cucumber-field-cultivation-literature.md) 기반. P14(강소라, 시설 22-28)는 사용자
확인으로 채점 소스에서 교체되었고 environment_rules에 참고용으로만 남는다."""

ANCHOR = {
    "name": "오이",
    "temp": {"allowed_min_kind": "literature_limit", "allowed_max_kind": "literature_limit", "optimal_min": 25.0, "optimal_max": 28.0, "allowed_min": 5.0, "allowed_max": 35.0,
             "months": [4, 5, 6, 7, 8, 9],
             "flag": "2026-07-25 사용자 확인으로 P14(시설, 22~28) → 제주 농업기술원 노지 문헌(25~28)으로 "
                     "교체 — crop_code 04009가 코드북상 노지재배인데 시설값을 외기 근사하던 기존 [확인 필요]가 "
                     "해소됨. allowed_min=5/allowed_max=35는 문헌이 직접 준 생육중지 임계치(휴리스틱 아님, "
                     "이진 채점 문제 자체가 없음). 채점 월은 기존과 동일 주 생육기(4-9월) 유지(문헌도 달력월 "
                     "미제공, 연평균 전체 사용시 전지역 0점 붕괴 확인된 기존 결정 재사용)."},
    # P14(시설) 문헌 조사 결과 — 2026-07-25부터 채점에는 미사용, 참고용으로만 보존.
    "environment_rules": [
        {"environment": "Air Temperature (°C)", "min": 22, "max": 28, "optimal": 25, "source": "P14"},
        {"environment": "Night Temperature (°C)", "min": 18, "max": 20, "optimal": 19, "source": "P14"},
        {"environment": "Relative Humidity (%)", "min": 70, "max": 85, "optimal": 80, "source": "P14"},
        {"environment": "Soil Temperature (°C)", "min": 20, "max": 25, "optimal": 22, "source": "P14"},
        {"environment": "CO2 (ppm)", "min": 600, "max": 1000, "optimal": 800, "source": "P14"},
    ],
    "flag": "P14는 참고용으로만 보존(2026-07-25부터 채점 미사용, 실제 노지 문헌으로 교체됨). "
            "습도·지온·CO2는 지역 기상 데이터 없어 여전히 미반영.",
}
