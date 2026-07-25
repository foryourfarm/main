"""배(09011) 문헌 앵커 — crop_literature_anchor_experiment.py가 import한다.
공식 재배적지 적지/가능지와 농진청의 4~10월 생육기를 조합해 점수화한다."""

ANCHOR = {
    "name": "배",
    "temp": {"months": [4, 5, 6, 7, 8, 9, 10], "optimal_min": 18.5, "optimal_max": 21.5,
             "allowed_min": 17.0, "allowed_max": 23.0,
             "source": "농업·농촌 기후정보시스템 https://www.arccas.or.kr/farming/landlimit/viewinfo.do (생육기기온 적지 18.5~21.5℃, 가능지 17~23℃) + 농촌진흥청 과수재배적지도 https://weather.rda.go.kr/ftrMap.do (4~10월)."},
    "documented_rules": {
        "growing_temp": {"months": [4, 5, 6, 7, 8, 9, 10], "target": 20.0,
                         "source": "농촌진흥청 과수재배적지도 https://weather.rda.go.kr/ftrMap.do (기준연도 1980-2010): 생육기 4~10월 평균기온 20℃"},
        "gis_land_suitability_temp": {"optimal_min": 15.0, "optimal_max": 18.0,
                         "allowed_min": 13.5, "allowed_max": 19.5,
                         "source": "memory/PearSummary.md §GIS 적지평가 Table 1 (S1~S3). [확인 필요] 달력월 미명시인 GIS 적지등급 기준이라 지역 월평균 채점에는 미사용."},
        "annual_temp": {"optimal_min": 8.0, "optimal_max": 11.0,
                        "allowed_min": 6.5, "allowed_max": 14.0,
                        "source": "memory/PearSummary.md §GIS 적지평가 Table 1 (S1~S3)"},
    },
    "flag": "농업·농촌 기후정보시스템 재배적지 지표의 적지 18.5~21.5℃·가능지 17~23℃와 농진청 자료의 4~10월을 따른다. "
            "출처불명 legacy 2~11월 값은 사용하지 않는다.",
}
