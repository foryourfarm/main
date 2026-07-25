"""사과(09001) 문헌 앵커 — crop_literature_anchor_experiment.py가 import한다.
농업·농촌 기후정보시스템의 적지/가능지와 공식 사례집의 4~10월을 조합해 점수화한다."""

ANCHOR = {
    "name": "사과",
    "temp": {"months": [4, 5, 6, 7, 8, 9, 10], "optimal_min": 14.5, "optimal_max": 18.5,
             "allowed_min": 13.5, "allowed_max": 19.5,
             "source": "농업·농촌 기후정보시스템 https://www.arccas.or.kr/farming/landlimit/viewinfo.do (생육기기온 적지 14.5~18.5℃, 가능지 13.5~19.5℃) + 기후변화 시나리오 활용사례집 https://www.climate.go.kr/home/CCS/_image/web_manual/climate_ref.pdf (4~10월)."},
    "documented_rules": {
        "temperature": {"optimal_min": 14.5, "optimal_max": 18.5,
                        "allowed_min": 13.5, "allowed_max": 19.5,
                        "source": "memory/Apple-정리.md §2 Table 2 (생육기온)"},
        "soil": [
            {"indicator": "ph", "optimal_min": 6.0, "optimal_max": 6.5,
             "allowed_min": 5.5, "allowed_max": 6.8,
             "source": "memory/registry.md §1; RDA 비료사용처방, 홍로품종 과실품질"},
            {"indicator": "p2o5", "optimal_min": 30.0, "optimal_max": 50.0,
             "allowed_min": 20.0, "allowed_max": 60.0, "unit": "mg/kg (Bray-1)",
             "source": "memory/registry.md §1; RDA 비료사용처방"},
            {"indicator": "ec", "optimal_min": 0.8, "optimal_max": 1.5,
             "allowed_min": 0.4, "allowed_max": 2.0,
             "source": "memory/registry.md §1 (partial)"},
        ],
    },
    "flag": "생육기 4~10월은 공식 사례집, 적지 14.5~18.5℃·가능지 13.5~19.5℃는 농업·농촌 기후정보시스템 재배적지 지표를 따른다. "
            "EC는 소규모·품종특화 근거와 1:5 물추출법 한계가 있어 partial 그대로 유지.",
}
