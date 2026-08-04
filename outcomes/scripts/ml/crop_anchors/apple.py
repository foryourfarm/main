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
                       "종전 적지 14.5~18.5·가능지 13.5~19.5는 국가 적지평가의 2단계가 optimal/allowed에 정확히 대응하는 구조였다. "
                       "🔴 **한계는 「행 교차 대입」이다**(2026-08-04 재조사로 정정): 1차 출처(Kim 2016 Table 3, "
                       "knowledge-base/papers/common/mlcm-suitability-integration-kim-2016.md)는 「생육기온 14.5~18.5」와 "
                       "「생육적온 10.0~20.0」을 **별개 행·다른 값**으로 준다. 우리 밴드는 전자 행이고 여기 들어온 18~28은 "
                       "다른 책(영농순기표)의 「생육적온」이다 — 같은 출처의 생육적온 행이 10.0~20.0인데 18~28을 쓴 근거가 없다 [확인 필요]. "
                       "종전 문구는 이 한계를 '생육적온을 월평균 기온 적합구간으로 쓴 성격 오인'이라 적었으나 그 표현은 근거가 없었다 — "
                       "arccas 14.5~18.5도 영농순기표 18~28도 **집계 기준(주간/일평균/월평균)이 문헌에 없다**"
                       "(memory/open-gaps.md, knowledge-base/registry.md 조사목표 2·3에 미해결로 등재). "
                       "생육기 달력월 4~10월은 기후변화 시나리오 활용사례집 https://www.climate.go.kr/home/CCS/_image/web_manual/climate_ref.pdf 을 그대로 유지."},
    # 두 지표로 분리(2026-08-04 사용자 결정). `temp`(생육적온 18~28)와 아래 arccas 적지·가능지는
    # **서로 다른 질문에 답한다** — 앞은 "이 작물이 자랄 수 있는 기온인가", 뒤는 "국가 적지평가가
    # 이 지역을 사과 적지로 보는가"다.
    # ⚠️ 분리안의 선택지 기호는 별건 질문의 ⓒ였다 — **FinalReport §1-4의 ⓒ(보류+UI 경고)가 아니다.**
    # §1-4에 대한 팀 답변은 ⓐ(밴드 갱신)이고 그것이 위 `temp`에 반영돼 있다. 두 결정은 양립한다.
    # 🔴 분리 사유를 "성격 오인"이라 적었던 것은 정정한다 — 근거 있는 지적은 집계 기준
    # (주간/월평균) 불일치가 아니라 **행 교차 대입**이다(위 `temp` source 참조).
    #
    # 🔴 **채점하되 주 총점의 min 대상에는 넣지 않는다.** 실측: 앵커월 전국평균 20.67℃가 가능지
    # 상한 19.5를 넘어 이 지표는 93/150지역이 0점이고 전국 평균 14.7점이다. min에 넣으면 국가 3단
    # 총점이 74.9 → 12.7로 무너져 C등급 132지역이 된다(평탄 min 138지역보다 나아지지 않는다).
    # 그 숫자가 틀렸다는 뜻이 아니다 — 국가 기준으로는 한국 대부분이 이미 사과 적지가 아닐 수 있고,
    # 그 판단은 문헌이 아니라 사람이 내려야 한다 [확인 필요].
    # 하드 페널티(게이트)도 두지 않는다 — 감점 폭을 줄 문헌이 없어 만들면 휴리스틱이 된다.
    "temp_suitability_grade": {
        "optimal_min": 14.5, "optimal_max": 18.5,
        "allowed_min": 13.5, "allowed_max": 19.5,
        # 두 경계 모두 arccas 「가능지」 문헌값이다 — literature_limit(생리적 절대한계, 경계 0점)이
        # **아니다.** 가능지 밖은 "부적지"라는 적지 등급 판정이고 생장이 멈추는 점이 아니므로
        # 경계는 60점을 받아야 한다. literature_limit으로 잘못 표기하면 0점 지역이 93 → 121로
        # 늘어난다(실측). 같은 arccas 하한에 apple.json `temp`가 쓰는 표기와 맞춘다.
        "allowed_min_kind": "cultivable_range", "allowed_max_kind": "cultivable_range",
        "cultivation_type": "open_field",
        "months": [4, 5, 6, 7, 8, 9, 10],
        "scored": True, "in_total": False,
        "source": "농업·농촌 기후정보시스템 재배적지 정보 "
                  "https://www.arccas.or.kr/farming/landlimit/viewinfo.do 사과 생육기기온: "
                  "적지 14.5~18.5℃, 가능지 13.5~14.5·18.5~19.5℃, 그 밖 부적지. "
                  "적지/가능지 2단계가 optimal/allowed에 정확히 대응하므로 두 경계 모두 "
                  "문헌값이다(휴리스틱 없음). 앵커월 4~10월은 기후변화 시나리오 활용사례집 "
                  "https://www.climate.go.kr/home/CCS/_image/web_manual/climate_ref.pdf 을 따른다. "
                  "[확인 필요] arccas가 '생육기기온'을 어떤 기준기간·관측고도·공간해상도로 "
                  "산출했는지 미확인 — 우리 4~10월 산술평균과 동일하다는 보장이 없다."},
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
