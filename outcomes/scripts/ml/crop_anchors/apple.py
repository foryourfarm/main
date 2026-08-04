"""사과(09001) 문헌 앵커 — crop_literature_anchor_experiment.py가 import한다.
농업·농촌 기후정보시스템의 적지/가능지와 공식 사례집의 4~10월을 조합해 점수화한다."""

ANCHOR = {
    "name": "사과",
    # 2026-08-04 교체(FinalReport §1-4 ⓐ). 종전 optimal 14.5~18.5는 arccas 「적지」였는데
    # 앵커월 전국평균이 20.63℃라 상한 밖으로 밀려 기온 점수가 평균 22.3점으로 무너져 있었다.
    # 🔴 allowed_min 13.5만 arccas 「가능지」 문헌값으로 남기고 allowed_max는 ±50% 휴리스틱이다
    # — 두 경계의 성격이 다르므로 apple.json이 allowed_min_kind/allowed_max_kind로 구분한다.
    "temp": {"allowed_min_kind": "cultivable_range", "allowed_max_kind": "heuristic", "months": [4, 5, 6, 7, 8, 9, 10], "optimal_min": 18.0, "optimal_max": 28.0,
             "allowed_min": 13.5, "allowed_max": 33.0,
             "source": "RDA 농사로 주요작물 영농순기표 p.141 사과 생육적온 18~28℃ (2026-08-04 채택). "
                       "allowed_min 13.5는 농업·농촌 기후정보시스템 https://www.arccas.or.kr/farming/landlimit/viewinfo.do 의 가능지 하한(문헌값), "
                       "allowed_max 33.0은 optimal 폭(10) ±50% 휴리스틱 [확인 필요]. "
                       "종전 적지 14.5~18.5·가능지 13.5~19.5는 국가 적지평가의 2단계가 optimal/allowed에 정확히 대응하는 구조였다 — "
                       "생육적온을 월평균 기온 적합구간으로 쓰는 것은 성격 오인일 수 있다 [확인 필요]. "
                       "생육기 달력월 4~10월은 기후변화 시나리오 활용사례집 https://www.climate.go.kr/home/CCS/_image/web_manual/climate_ref.pdf 을 그대로 유지."},
    "documented_rules": {
        "temperature": {"optimal_min": 14.5, "optimal_max": 18.5,
                        "allowed_min": 13.5, "allowed_max": 19.5,
                        "source": "memory/Apple-정리.md §2 Table 2 (생육기온)"},
        "soil": [
            {"indicator": "ph", "optimal_min": 6.0, "optimal_max": 6.5,
             "allowed_min": 5.5, "allowed_max": 6.8,
             "source": "memory/registry.md §1; RDA 비료사용처방, 홍로품종 과실품질"},
            # ⚠️ 채점 배선 금지(2026-08-02). 이 밴드는 **Bray-1 추출법** 기준이고, 우리 토양
            # 데이터(`data/01_soil_chemistry_modified.csv`의 `available_p`)는 중앙값 419.7
            # mg/kg·범위 62~1289로 **약 10배 다른 스케일**이다(추출법 계열이 다름 —
            # knowledge-base/registry.md §5 "측정법 불일치가 지표값을 6배까지 벌린다" 참고).
            # 이 값을 `_shared.json`/`soil_overrides`로 옮기거나 band_score에 넘기면 전 지역이
            # 상한 밖으로 떨어진다. 흙토람 반환값의 추출법이 확인될 때까지 기록용으로만 둔다.
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
