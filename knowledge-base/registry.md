# 도메인 지식 명세서 (Registry)
마지막 갱신: 2026-08-04 (Delta: Iteration 9 — 배 ec/organic/p2o5 3개 **missing→partial 최초 전환**, 신규 다운로드 없이 기존 사과배치 논문(Ahn 2011 전북 110개소)의 배 부수데이터 재발견으로 반영. 배 냉해(개엽기/만개기) 후보 4편 신규 확보, 원문 확보 대기중)
누적 처리 논문 수: 61 (Iteration 9: 신규 md 파일 추가 없음 — 기존 파일 재조명, 배 6/13→9/13 상세 §6-5)

> **Iteration 4 반영 경위**: 이 13편은 이번 갱신 이전에 이미 `knowledge-base/papers/{cucumber,lettuce,potato}/`에 파일로 커밋돼 있었으나(각 파일 말미에 `Registry Delta` 블록 존재), registry-keeper가 실행되지 않아 이 문서에는 한 번도 집계되지 않은 상태였다. 이번에 각 파일의 Registry Delta를 읽어 소급 반영했다.

> 이 파일은 DB.md의 `crop_growth_guide`, `soil_change_rule` 스키마를 기준으로 무엇이
> 채워졌고 무엇이 비었는지만 압축해서 담습니다. 논문 본문은 `papers/` 폴더에만 존재합니다.

## 1. crop_growth_guide 커버리지

| crop | indicator | growth_stage | optimal range | allowed range | weight | status | source(s) |
|---|---|---|---|---|---|---|---|
| 사과 | temp_day(fruit_growth/maturity, 선형관계) | fruit_growth+maturity | (구간 아님) 확장속도=0.062~0.075mm/day 증가 per℃(6~20℃), 고온↑→SSC/착색↑·경도/전분↓(성숙가속) | - | - | **partial(2026-08-03, 독립근거 3건)** | papers/apple/apple-fruit-growth-maturity-temperature-warrington-1999.md(인용155, NZ HortResearch 정밀통제환경). papers/apple/apple-taste-texture-climate-change-sugiura-2013.md(인용143, 일본 40년 포장실측). **2026-08-03 국내 3번째 독립근거**: papers/apple/apple-temperature-phenology-fruit-quality-lee-2023.md(인용19, 강원 춘천 20년 실측, 후지·홍로) — 온도상승↑→발아·개화 가속(홍로>후지), 홍로는 과중·당도도 유의개선하나 후지는 무관. 3편 모두 같은 방향(고온↑→생육가속) 수렴, **품종별 반응차(후지 둔감 vs 홍로 민감)라는 새 축 추가**(품종 미구분 스키마와 충돌, §5). **한계**: 3편 모두 "적정범위"가 아니라 "온도-속도/추세 관계"라 optimal_min/max 형태로 직접 대입 불가 |
| 사과 | temp_day(coloring, 착색기) | coloring | - | - | - | **partial(2026-08-03 최초 전환)** | Iteration 4 — 기존 시드 12~13℃가 실은 "야간저온 또는 일교차" 문헌이 잘못 매핑된 것으로 의심됨(Wang et al. 2018/이주영 2011의 오이 사례와 동일 계열 이슈). Ryu et al.(2017)이 야간온도(temp_night_min 행)를 filled로 채웠으나 낮기온 자체는 missing으로 남아있었음. **2026-08-03**: papers/apple/apple-coloring-sugar-gene-expression-hongro-kim-2016.md(국내 홍로, 항온챔버 25/30/35℃ 처리) — 25℃(양호) vs 30~35℃(착색·당관련 유전자 발현 모두 크게 억제)로 registry상 유일한 순수 missing 항목을 최초로 partial 전환. Ryu(2017)의 야간온도 임계(≈25℃ 경계)와 방향·임계점대가 수렴. **한계**: 항온챔버 적출과실 처리라 포장 대기 낮기온과 간접 대응 — 포장 실측 전까지 정식 filled 아님 |
| 사과 | temp_night_min(coloring, 착색기, **최초 filled**) | coloring | LNT(저온) ≈ 야간 20.1~23.4℃(착색 촉진) | HNT(고온) ≈ 야간 26.1~29.4℃(착색 억제, 회피 권장) | - | **filled(2026-08-03)** | papers/apple/apple-coloring-night-temperature-hongro-ryu-2017.md — RDA 국립원예특작과학원(완주) 실측, 홍로 품종, 완주 30년 평년 야간기온(23.1~26.4℃) 기준 ±3℃ 처리. 안토시아닌 생합성 유전자(MdCHS 등 5종) 발현이 저온에서 최대 3배↑, 고온에서 억제. **한계**: 2수준(±3℃) 비교라 정확한 임계점은 아님. 만개후 70~131일 구간 한정 실험이라 기존 시드의 착색기 정의(day_of_year 233~293)와의 정합성은 팀 검토 필요(§5) |
| 사과 | ph | 전기간 | 6.0~6.5 | 5.5~6.8 | - | filled | RDA 비료사용처방, 홍로품종 과실품질 |
| 사과 | ec | 전기간 | 0.8~1.5 | 0.4~2.0 | - | **partial(2026-08-03 재검토 신호)** | papers/apple/hongro-fruit-quality-soil-2009.md(N=60, 품종특화), papers/apple/sod-orchard-soil-acidity-2009.md(N=4처리, 초생), papers/apple/organic-apple-manual-soil-management.md(범위값). **한계**: 소규모 조사+매뉴얼만. national-scale 검증 부재. RDA TRKO202100009605(농업환경자원변동평가 5차사업, 2021) 재시도(2026-08-02, 2026-08-03)에도 PDF 원문 다운로드 실패(ScienceON에서 초록/목차까지는 접근, EC 단위 표기 불일치 발생 — 원문 재확인 필요) — NTIS/RDA 직접 문의 필요. 김이현 외(2019)·정승탁 외(2022, 연도정정: 기존기록 2021은 오류)는 서지정보만 확정, 초록 텍스트 미확보. **2026-08-03 교차검증(해외)**: papers/apple/apple-ec-organic-conventional-gasparatos-2011.md(그리스, 관행 1.22 dS/m vs 유기 0.91 dS/m, P<0.01) — 1:1법이라 한국표준(1:5) 불일치, 직접대입 불가. **2026-08-03 국가기준 확인**: papers/apple/apple-soil-optimum-range-landuse-kang-2014.md(RDA-NAAS, 전 토지이용형태 공통) — EC≤2.0 dS/m가 기존 allowed_max(2.0)의 국가기준 출처로 확인됨(단 "과수원" 통합기준, 사과 단독 아님). **2026-08-03 지역실측(전북)**: papers/apple/apple-topography-soil-jeonbuk-ahn-2011.md(110개소 중 사과) — 사과 EC 실측평균 **0.5 dS/m로 기존 optimal(0.8~1.5)보다 낮게 관찰됨** — 기존 optimal 추정범위 자체를 재검토해야 할 신호일 수 있음(§5 Iteration 8 신규 이슈). national-scale 검증 여전히 미해결 |
| 사과 | ec(측정법, **reference_only**) | - | - | - | - | **filled(방법론, 2026-08-03 원문 확보)** | papers/apple/apple-ec-fdr-hilhorst-calibration-lee-2023.md — FDR센서(TEROS12) bulk EC를 σb=0 보정 후 Hilhorst모델로 pore water EC 추정 시 RMSE 2.49→1.52 개선, 1:5물추출법 EC와의 관계식 RMSE=0.20. **optimal_range(0.8~1.5) 값 출처 아님**, 상추 Lee(2003)와 동일 패턴. ⚠️폰트손실로 σb=0 추정치(3.55/4.1) 일부 불확실 |
| 사과 | organic | 전기간 | 일반재배 실측 12~35 g/kg(평균 21±6, N=60 홍로농가) — 당도/경도/착색 전부(+)방향 기여(16~17%) / 유기재배 RDA 목표 30~40 g/kg | 15~35(일반, root-zone 논문 근사치와 유사) | - | **partial(중요도 재평가, 2026-08-03)** | papers/apple/hongro-fruit-quality-soil-2009.md(N=60 실측범위), papers/apple/organic-apple-manual-soil-management.md(RDA 유기재배 목표치). **한계**: 두 수치가 서로 다른 모집단(일반재배 관찰범위 vs 유기재배 처방목표) — 30~35만 겹침, 그대로 합치면 안 됨. papers/apple/sod-orchard-soil-acidity-2009.md는 18개월 단기관찰(16~21g/kg)이라 보조참고만. **2026-08-03 전용연구 확보(해외)**: papers/apple/apple-organic-groundcover-management-merwin-1994.md(미국 코넬대, 6년 실험, 인용138) — "관리방식(멀칭 권장)"이 유기물·수량에 미치는 메커니즘 실증, 다중회귀의 "유기물-수량 음의 상관"은 인공적 결과(artifact)로 왜곡 해석 금지. **2026-08-03 중요도 재평가(국내)**: papers/apple/apple-soil-contribution-hongro-kim-2012.md(홍로 60농가) — 유기물의 과중/당도/착색/종합품질 기여율이 **0.1~5.6%로 지속적으로 낮음**(토양 물리성이 화학성보다 더 중요) — Merwin(1994)의 회귀왜곡 경고와 궤를 같이해 "유기물이 핵심 결정인자가 아닐 수 있다"는 2번째 독립 신호 |
| 사과 | p2o5 | 전기간 | 30~50 mg/kg | 20~60 | - | filled | RDA 비료사용처방 (Bray-1) |
| 사과 | p2o5_유기 | 전기간 | 40~60 mg/kg | 25~80 | - | filled | 유기재배 매뉴얼 |
| 사과 | p2o5_실제시비 | 전기간 | 10~12 kg/10a | +20% 현장보정 | - | filled | 협회 가이드 |
| 사과 | p2o5_실태 | 전기간 | 평균 22.5 kg/10a | (극단적 과잉) | - | partial | 실태조사 805농가. **2026-08-03 원인분석 보강**: papers/apple/apple-p2o5-legacy-overapplication-sharpley-2013.md(인용1040, "legacy P" 개념 — 토양 P는 작물흡수보다 빠르게 누적되며, 실측 사례에서 시비를 완전히 끊어도 7~27년간 유의한 감소가 없음) — 사과·한국 특정 연구는 아니나 구조적 설명 제공. **2026-08-03 사과 특이적 지역실측 확보**: papers/apple/apple-topography-soil-jeonbuk-ahn-2011.md(전북 110개소 중 사과) — 유효인산 631 mg/kg(Lancaster법)로 RDA 적정수준(200~300)의 **2.1~3.2배 과잉**을 사과 특이적으로 재확인. ⚠️Lancaster법 수치라 registry의 Bray-1 기준(30~50mg/kg)과 단위체계 상이(같은 배치 papers/apple/apple-soil-optimum-range-landuse-kang-2014.md의 과수원 300~550mg/kg과 동일 계열) — 측정법 혼재 주석 필요. optimal_range 수치 변경 없음, 구조적 이해만 보강 |
| 사과 | temp_max(고온피해) | 전기간 | 회피 31°C↑ | - | - | filled | Iteration 2-2 (기온 영향) |
| 사과 | frost_damage_budburst | 개엽기 | -5.0°C(10%), -9.4°C(90%) | - | - | filled | Iteration 2-2 (냉해 임계) |
| 사과 | frost_damage_fullbloom | 만개기 | -2.2°C(10%), -3.9°C(90%) | - | - | filled | Iteration 2-2 (냉해 임계) |
| 사과 | gdd(적산온도) | 전기간 | ∑[(Tmax+Tmin)/2 - Tbase] | - | - | partial(2026-08-03 재인용함정 해결) | Iteration 2-2 (베이스온도 작물별 확정 필요). 국내 후보 4편(Lee 2015·김진희 2019·김수옥·윤진일 2010 등) 전부 GDD가 아니라 냉각요구시간(chilling_requirement) 계열로 재분류(기각). papers/apple/apple-gdd-growth-anna-cepeda-2021.md(콜롬비아)의 Tbase=7.22℃는 Chaves et al.(2017)의 재인용치라 기각. **2026-08-03 원 출처 확보**: papers/apple/apple-gdd-fruit-diameter-chaves-2017.md(Acta Hortic. 1160:335-340, 워싱턴주 11지점×4개년 실측) — **Tbase=7.22℃('Cripps Pink')/5.55℃('Gala')/6.11℃('Red Delicious')가 재인용이 아니라 Von Bertalanffy 커브핏으로 직접 도출된 값**임을 확인(재인용 체인의 진짜 원출처 도달). **한계**: 미국 품종 3종 한정, 후지·홍로 등 한국 주력품종 값은 아님 — Tbase는 missing→**partial로 격상**(filled는 아님, 국내 품종 실측 필요) |
| 사과 | chilling_requirement(냉각요구시간, **신규 지표**) | 휴면기(만개후 ~255일까지 역산) | Chilling Hours model 666시간 / Utah model 517 CU | - | - | **filled(2026-08-02 신규)** | Lee, Park & Park(2015), Horticultural Science and Technology 33, DOI 10.7235/hort.2015.15010, 인용5 — 충주 지역 후지(Fuji) 실측, conflict-checker 원문 초록 직접 확인. **주의**: GDD(생육기 적산온도, 가온 축적)와 물리적으로 반대 방향(휴면타파, 냉각 축적) 개념이므로 gdd.Tbase와 절대 혼동 금지. DB 스키마에 이 지표 자체가 없음(완전 신규) — 팀 결정 필요. 인용수 5로 기준 미달이나 "공백 지표" 예외 적용, 단일 품종·단일 지역 한계 명시. **2번째 독립 근거(2026-08-03)**: papers/apple/apple-fuji-phenology-prediction-kim-yun-2010.md(경기도 후지) — Chill Day 모형 기준온도 6.1℃/냉각요구도 -100.5 chill-day. **주의**: Lee(2015)와 모델체계 자체가 다름(Chilling Hours/Utah vs Chill Day)라 두 수치를 직접 비교·평균 불가, "냉각요구시간이 실재하고 모델·지역에 따라 다르게 추정됨"을 독립 재확인하는 용도로만 병기 |
| 사과 | forcing_requirement_bloom(개화강제요구량, **신규 지표 후보**) | 내생휴면해제~만개 | anti-chill day 275.1(기준온도 6.1℃) | - | - | partial | papers/apple/apple-fuji-phenology-prediction-kim-yun-2010.md — 경기도 후지, DVS모델(RMSE 2.5일) 대비 정확도 개선(RMSE 1.7일, 2000~2008 검증). GDD와 개념적으로 유사(온도 축적량)하나 대상 시기가 "휴면해제~개화"로 gdd.Tbase(개화~수확)와 전혀 다름 — 별도 지표. DB 스키마에 없음, 팀 결정 필요 |
| 배 | temp_day(생육기온) | 전기간 | O(S1~N1 4단계) | O | - | filled | papers/pear/gis-soil-climate-suitability-2019.md |
| 배 | 연평균기온 | 전기간 | O(S1~N1 4단계) | O | - | filled | papers/pear/gis-soil-climate-suitability-2019.md |
| 배 | ph | 전기간 | 5.8~7.0 | - | - | filled | Yara Korea + 충청북도 농업기술원 (Iteration 2-1) |
| 배 | ec | 전기간 | 0.6 dS/m(전북 실측, N=110 중 배) / ≤2.0(RDA 과수원 통합 상한) | - | - | **partial(2026-08-04 최초 전환)** | papers/apple/apple-topography-soil-jeonbuk-ahn-2011.md(Table 5, 전북 110개소 과종별 비교 — 배 실측 0.6dS/m, 1:5법)+papers/apple/apple-soil-optimum-range-landuse-kang-2014.md(RDA-NAAS, 과수원 통합 상한 2.0). **한계**: 두 논문 모두 "사과" 폴더 파일에 부수적으로 포함된 배 데이터이며, 배 전용 연구가 아님. 지역단위(전북)·소표본이라 national-scale 아님. **신규 후보(원문 미확보)**: Lee & Lee(2011, 경남 25개소, 인용10) — EC 수치 미확인, 원문 필요. Lee et al.(2016, Acta Hortic. 1146:41-48, 배 단독) — 원문 접근 차단(Anubis 봇방어), 재시도 필요 |
| 배 | organic | 전기간 | 35 g/kg(전북 실측) / 25~35(RDA 과수원 통합 기준) | - | - | **partial(2026-08-04 최초 전환)** | papers/apple/apple-topography-soil-jeonbuk-ahn-2011.md(Table 5, 배 실측 35g/kg — 5과종 중 최고)+papers/apple/apple-soil-optimum-range-landuse-kang-2014.md(과수원 통합 25~35, 배 실측치와 정확히 겹침 — 상호검증됨). **한계**: 상동(배 전용 연구 아님, 지역단위). 윤성탁 외(2010, 배 전용, papers/pear/yoon-organic-amendment-soil-2010.md 이미 KB 존재)는 KCI paywall로 정량수치 미확보 — 원문 재확보 시 최우선 |
| 배 | p2o5 | 전기간 | 859 mg/kg(전북 실측, Lancaster법) | - | - | **partial(2026-08-04 최초 전환)** | papers/apple/apple-topography-soil-jeonbuk-ahn-2011.md(Table 5, 배 실측 859mg/kg — RDA 적정 200~300의 2.9~4.3배 과잉) + papers/apple/apple-soil-optimum-range-landuse-kang-2014.md(과수원 통합 300~550mg/kg, 동일 Lancaster법 계열). ⚠️Lancaster법이라 사과의 Bray-1 기준과 동일한 단위체계 혼재 문제 재현. **신규 후보(원문 미확보)**: Park, Lim & Lee(2012, 배 전용, Korean J. Soil Sci. Fert. 45(2)) — 측정법 미확인, 원문 확보 최우선 |
| 배 | gdd(적산온도) | 전기간 | 85°C 확정 | - | - | filled | Iteration 2-2 (베이스온도 10°C) |
| 배 | temp_max(일소_FST) | 전기간 | 회피 47.1°C↑ | - | - | **filled** | Iteration 3-b (McClymont 2016) ⚠️ FST ≠ 대기온 |
| 배 | rainfall_optimal | 전기간 | 270mm/시즌 | - | - | **partial** | Iteration 3-c (Ye et al. 2019) ⚠️ 중국 황토고원, 한국 재검증 필요 |
| 오이 | temp_max(고온피해) | 전기간 | 회피 30°C↑ | - | - | filled | Iteration 2-2 (기온 영향) |
| 오이 | rainfall_optimal_greenhouse | 전기간 | 봄 225-240mm, 가을 105-120mm | - | - | **partial** | Iteration 3-c (Wang et al. 2025) ⚠️ 온실 환경만, 노지 기준 미정 |
| 오이 | temp_day(대기온) | 전기간 | - | - | - | **missing(구조확인)** | Iteration 4 — 기존 시드 20~22℃가 실은 "근권 지온" 값이 잘못 들어간 것이라는 의심이 Wang et al.(2018)+이주영 외(2011) 두 독립 문헌으로 확정됨. 대기 낮기온 자체의 적정범위는 여전히 미확보 |
| 오이 | temp_soil(근권온도, **신규 지표 후보**) | 전기간 | 18~22℃(이주영 2011: 18~20 / 김태욱·김진현 2001 재인용: 20~22, 두 문헌 수렴) | 하한 13℃(인산흡수 저해, P09) | - | **filled** | papers/cucumber/cucumber-leaf-mineral-soil-chemistry-lee-2011.md, papers/cucumber/cucumber-air-rootzone-temperature-wang-2018.md(구조검증). DB 스키마에 `temp_soil` 컬럼 없음 — 팀 결정 필요 |
| 오이 | rainfall_optimal_field(노지, **신규 지표 후보**) | 전기간 | 노지 관수 6mm/day(수량최적)~8mm/day(최대), 온실:노지 물요구량비 ≈1:3 | - | - | partial | papers/cucumber/cucumber-field-irrigation-water-use-abdelrahman-2004.md ⚠️ 오만 건조기후 실험, 한국 몬순기후 미검증. 순수 관수량이라 자연강우 의존형 rainfall 지표와 개념이 다름 |
| 오이 | (화학성) ph/ec/organic/p2o5 | 전기간 | 실측 pH 6.2~6.8, EC 3.2~3.5 dS/m(1:5), 유효인산 759~1,016 mg/kg | - | - | partial | papers/cucumber/cucumber-leaf-mineral-soil-chemistry-lee-2011.md ⚠️ "우수농가 실태치"이지 "권장 처방"이 아님 — optimal_range로 바로 못 씀, 참고치로만 |
| 감자 | temp_max(고온피해_괴경형성) | 전기간 | 야간 ≥28°C 중단 | - | - | **filled** | Iteration 3-a (Zhang et al. 2024) |
| 감자 | temp_max(고온피해_광합성) | 전기간 | >22°C 부작용, 30°C↓45% | - | - | **filled** | Iteration 3-a (Lal et al. 2022) |
| 감자 | temp_min(냉해_잎) | 전기간 | -3°C | - | - | **filled** | Iteration 3-a (Stegner et al. 2019) |
| 감자 | temp_min(빙핵_형성) | 전기간 | -2.3±0.4°C | - | - | **filled** | Iteration 3-a (Stegner et al. 2019) |
| 감자 | (화학성+강수) | 전기간 | 강수 ETc상대값 | - | - | missing | Iteration 3-c (Mora 2025 partial). Iteration 4에서도 화학성·강수는 다룬 논문 없음 — 여전히 missing |
| 감자 | temp_day(tuber, allowed_max) | tuber | 괴경형성 최적 22~24℃(기존 optimal 23~24와 거의 일치) | **27℃**(기존 시드값과 동일 — 이번에 실측으로 강하게 재확인) | - | filled | papers/potato/potato-tuber-initiation-temperature-kim-2016.md — 승온실험 AT+5.0℃(평균 27.1℃)에서 수량 0.0 t/ha(전멸) 실측, allowed_max=27의 가장 강력한 근거 확보 |
| 감자 | temp_min_frost_damage_tuber(**신규 지표 후보**, 괴경 냉해 가드레일) | 전기간(월동·방치 괴경 한정) | - | -1.5~-1.9℃ 이하(일부 고사), -2.8℃ 이하(광범위 고사) | - | filled | papers/potato/potato-tuber-freezing-boydston-2006.md (인용34, 6년 포장실측+실험실 정밀통제) ⚠️ "생육기 정상재배 온도하한"이 아니라 "월동중 방치괴경의 동결치사 임계값" — 지상부 냉해(-3℃, Stegner 2019)보다 지하부가 더 예민함이 확인됨. 기존 `temp_day.allowed_min`과 다른 별도 지표로 분리 필요 |
| 감자 | tuber_initiation_optimal_temp(**신규 지표 후보**) | tuber_initiation | 22~24℃ | - | - | partial | papers/potato/potato-tuber-initiation-temperature-kim-2016.md ⚠️ 기존 tuber 단계 optimal(23~24)과 사실상 중복 — "괴경형성기"와 "괴경비대기"를 하나의 growth_stage로 뭉뚱그릴지 분리할지 팀 결정 필요 |
| 감자 | diurnal_temp_range(**신규 지표 후보**, 일교차) | 전기간 | 평균기온 17~22℃대에서는 일교차 클수록 수량 유리 | 평균22℃+ 일교차17℃초과는 불리(일최고 30℃초과 열스트레스) | - | partial | papers/potato/potato-tuber-initiation-temperature-kim-2016.md — DB 스키마에 없는 개념(주야 "차이"), 반영 여부 팀 결정 필요 |
| 감자 | soil_frost_depth_snow_compaction(**신규 지표 후보**, 자란모 방제용) | 월동기 | - | 토양동결심도 0.3m 초과 시 자란모(volunteer) 괴경 고사 | - | filled | papers/potato/potato-frost-snow-compaction-shimoda-2018.md (인용13~14) ⚠️ crop_growth_guide(재배 최적조건)가 아니라 병해충/잡초 방제 목적 지표 — 적설지역 한정, 별도 테이블/용도로 관리 검토 |
| 감자 | soil_frost_tuber_killing(**신규 지표 후보**) | 월동기 | - | 토양서리 심도 기반 고사(정확한 수치는 원문 재확인 필요) | - | partial | papers/potato/potato-frost-soil-yazaki-2013.md (인용21) ⚠️ 추출 시 핵심 수치가 명시적으로 안 잡힘 — 원문 재확인 필요 |
| 상추 | temp_max(고온피해) | 전기간 | 회피 30°C↑ | - | - | filled | Iteration 2-2 (기온 영향) |
| 상추 | temp_day(적온) | 전기간 | 18~18.5℃(Lafta 2017·Wallace 2012 재인용 수렴, 기존 시드 15-20과 부합) | allowed_max 30(노지 실측 뒷받침, 27℃↑부터 추대·팁번 급증) | - | filled | papers/lettuce/lettuce-heat-tolerance-field-lafta-2017.md, papers/lettuce/lettuce-tunnel-openfield-yield-wallace-2012.md ⚠️ 적온 수치 자체는 두 논문 모두 재인용(원출처 Dufault 2006 계열 동일 가능성 있어 완전 독립검증은 아님), allowed_max는 노지 실측 |
| 상추 | ec(신규) | 전기간 | 수량최고 3.50 dS/m(무비, 강보구 1996 실측) / 입모율 50%확보 ≤6 dS/m / RDA공식 ≤2.0 | - | - | filled | papers/lettuce/lettuce-soil-ec-salinity-kang-1996.md ⚠️ 문헌 간 최적점 편차 큼(0.85~3.50, 품종·토양·시비조건 차이로 추정 — 단위환산 문제 아님, Lee 2003으로 확인됨) |
| 상추 | ph/organic/p2o5 | 전기간 | pH 6.5~6.9(협소구간, 소석회처리 6.9 최고수량) / 유기물 13.7~19.7 g/kg / 유효인산 358~586 mg/kg | - | - | partial | papers/lettuce/lettuce-soil-ph-organic-compost-yoon-2025.md ⚠️ 상추 전용 실측이나 시험구간이 좁아 상·하한(실패 임계값) 미확인 |
| 사과 | rainfall_by_stage | 전기간 | 개화-결실 120mm, 과실팽창 319mm, 성숙 113mm | - | - | **partial** | Iteration 3-c (Ru et al. 2025) ⚠️ 중국 모델(R²=0.63), 지역 편차 큼. **2026-08-03 한국 재검증 확대**: papers/apple/apple-yield-weather-factors-kim-2014.md(전국 15주산지 8개년 패널, 원문 전체 확보) — 10월 누적강수+1mm→단수-4.05kg/10a(1%), 4월누적강수+1mm→-4.21kg/10a(1%) 등 8개 계수 확보. **한계**: registry의 "총량 mm 최적구간" 형태가 아니라 "월별 1mm당 한계효과" 계수라 직접 대입 불가 — 방향성(다량강수=악영향) 검증 근거로만 사용. Do et al.(2024, Agriculture MDPI, 홍로·군위, N=5·단일연도)는 mm 단위 관수 스펙 자체가 없어 "고온기 미스트관수→열과·착색 개선" 정성적 근거로만 caution 병기. **2026-08-03 방법론 보강(해외)**: papers/apple/apple-evapotranspiration-crop-coefficient-zanotelli-2019.md(이탈리아, 3년 에디covariance 직접측정, 인용54) — 생육단계별 실측 Kc(초기 0.657/성숙 1.013/후기 0.835)가 FAO 표준표보다 15~30% 낮음. **Kc계수 형태라 Ru(2025)의 mm총량과 단위체계 자체가 달라 직접 대체 불가**, "FAO표준을 그대로 쓰면 과다산정"이라는 방법론적 경고만 참고. **2026-08-03 유효강수 개념 추가(해외)**: papers/apple/apple-rainfall-efficiency-treder-2022.md(폴란드, 4개년) — "총 강수 mm ≠ 유효 흡수 mm"(강수>ETo인 날만 유효, 전체 강수일의 36~54%뿐이나 총 강수량의 84.5~95% 차지) — 기존 mm 총량 지표가 실제 흡수량을 과대추정할 수 있다는 방법론적 경고. papers/apple/apple-cwsi-irrigation-treatment-kim-2019.md(국내 RDA, 시나노스위트, 관개 50%/75%ET 처리)는 **자연강수가 아닌 인공관개 스킴**이라 rainfall_by_stage 갭을 채우지 못함(reference_only, 향후 관개스케줄링 기능 참고용) |

## 2. soil_change_rule 커버리지

| action_type | indicator | effect_coeff | decay_days | status | note | source(s) |
|---|---|---|---|---|---|---|
| (온도 환경, action 아님) | organic | 정성적 근거만(온도↑ → 무기화율↑) | 정성적 근거만 | partial | 근권온도-기온 환산모델 없어 계수화 보류 | papers/apple/root-zone-temperature-2001.md |
| FERTILIZE_N | organic/EC(?) | 관비 최적농도(200mg/L, 실생묘) 확인됨 | - | partial | 단위가 영양액 mg/L라 밭 kg/10a 환산 필요. indicator 자체도 매핑 미정 | papers/pear/nitrogen-level-seedling-2006.md |
| IRRIGATION(강수과다) | rainfall_excess | 토양산소부족→뿌리부패 | 일 강수 30-50mm 이상 시 작물생육 저해(3-5cm 적층, 3일↑ 산소결핍) | **filled** | Iteration 3-c (Zhang et al. 2025 Review) | Iteration 3-c |
| DROUGHT(가뭄) | awr | AWR<100(제한급수), <50(심각); -0.2~-0.3MPa | - | partial | Iteration 2-2 | Iteration 2-2 |
| LIMING | ph | 석회시용량 → pH 변화 | 계절별 | filled | pH 범위 유지/회복. RDA 기준 적용 | RDA 비료사용처방 |
| FERTILIZE_P | p2o5 | P2O5 시용량(kg/10a) → 토양 p2o5(mg/kg) | 계절별 | filled | Bray-1 기준 적용. 현장 극단적 과잉(22.5 kg/10a) 원인 조사 필요 | RDA 비료사용처방, 실태조사 805농가 |

## 3. 논문 인덱스

| 제목 | 작물 | 파일 경로 | 한 줄 요약 |
|---|---|---|---|
| 신고배 재배지 내 수체 및 토양의 탄소 및 질소 저장량 | 배 | papers/pear/carbon-nitrogen-stock-2013.md | 15년생 성목 탄소·질소 정적 저장량 스냅샷. 행위-반응 데이터 아님 |
| 질소 시용수준에 따른 배 신고 실생묘의 생육과 질소관련물질의 변화 | 배 | papers/pear/nitrogen-level-seedling-2006.md | 실생묘 대상 질소농도 4수준 실험. 200mg/L 최적 |
| 과원의 근권 온도가 토양 공기 및 화학성과 사과나무 생육에 미치는 영향 | 사과 | papers/apple/root-zone-temperature-2001.md | 근권온도×경과일 → 유기물·질소 변화 정량 데이터 |
| 지목과 토양적성도를 활용한 사과 재배적지 선정에 관한 연구 | 사과 | papers/apple/land-category-suitability-2023.md | 사과 온도 계열 적정구간(4단계) 제공, MLCM/AHP 방법론 논의 |
| GIS 기반의 토양 및 기후조건 통합 배 과수의 적지 평가 | 배 | papers/pear/gis-soil-climate-suitability-2019.md | 배 온도 계열 적정구간(4단계) 제공, MLCM vs AHP 전국 비교·검증 |
| 배 생육 기간 중 온도 환경이 세포벽 구성 물질 변화에 미치는 영향 | 배 | papers/pear/temperature-cell-wall-2022.md | 적산온도(GDD)-생육속도-과실 품질 관계. 생육단계 파생 로직에 참고 |
| 홍로 품종 과실품질과 토양 pH의 관계 | 사과 | papers/apple/fruit-quality-hongro-품종.md | 사과 최적 pH 6.0~6.5 확인. 초생재배 시 pH 6.2~6.4 안정성 |
| RDA 비료사용처방 (표준영농교본) | 사과/배 | papers/rda/비료사용처방-표준.md | 사과·배 pH 6.0~6.5, P2O5 30~50(Bray-1), 석회시용 표준 |
| 실태조사: 전국 805농가 토양 화학성 분석 | 사과 | papers/survey/national-soil-status-805farms.md | 실제 시비 22.5 kg/10a (이론의 125%), 토양 P 극단적 축적 문제 노출 |
| 유기재배 매뉴얼: 작물별 토양 화학성 기준 | 전작물 | papers/organic/organic-soil-criteria-manual.md | 유기 인산 40~60 mg/kg, 일반과 상이 |
| 협회 가이드: 현장 시비량 보정 (P2O5 10~12 kg/10a + 20%) | 사과 | papers/association/practical-fertilizer-guide.md | 이론 vs 현장 갭 분석. 토양검정+현장보정 권장 |
| 초생재배 토양산도 안정화 | 사과 | papers/apple/cover-crop-soil-acidity-stability.md | 초생재배 시 pH 6.2~6.4 안정. 토양미생물 다양성 증가 |
| Distinct Impacts of Air and Root-Zone Temperatures on Cucumber Seedlings | 오이 | papers/cucumber/cucumber-air-rootzone-temperature-wang-2018.md | Tair·Troot가 서로 다른 생리경로(탄소동화 vs 질소흡수)로 작용 — temp_day/temp_soil 분리 필요성을 실험적으로 확정. reference_only(구조 증명용, 수치 없음) |
| Water Use Efficiency and Yield of Cucumber Under Greenhouse and Field Conditions | 오이 | papers/cucumber/cucumber-field-irrigation-water-use-abdelrahman-2004.md | 노지 관수량-수량 회귀식(R²=0.92), 온실:노지 물요구량 ≈1:3. 오만 건조기후 한정 |
| 시설재배 오이의 생육시기별 엽 중 다량/미량요소 함량 (이주영 외, 2011) | 오이 | papers/cucumber/cucumber-leaf-mineral-soil-chemistry-lee-2011.md | 적정 토양온도 18~20℃(P09와 수렴), 우수농가 실측 화학성(pH·EC·유효인산) |
| Estimation of Conversion Factors for EC (Saturation-Paste vs 1:5 Water Extraction) (Lee 외, 2003) | 상추(방법론) | papers/lettuce/lettuce-ec-conversion-factor-lee-2003.md | 간척지 90점 기준 EC 환산계수. reference_only — 상추 EC 실측치에 기계적 적용 금지(저자 스스로 명시) |
| Field Evaluation of Lettuce Genotypes for Heat Tolerance (Lafta 외, 2017) | 상추 | papers/lettuce/lettuce-heat-tolerance-field-lafta-2017.md | 노지 실측, 적온 18℃ 재인용 + allowed_max 30 뒷받침, 36품종 내열성 비교 |
| 염류집적이 상추의 발아 및 생육에 미치는 영향 (강보구 외, 1996) | 상추 | papers/lettuce/lettuce-soil-ec-salinity-kang-1996.md | 토양 EC 실측(입모율 회귀식, 수량최고 EC 3.50 무비조건) |
| 인산석고 유래 소석회처리 퇴비의 상추 생육 및 토양 특성 (윤진주 외, 2025) | 상추 | papers/lettuce/lettuce-soil-ph-organic-compost-yoon-2025.md | pH·유기물·유효인산 실측(협소구간), 소석회처리 최고수량 |
| Lettuce Yield and Quality in High Tunnel and Open-Field Production (Wallace 외, 2012) | 상추 | papers/lettuce/lettuce-tunnel-openfield-yield-wallace-2012.md | 3개 기후대 노지/터널 비교, 적온 18.5℃ 재인용(Lafta 2017과 동일계보 가능성) |
| Snow Compaction (Yuki-fumi) for Frost-Killing Potato (Shimoda & Hirota, 2018) | 감자 | papers/potato/potato-frost-snow-compaction-shimoda-2018.md | 토양동결심도 0.3m 초과 시 자란모 괴경 고사 — 방제 목적 지표 |
| Effective Killing of Volunteer Potato Tubers by Soil Frost (Yazaki 외, 2013) | 감자 | papers/potato/potato-frost-soil-yazaki-2013.md | 토양서리 기반 괴경 고사 — 핵심 수치 원문 재확인 필요(partial) |
| 기온상승에 따른 감자 생육 및 수량 변화 분석 (이인하 외, 2024) | 감자 | papers/potato/potato-heat-stress-thermal-gradient-lee-2024.md | 품종별(수미/조풍) 고온 민감도 차이(ΔT 상대값). reference_only — 절대온도 환산 불가 |
| Freezing Behavior of Potato Tubers in Soil (Boydston 외, 2006) | 감자 | papers/potato/potato-tuber-freezing-boydston-2006.md | 괴경 동결치사 임계값(-1.5~-2.8℃), 6년 포장실측+실험실. 지상부보다 지하부가 더 냉해에 예민함을 확정 |
| Effect of High Temperature, Daylength, Reduced Solar Radiation on Potato (Kim & Lee, 2016) | 감자 | papers/potato/potato-tuber-initiation-temperature-kim-2016.md | 괴경형성 최적 22~24℃, allowed_max=27 강력 재확인(27.1℃서 수량 0), 일교차(DTR) 신규지표 후보 |
| Apple Fruit Growth and Maturity are Affected by Early Season Temperatures (Warrington 외, 1999) | 사과 | papers/apple/apple-fruit-growth-maturity-temperature-warrington-1999.md | 과실확장속도-온도 선형관계(0.062~0.075mm/day per℃), fruit_growth/maturity 온도 최초 실증. 해외(뉴질랜드), bounded range 아님 |
| 사과생산량에 영향을 미치는 기상요인 분석 (김미리·김승규, 2014) | 사과 | papers/apple/apple-yield-weather-factors-kim-2014.md | 전국 15주산지 8개년 패널, 강수·기온 월별 계수 8개(10월 강수+1mm→단수-4.05kg/10a 등) |
| FDR 센서를 이용한 사과원 토양 실시간 EC 측정을 위한 Hilhorst 모델의 보정 (이재범·김종윤, 2023) | 사과(방법론) | papers/apple/apple-ec-fdr-hilhorst-calibration-lee-2023.md | FDR↔1:5물추출법 EC 환산(RMSE 0.20). reference_only — optimal_range 값 출처 아님 |
| 기온자료에 근거한 사과 '후지' 품종의 발아기 및 개화기 예측 (김수옥·윤진일, 2010) | 사과 | papers/apple/apple-fuji-phenology-prediction-kim-yun-2010.md | Chill Day 모형(기준온도 6.1℃/냉각요구 -100.5), 만개예측 anti-chill day 275.1. GDD 아닌 chilling_requirement 2번째 근거 |
| Phosphorus Legacy: Overcoming the Effects of Past Management Practices to Mitigate Future Water Quality Impairment (Sharpley 외, 2013) | 사과(구조참고) | papers/apple/apple-p2o5-legacy-overapplication-sharpley-2013.md | "legacy P" 개념 — 토양P 누적은 작물흡수보다 빨라 시비중단 후 7~27년간 유의한 감소 없음(인용1040). p2o5_실태 극단적 과잉의 구조적 설명 |
| Changes in the Taste and Textural Attributes of Apples in Response to Climate Change (Sugiura 외, 2013) | 사과 | papers/apple/apple-taste-texture-climate-change-sugiura-2013.md | 일본 40년 포장실측(인용143) — 만개일 1.0~2.3일/decade 앞당겨짐, 성숙기고온↑→산·경도·수침↓. Warrington(1999) 독립 재확인 |
| Comparative Effects of Organic and Conventional Apple Orchard Management on Soil Chemical Properties (Gasparatos 외, 2011) | 사과 | papers/apple/apple-ec-organic-conventional-gasparatos-2011.md | 그리스, EC 관행1.22 vs 유기0.91 dS/m(1:1법, P<0.01). 측정법 상이해 한국표준(1:5) 직접대입 불가 |
| Evapotranspiration and Crop Coefficient Patterns of an Apple Orchard in a Sub-Humid Environment (Zanotelli 외, 2019) | 사과 | papers/apple/apple-evapotranspiration-crop-coefficient-zanotelli-2019.md | 이탈리아 3년 에디covariance 실측(인용54) — 생육단계별 Kc(초기0.657/성숙1.013/후기0.835), FAO표준보다 15~30%낮음 |
| Night Temperatures Affect Fruit Coloration and Expressions of Anthocyanin Biosynthetic Genes in 'Hongro' Apple Fruit Skins (Ryu 외, 2017) | 사과 | papers/apple/apple-coloring-night-temperature-hongro-ryu-2017.md | **국내(RDA 완주) 실측** — 착색기 야간온도 LNT 20.1~23.4℃(촉진) vs HNT 26.1~29.4℃(억제). 착색기 temp_night_min 최초 filled |
| Orchard Groundcover Management Impacts on Apple Tree Growth and Yield, and Nutrient Availability and Uptake (Merwin & Stiles, 1994) | 사과 | papers/apple/apple-organic-groundcover-management-merwin-1994.md | 미국 코넬대 6년 실험(인용138) — 짚멀칭이 유기물·K·P·수량 최우수. organic 전용연구 최초 확보(관리방식 메커니즘) |
| Analysis of Growth and Physicochemical Changes of the Apple cv. Anna in a High Altitude Tropical Climate (Cepeda 외, 2021) | 사과 | papers/apple/apple-gdd-growth-anna-cepeda-2021.md | 콜롬비아, Tbase=7.22℃(Chaves 2017 재인용) 적용 로지스틱생장모델 R²>0.99. gdd.Tbase 독립근거 아님(재인용치) |
| Setting up The Optimum Ranges of Soil Chemical Properties According to Agricultural Land Use (Kang 외, 2014) | 사과(과수원 통합) | papers/apple/apple-soil-optimum-range-landuse-kang-2014.md | RDA-NAAS 국가기준 — EC≤2.0(기존 allowed_max 출처 확인), 과수원 유효인산 300~550mg/kg(Lancaster법, Bray-1과 단위체계 상이) |
| Assessment of Rainfall Efficiency in an Apple Orchard (Treder 외, 2022) | 사과 | papers/apple/apple-rainfall-efficiency-treder-2022.md | 폴란드 4개년 — "유효강수(강수>ETo)" 개념, 총강수 mm≠실제흡수량 경고. rainfall_by_stage mm구간은 미해결 |
| Response of Crop Water Stress Index (CWSI) and Canopy Temperature of Apple Tree to Irrigation Treatment Schemes (Kim 외, 2019) | 사과(방법론) | papers/apple/apple-cwsi-irrigation-treatment-kim-2019.md | 국내 RDA, 시나노스위트 — 관개 50%/75%ET시 CWSI 0.79→0.64. 인공관개 스킴이라 rainfall_by_stage(자연강수) 아님, reference_only |
| Modeling Fruit Growth of Apple (Chaves 외, 2017) | 사과 | papers/apple/apple-gdd-fruit-diameter-chaves-2017.md | 워싱턴주 11지점×4개년 실측 — Tbase=7.22/5.55/6.11℃(품종별) **재인용 아닌 직접도출** 확인. gdd.Tbase missing→partial 격상 |
| Temperature Changes Affected Spring Phenology and Fruit Quality of Apples Grown in High-Latitude Region of South Korea (Lee 외, 2023) | 사과 | papers/apple/apple-temperature-phenology-fruit-quality-lee-2023.md | 국내(춘천) 20년 실측, 후지·홍로 — 온도↑→생육가속(홍로>후지), temp_day(fruit_growth/maturity) 3번째 독립근거. 품종별 반응차 신규 확인 |
| Expression of Genes Affecting Skin Coloration and Sugar Accumulation in 'Hongro' Apple Fruits at Ripening Stages in High Temperatures (Kim 외, 2016) | 사과 | papers/apple/apple-coloring-sugar-gene-expression-hongro-kim-2016.md | 국내 홍로, 항온챔버 25/30/35℃ — 착색·당 유전자 발현이 30~35℃서 크게 억제. **temp_day(coloring) missing→partial 최초 전환** |
| Relative Contribution Rate on Soil Physico-chemical Properties Related to Fruit Quality of 'Hongro' Apple (Kim 외, 2012) | 사과 | papers/apple/apple-soil-contribution-hongro-kim-2012.md | 국내 홍로 60농가 — 유기물 기여율 0.1~5.6%로 낮음(organic 중요도 재평가), 유효인산-착색 55.9% 신규연결 발견 |
| Relationships between Soil Physico-chemical Properties and Topography in Jeonbuk Orchard Fields (Ahn 외, 2011) | **사과+배** | papers/apple/apple-topography-soil-jeonbuk-ahn-2011.md | 전북 110개소, 과종별(사과·배·복숭아·포도·감) 비교표(Table 5) 보유. 사과 EC 0.5(재검토 신호)/유효인산 631. **2026-08-04 배에도 반영**: 배 EC 0.6, 유기물 35(RDA기준과 겹침), 유효인산 859(적정 2.9~4.3배 과잉) — 배 ec/organic/p2o5 최초 partial 전환의 근거 |

## 4. 커버리지 통계 (Iteration 8 최종, 2026-08-03)

> **denominator 주의**: "13"은 Iteration 3까지 쓰던 고정 체크리스트(작물당 temp_day/temp_night_min/frost×2/temp_max/gdd/ph/ec/organic/p2o5류/rainfall)를 기준으로 한 근사치이며 실제 스키마 제약은 아니다. Iteration 4에서 이 체크리스트 **밖의 신규 지표 후보**(temp_soil, rainfall_optimal_field, diurnal_temp_range, tuber_initiation_optimal_temp, soil_frost_depth_snow_compaction, soil_frost_tuber_killing, temp_min_frost_damage_tuber — 총 7개)가 발견됐고, Iteration 5~6에서 사과 2개(chilling_requirement, forcing_requirement_bloom)가 추가돼 총 9개다. 이들은 기존 13항목 분모에는 넣지 않고 별도로 표기한다(넣으면 "채워짐 비율"이 인위적으로 부풀려짐). reference_only 논문(구조 검증·측정법 검증용, 수치 자체는 못 씀)도 분모에서 제외 — 총 4편(변동 없음). **사과는 Iteration 6에서 temp_day를 fruit_growth/maturity와 coloring 2행으로 분리해 13→14항목으로 늘었고, Iteration 7에서 coloring 항목이 temp_day(coloring)와 temp_night_min(coloring) 2개로 다시 나뉘어 14→15항목으로 늘었다** — 아래 표에서 사과만 "X/15"로 표기.

### crop_growth_guide (기존 13항목 체크리스트 기준, 사과는 15)
- 작물별 filled+partial 합산 변화는 아래 "작물별 커버리지" 표 참고(정확한 산정은 크롭별로만 의미 있음 — 5작물을 하나의 분모로 합산하면 왜곡됨)
- 신규 지표 후보(체크리스트 밖): 9개(오이2·감자5·사과2, 변동 없음) — 스키마 반영 여부 팀 결정 대기
- reference_only(수치 사용 불가, 구조/방법론 검증용): 4편(변동 없음) — Wang et al.(2018, 오이), Lee et al.(2003, 상추 EC), 이인하 외(2024, 감자 ΔT), 이재범·김종윤(2023, 사과 EC측정법)

### soil_change_rule
- 변동 없음: filled 6/6 (100%) — Iteration 5~7에서 soil_change_rule 관련 신규 논문 없음

### 작물별 커버리지 (filled + partial)
| 작물 | Iteration 8 | Iteration 9 | 상태 |
|---|---|---|---|
| 사과 | 15/15 (100%) | 15/15 (100%) | 변동 없음(이번 라운드는 배만 다룸) |
| 배 | 6/13 (46%) | **9/13 (69%)** | ec·organic·p2o5 3개가 missing→**partial로 최초 전환**(2026-08-04) — 이미 확보돼 있던 apple-topography-soil-jeonbuk-ahn-2011.md(전북 110개소, 과종별 비교표)에 배 데이터가 부수적으로 포함돼 있었음을 재발견, 신규 다운로드 없이 즉시 반영. Kang(2014) 과수원 통합기준(organic 25~35, 배 실측 35와 정확히 겹침)과 상호검증됨. **한계**: 배 전용 연구가 아니라 지역단위(전북) 소표본 부수데이터 — national-scale·배 전용 검증은 여전히 미해결 |
| 감자 | 5/13 (38%) | 5/13 (38%) | 변동 없음 |
| 오이 | 3/13 (23%) | 3/13 (23%) | 변동 없음 |
| 상추 | 4/13 (31%) | 4/13 (31%) | 변동 없음 |

**신규 지표 후보 현황(체크리스트 밖, 별도 트랙)**: 오이 2개(temp_soil filled, rainfall_optimal_field partial) / 감자 5개(temp_min_frost_damage_tuber filled, tuber_initiation_optimal_temp partial, diurnal_temp_range partial, soil_frost_depth_snow_compaction filled, soil_frost_tuber_killing partial) / 사과 2개(chilling_requirement filled·2개 독립근거, forcing_requirement_bloom partial) — DB.md `crop_growth_guide.indicator` 목록에 추가할지, 어떤 걸 크롭할지는 §5 구조적 이슈 참고.

**사과 100%가 착시인 이유(Iteration 8에서 더 뚜렷해짐)**: filled+partial 15/15는 숫자상 완전해 보이지만, **8개 항목이 여전히 partial에 머물러 있다**(ec·organic·gdd·rainfall_by_stage·temp_day(fruit_growth/maturity)·p2o5_실태·temp_day(coloring)·forcing_requirement_bloom). 그중 다수가 "국내 national-scale 검증 부재"라는 근본 문제를 여전히 공유하며, 이번 라운드는 오히려 **기존 optimal 추정치에 대한 의문을 새로 제기**했다(사과 EC 전북 실측 0.5 dS/m가 기존 optimal 0.8~1.5보다 낮음; 유기물 중요도가 실측상 낮다는 반증적 신호). 즉 "100% 도달"은 "빈 항목이 없다"는 뜻일 뿐 "모든 수치가 확정됐다"는 뜻이 아니다 — 오히려 Iteration 9에서는 **기존 partial 수치들의 재검토**가 새로운 논문 탐색보다 더 중요해질 수 있다.

---

## 5. 알려진 구조적 이슈 (팀 결정 필요)

### Iteration 8 신규 이슈

- **사과 EC 기존 optimal(0.8~1.5) 재검토 신호**: papers/apple/apple-topography-soil-jeonbuk-ahn-2011.md(전북 110개소 중 사과)의 실측 EC 평균이 0.5 dS/m로, registry 기존 optimal 하한(0.8)보다도 낮게 나왔다. 기존 optimal은 hongro(N=60, 충주·문경 등 6개 주산지)·sod(N=4처리) 소규모 조사 기반인데, 전북(다른 지역) 실측은 이보다 낮은 값을 보인다 — **지역별 토양 특성 차이인지, 기존 optimal 추정 자체가 편향(6개 주산지에 국한)됐는지 팀이 재검토 필요**. EC뿐 아니라 organic도 비슷한 패턴(중요도 자체가 실측상 낮다는 반증)이 나와, Iteration 9에서는 "새 논문 찾기"보다 "기존 partial 수치 재검토"가 우선순위가 될 수 있음.
- **유효인산 측정법(Bray-1 vs Lancaster) 혼재가 명확히 확인됨**: 같은 배치의 3편(Kang 2014 RDA국가기준, Kim 2012 홍로 60농가, Ahn 2011 전북 110개소)이 모두 유효인산을 200~900 mg/kg 대의 수치로 보고하는데, registry의 기존 p2o5(Bray-1, 30~50mg/kg)와는 10배 이상 차이난다. 이는 단위 오류가 아니라 **RDA 내에서도 과수원 토양에 Bray-1과 Lancaster 두 추출법이 병존**하기 때문으로 추정된다 — registry에 두 체계를 명시적으로 구분 표기하고, 향후 어느 논문이 어느 추출법을 썼는지 반드시 확인하는 절차를 검색 워크플로우에 추가해야 함.
- **유기물(organic)의 실제 중요도에 대한 2번째 반증 신호**: Merwin & Stiles(1994, 미국)의 회귀왜곡 경고에 이어, papers/apple/apple-soil-contribution-hongro-kim-2012.md(국내 홍로 60농가)가 유기물의 과중/당도/착색/종합품질 기여율이 0.1~5.6%로 지속적으로 낮다는 것을 확인했다 — **두 개의 독립된 논문이 각기 다른 방식(회귀왜곡 경고 vs 상대기여율 분해)으로 "유기물이 생각보다 핵심적이지 않을 수 있다"는 같은 방향의 신호를 보낸다.** organic 지표의 registry 내 비중(현재 다른 화학성 지표와 동등하게 다뤄짐)을 재검토할 근거가 쌓이고 있음.
- **유효인산-착색 55.9% 신규 연결고리**: Kim et al.(2012)에서 유효인산이 착색(coloring)에 유독 강하게 기여(55.9%, 다른 품질지표에서는 6.5% 이하)한다는 결과가 발견됨 — registry에 없던 완전히 새로운 지표 간 연결(p2o5 ↔ 착색). 인산 과잉(p2o5_실태에서 이미 확인된 문제)이 착색에 긍정적으로 작용하는지, 혹은 어느 수준을 넘으면 부작용이 있는지는 미확인 — Iteration 9 탐색 후보.
- **gdd.Tbase 재인용 함정이 최종적으로 해결됨**: Chaves et al.(2017) 원문을 직접 확보해 Tbase=7.22/5.55/6.11℃(품종별)가 재인용이 아니라 워싱턴주 11지점×4개년 실측에서 직접 도출된 값임을 확인했다. 다만 미국 품종(Cripps Pink/Gala/Red Delicious) 한정이라 한국 주력품종(후지·홍로) 값은 아니므로 filled 전환은 아직 시기상조 — Von Bertalanffy 커브핏 방법론을 후지·홍로 국내 실측 데이터에 적용하는 후속 연구가 다음 단계.
- **착색기 낮기온(temp_day-coloring)에 대한 간접 근사 채택 — 검증 필요**: Kim et al.(2016)의 항온챔버(25/30/35℃, 적출과실) 결과를 "낮기온" 지표에 partial로 반영했으나, 이는 **포장의 실제 대기 낮기온이 아니라 과실 자체의 온도**를 통제한 실험이다. Ryu(2017, 야간온도)와의 임계점(≈25℃) 수렴이 우연인지 실제 생리적 연관인지는 불명확 — DB에 반영하기 전 "포장 실측으로 재확인 필요"라는 라벨을 명확히 유지해야 함.

### Iteration 7 신규 이슈

- **착색기 온도의 진짜 신호는 "낮"이 아니라 "밤"일 가능성이 실측으로 뒷받침됨**: Ryu et al.(2017, RDA 완주, 국내 실측)이 야간온도(LNT 20~23℃ 촉진 / HNT 26~29℃ 억제)가 안토시아닌 생합성 유전자 발현을 최대 3배까지 좌우한다는 것을 직접 확인. 기존 temp_day(coloring) missing 상태의 F-2 가설("착색기 온도값이 실은 야간저온/일교차 문헌의 오매핑")과 정확히 부합. **단, 이 실험의 관측창(만개후 70~131일)이 기존 시드의 착색기 정의(day_of_year 233~293)와 정확히 겹치는지는 만개일 추정 로직과 연결해 팀이 확인해야 한다** — DB 반영 전 필수 검토사항.
- **유기물(organic) 지표의 "적정구간" vs "관리메커니즘" 성격 혼동 위험**: Merwin & Stiles(1994)의 다중회귀에서 유기물 회귀계수 부호가 음수로 나왔으나 저자 스스로 이를 인공적 결과(artifact, 경운·제초제 처리의 유기물 감소가 다른 이유의 수량저하와 우연히 겹친 것)라고 명시했다. 이 논문을 organic 지표에 반영할 때 절대 "유기물이 적을수록 좋다"로 옮기면 안 되며, "관리방식(멀칭 권장)"이라는 정성적 근거로만 사용해야 한다.
- **GDD Tbase의 반복적 재인용 함정**: Cepeda et al.(2021)이 사용한 Tbase=7.22℃는 독자 도출이 아니라 Chaves et al.(2017)의 재인용치다. 이런 식으로 "누군가 Tbase를 인용해서 쓰고 있다"는 사실이 "그 Tbase가 검증됐다"는 근거로 오인되기 쉽다 — registry에 Tbase를 반영하려면 **최초 도출 논문(Chaves 2017)을 직접 확보**해야 하며, 재인용 체인만으로는 filled/partial 전환이 안 된다는 원칙을 명시.

### Iteration 4 신규 이슈

- **오이 temp_day/temp_soil 분리가 이중으로 확정됨**: Wang et al.(2018, 정밀 요인설계 수경실험)과 이주영 외(2011, 국내 실측)가 독립적으로 "기존 시드의 20~22℃는 대기온이 아니라 근권/토양온도"라는 결론에 수렴. **`crop_growth_guide.indicator`에 `temp_soil`을 신설하고 기존 `temp_day` 값을 옮길지, 그대로 둘지 팀 결정 필요.** 대기 낮기온 자체의 적정범위는 여전히 미확보(별도 문헌 필요).
- **상추 EC 문헌 간 불일치는 측정단위 문제가 아님이 확인됨**: Lee et al.(2003)의 간척지 기반 EC1:5↔ECe 환산계수를 상추 EC 실측치(강보구 1996: 3.50 / 김기수 2011: 0.85)에 적용해보면 물리적으로 말이 안 되는 값이 나옴(저자 스스로도 "간척지 외 토양 적용 불확실" 명시). 즉 상추 EC 최적점이 문헌마다 0.85~3.50으로 벌어지는 건 단위 문제가 아니라 **품종·시비·토성 차이**로 봐야 함 — RDA 공식기준(≤2.0)과 개별 실측치를 구분 표기하는 방향으로 정리.
- **감자 괴경 냉해가 지상부보다 더 예민함이 확정됨**: Boydston et al.(2006, 인용34)이 지상부 냉해(-3℃, Stegner 2019)보다 낮은 -1.5~-1.9℃에서 괴경이 먼저 죽는다는 것을 6년 포장실측으로 확인. 다만 이 값은 "생육기 정상재배 온도하한"이 아니라 "월동중 방치괴경의 동결치사 임계값"이라 기존 `tuber.allowed_min`에 그대로 넣으면 안 되고 별도 지표(`temp_min_frost_damage_tuber`)로 분리 필요.
- **감자 tuber allowed_max=27은 이제 실측 근거 확보**: Kim & Lee(2016) 승온실험에서 평균기온 27.1℃일 때 수량이 0.0 t/ha(전멸)로 실측됨 — 기존 시드값(27)의 가장 강력한 근거.
- **일교차(DTR)라는 새 지표 개념 발견**: Kim & Lee(2016)가 "평균기온 자체"뿐 아니라 "일교차 크기"가 감자 수량에 유의하게 영향(17~22℃대에서는 클수록 유리, 22℃+17℃초과는 불리)을 확인. 현재 스키마엔 없는 개념(주야 온도차) — 반영 여부 및 방법(파생 계산 vs 별도 저장) 팀 결정 필요.
- **품종별 세분화 이슈 재부상**: 이인하 외(2024)가 감자 '수미'(민감)와 '조풍'(내열) 사이에 뚜렷한 온도 민감도 차이를 보고 — 현재 DB가 품종을 구분하지 않는 스키마(작물 단위 통합)와 충돌. 5종 작물 고정처럼 품종도 고정할지, 확장할지는 YAGNI 원칙 하에 팀이 결정할 사안(당장 반영 안 함, 이슈만 기록).

### Iteration 3 신규 이슈

- **배 고온 지표의 이원성**: 배 일소(sunscald)는 FST(과실표면온도) 47.1°C 임계이나, 이는 대기온이 아니라 태양복사+증발산 함수. 사용자가 측정 가능한 대기온 기준값 필요. 별도 지표 개선 또는 주석 명시 필요.

- **강수 mm 임계값의 지역·토양질감 민감도**: 현재 일 30-50mm는 일반 원리이나, 포식(clay), 식양(loam), 양토(sandy loam)의 포장용수량이 다르므로 같은 30mm가 의미하는 포화도가 상이. 한국 토양질감별 임계값 재산출 필요(특히 논→밭 전환 지역).

- **강수 기준의 지역·작물 편차**: 현재 배 270mm(황토고원 중국), 오이 225-240mm(온실 중국), 사과 단계별(중국 R²=0.63). 모두 중국/외국 기준이며, 한국 기후(여름 강수 집중)와 토양(산성 화산회토) 조건에서 동일하게 적용되는지 재검증 필요.

- **ETc 기준값 부재**: 감자 수분수요는 ETc 상대값(0.8~1.0ETc 범위)이나, 절대값(mm/일)으로 환산하려면 한국 지역별 ET0(기준 증발산량) 데이터 필요. 농과원/기상청 자료 확보 필요.

- **감자 냉해의 기관별 세분화**: 현재 -3°C(잎냉해), -2.3±0.4°C(빙핵)는 지상부 기준. 괴경·뿌리 냉해 임계값 미정. 냉저장 연구(seed potato) 자료와 포장 조사 구분 필요.

### 기존 이슈 (Iteration 2 이전)

- **사과 EC national-scale 검증 부재**: 현재 EC optimal range(0.8~1.5)는 소규모 조사(hongro N=60, sod N=4처리) + 매뉴얼 범위값에만 의존. RDA 전국 실측 통계(KISTI TRKO202100009605, 2013~2016) 원문 접근 불가(404). 흙토람 데이터베이스 또는 RDA 직접 문의로 national-scale 데이터 확보 필요.
- **사과 EC 측정법**: 1:5 물추출법(국제 표준 ECe와 단위 다름, 향후 환산계수 필요) — 국제 문헌(FAO, 외국 논문)과 비교 시 단위 변환 필수.
- **사과 P2O5 극단적 과잉**: 이론 8~10(RDA 추천) vs 실제 22.5 kg/10a(실태조사 평균). 전국 P축적 문제의 근원. 토양검정(Bray-1) 기준(30~50 mg/kg)과 현장 시비의 괴리 원인을 추적 필요. 협회 가이드의 +20% 현장보정(10~12 kg/10a)도 여전히 이론보다 높음 — 역사적 P 축적 vs 재배 관성 분석 필요.
- **질소 지표 매핑 미정**: `crop_growth_guide.indicator`/`soil_change_rule.indicator` 목록
  (`ph/ec/p2o5/organic` 등)에 질소(N) 관련 지표가 없음. 지금까지 확인한 여러 배 논문이
  질소를 핵심 변수로 다루는데, EC로 대리할지 별도 지표(예: `n_conc`)를 신설할지 팀 결정 필요.
- **온도-근권온도 환산 모델 부재**: `weather_snapshot.temp_avg`(기온)만으로는 토양 내부
  근권온도를 알 수 없음. 사과 근권온도 논문의 계수를 실제로 쓰려면 환산식 또는 국내
  지역별 지중온도 실측 문헌이 별도로 필요.
- **적지평가 방법론(MLCM vs 요인별 점수제) 미결정**: PRD §7 관련. 배 GIS 논문이 실증
  비교를 제공하나("MLCM이 실측과 더 유사하나 둘 다 수확량 검증은 없음"), 최종 방식은
  아직 팀이 정하지 않음.
- **시비량 단위 불일치**: 논문마다 mg/L(영양액), mg/kg(토양), kg/10a(포장 시비량) 등
  단위 체계가 달라 매번 환산이 필요함. 공통 단위 규약을 프로젝트 차원에서 먼저 정하면
  이후 논문 추출이 더 빨라질 것으로 보임. **예시**: P2O5의 경우 토양 mg/kg ← → 시비 kg/10a 환산 시 토양 밀도·유효층 깊이 가정 필요.

---

## 6. Iteration 4 완료 요약 / Iteration 5 준비 현황

### Iteration 4에서 실제로 처리된 것 (2026-08-01 소급 반영)
- ~~scout-4c: 감자 괴경/근부 냉해~~ → **완료**: Boydston 2006(괴경 동결치사), Shimoda&Hirota 2018(적설압축 방제), Yazaki 2013(토양서리, partial) 3편 반영
- scout-4a(한국 강수 임계값), scout-4b(배 대기온 고온 피해)는 **이번 라운드에서 다뤄지지 않음** — 여전히 미착수, Iteration 5로 이월
- 계획에 없던 추가 성과: 오이 temp_day/temp_soil 구조 확정(Wang 2018 + 이주영 2011), 상추 EC/pH/temp_day 재검증 5편, 감자 tuber allowed_max 실측 재확인 + DTR 신규지표

### Iteration 5 준비 — 사용자 요청 조건 반영 (2026-08-01)
사용자가 다음 조건을 명시: **①국내논문 우선 ②스캔본(이미지 판독) 지양 ③정확성 보장**. ②는 `docs/crop-domain-knowledge.md`가 지적한 실제 문제(스캔본 7편 중 일부가 한글 폰트 소실로 본문 유실)와 직결되므로, scout 단계에서 텍스트 레이어 유무를 1차 필터로 걸 것.

**[2026-08-02 갱신] 최우선 — 사과 착색기 온도 (코드레벨로 확인된 실채점 오류)**
0. **사과 착색기(coloring) `temp_day`/`temp_night_min`** — `dev` 반영분 `docs/guide-seed-known-issues.md`(P1/F-2)가 발견: optimal 12~13℃가 착색기(8/21~10/20) 실제 평년기온(8월 26.1/9월 22.2/10월 14.7℃)과 전혀 안 맞아 전국 대부분 0~9점. `temp_night_min`(8,8 점값)은 이미 삭제됨. 담당자 추정: "착색 유기 저온 또는 일교차(DTR) 문헌이 temp_day에 오매핑". **"사과 생육단계 온도" 같은 넓은 검색이 아니라 "사과 착색 저온요구 / 사과 착색 일교차" 특정 검색**

**최우선 gap (5작물 공통, 화학성 공백)**
1. 배 EC·유기물·P2O5 (13항목 중 3개 missing — 5작물 중 유일하게 손 안 댄 화학성)
2. 오이 pH·EC·유기물·P2O5의 **처방 기준**(현재는 이주영 2011의 "우수농가 실태치"뿐 — optimal_range로 쓸 수 있는 처방/문헌 기준 아님)
3. 감자 pH·EC·유기물·P2O5 전부 (이번 라운드도 온도/냉해만 다룸, 화학성은 여전히 0)
4. 상추 pH·유기물·P2O5의 **상·하한**(윤진주 2025는 6.5~6.9 협소구간만 커버, 극단값 미확인)

**차순위 gap**
5. 사과 생육단계별(fruit_growth/maturity) 대기 낮기온 — coloring은 위 0번으로 분리. 나머지 2단계는 P14(근권온도)만 있어 여전히 미확보
6. 배 대기온 고온피해 기준값 (scout-4b 이월)
7. 한국 실측 강수 임계값 — 배·오이·사과 전부 중국/외국 자료뿐 (scout-4a 이월)
8. 신규 지표 후보 7개의 스키마 반영 여부 팀 결정(§5 Iteration 4 신규 이슈 참고) — 이건 검색이 아니라 팀 결정 사안

> **참고**: `docs/guide-seed-known-issues.md`의 P5("crop-domain-knowledge.md 리포에서 유실")는 이미 해소됨 — 그 문서는 PR #66(2026-08-01 머지)으로 지금 `dev`에 있다.

## 6-1. Iteration 5 완료 요약 (2026-08-02, 사과 6개 갭 병렬 조사)

scout 6개(착색기·fruit_growth/maturity·EC·organic·rainfall·gdd) + conflict-checker 3개(EC·rainfall·gdd)를 병렬 실행. **이번 세션은 Aira MCP가 실제로 연결 안 돼 있어 전 에이전트가 Semantic Scholar/CrossRef/OpenAlex/RISS 공개 API로 대체 수행함 — 인용수 확인이 부분적으로만 가능했던 원인.**

| 갭 | 결과 | 후속 조치 |
|---|---|---|
| 0. 착색기 온도 | **국내논문 0편**(인용수 기준 통과작 없음), 해외 5편(Blankenship 1987 등)만 확보 | 사용자 지침("국내 우선")에 따라 **이번 라운드 보류**. 여전히 missing |
| 5. fruit_growth/maturity 온도 | **국내논문 0편**, 해외 4편(Warrington 1999 등)만 확보 | 상동, **보류**. 여전히 missing |
| 사과 ec | 국내 4편 확인 — 1편 blocked_paywall(TRKO202100009605, 원문 다운로드 실패), 2편 caution(메타데이터만), 1편 approve(측정법 reference_only, 원문 미확보) | registry 갱신함(위 §1). 원문 확보는 못 함 — 여전히 partial |
| organic | **신규 검색 없이 기존 보유 논문 2편 교차반영으로 해결** — hongro-fruit-quality-soil-2009.md + organic-apple-manual-soil-management.md에 이미 있던 유기물 수치를 registry에 반영 | registry 갱신 완료(위 §1), partial 유지하나 근거 대폭 강화 |
| rainfall_by_stage | 국내 2편 확인 — 1편 조건부 approve(김미리·김승규 2014, 단일계수만 확인) + 1편 caution(Do 2024, mm스펙 없어 정성적 근거만) | registry 갱신함(위 §1). 여전히 partial, mm 임계값 자체는 미해결 |
| gdd(Tbase) | 국내 3편 검증 — 1편 access_blocked(재시도 필요), 1편 reject(타겟 불일치 의심), 1편 reject(**GDD 아닌 chilling requirement로 확인** — 개념 다름) | Tbase는 여전히 partial. 대신 **신규 지표 chilling_requirement 1건 filled**(위 §1) — 뜻밖의 성과 |

**총평**: 사과 6개 갭 중 정량 수치가 실제로 새로 채워진 것은 organic(기존 자료 재발굴)과 chilling_requirement(신규 지표) 2건뿐. EC/rainfall/gdd는 "후보는 있으나 원문 미확보"로 막혀있고, 착색기/fruit_growth·maturity는 국내논문 자체가 없어 손을 못 댔다. **이 도메인(사과 국내 온도·화학성 연구)은 국제 인용지수에 안 잡히는 국내 학회 초록집·정부보고서 형태가 많아, Semantic Scholar류 인용수 필터링 자체가 근본적으로 잘 안 맞는다** — RISS/KISS 원문 직접 열람 또는 저자·학회·RDA 직접 문의 경로가 이 갭들 해소에 더 결정적일 것으로 보임.

### Iteration 6 준비
1. EC: TRKO202100009605 원문 확보(NTIS 재검색 또는 RDA 국립농업과학원 직접 문의) — national-scale 검증의 유일한 현실적 경로
2. rainfall: 김미리·김승규(2014) 원문 전체(KISS/DBpia 정식 구매 또는 저자 문의)로 전 생육단계 계수표 확보
3. gdd: 김수옥·윤진일(2010) 원문 재시도 1회, 실패 시 폐기하고 정식 심사 저널의 사과 물후기 예측 논문으로 재검색("사과 발육모델 DVR", "사과 만개기 예측 적산온도")
4. chilling_requirement: 신규 지표 스키마 반영 여부 팀 결정 필요(§5 이슈로 등록)
5. 착색기/fruit_growth·maturity: 국내논문이 이번엔 없었음 — 인용수 기준을 완화하거나(학회 초록집 허용) RDA 사과연구소 회색문헌으로 전환 검토 필요, 사용자 재확인 후 진행

## 6-2. Iteration 6 완료 요약 (2026-08-03, 사용자 직접 제공 PDF 4편 원문 확보)

Iteration 6 준비(위 §6-1) 항목 중 EC·rainfall·gdd 원문 확보 재검색을 scout으로 시도하던 중 사용자가 직접 다운로드한 PDF 4편을 제공, 원문을 전부 확보해 md화했다. **poppler(pdftoppm)가 시스템에 없어 Read 도구의 기본 PDF 페이지 렌더링이 실패**했고, 대안으로 ①born-digital PDF는 `pdftotext`(mingw64에 설치돼 있음, 텍스트 레이어 직접 추출), ②CMap 손실로 pdftotext가 실패한 PDF는 PyMuPDF(`fitz`)로 PNG 렌더링 후 이미지로 시각 판독하는 방식을 썼다.

| 논문 | 대상 gap | 결과 |
|---|---|---|
| Warrington et al.(1999) | fruit_growth/maturity 온도 | **filled(partial)** — 과실확장속도 온도선형관계 확보(위 §1). 해외자료지만 사용자가 직접 선택 |
| 김미리·김승규(2014) | rainfall_by_stage | **원문 전체 확보** — Iteration 5의 "단일계수만 확인" caution을 8개 계수+3모형비교로 해소(위 §1) |
| 이재범·김종윤(2023) | ec(측정법) | **원문 확보 완료** — Iteration 5의 "승인됐으나 원문 미확보" 상태를 해소, reference_only로 확정(위 §1) |
| 김수옥·윤진일(2010) | gdd(Tbase) | **원문 확보했으나 GDD는 여전히 미해결** — pdftotext로는 CMap 손실로 실패, PyMuPDF 이미지 판독으로 겨우 확보. 내용 확인 결과 GDD가 아니라 Chill Day 모형(냉각요구시간)이라 gdd.Tbase는 채우지 못함. 대신 chilling_requirement의 2번째 독립근거 + 신규지표 forcing_requirement_bloom(anti-chill day 275.1) 발견(위 §1) |

**총평**: EC·rainfall·gdd 3개 gap 중 실제로 registry 수치가 개선된 건 rainfall(대폭)과 EC(방법론 확정) 2건. **gdd.Tbase는 이번에도 못 채웠다** — 확인된 국내 후보 5편(Lee 2015, 김진희 2019, 김수옥·윤진일 2010 + 이번 재검증분) 전부가 GDD가 아니라 근처 개념(냉각요구시간·냉해위험도)이었다. 이는 우연이 아니라 **한국에서 "사과 적산온도" 관련 국내 학술자료가 압도적으로 "휴면·개화예측" 쪽에 몰려있고, "개화~수확 생육기 GDD"를 직접 다루는 국내 자료가 실제로 희소함**을 반복 확인한 것으로 보인다 — 다음 시도는 학술논문 검색보다 RDA 사과연구소의 재배력·적산온도 기술서(회색문헌) 쪽이 더 유망할 수 있다.

### Iteration 7 준비
1. **gdd.Tbase**: 여전히 미해결 — RDA 사과연구소/국립원예특작과학원의 적산온도 기반 재배력·수확기예측 기술서(회색문헌) 확인 필요. 학술논문 경로는 5회 시도 후 소득 없어 우선순위 하향 검토
2. **forcing_requirement_bloom·chilling_requirement 신규지표 2개**: 스키마 반영 여부 팀 결정(검색 아님)
3. **착색기/fruit_growth 나머지 1단계(fruit_growth는 이번에 partial 확보, maturity는 Warrington 논문에 포함돼 있어 사실상 커버됨)**: 착색기만 국내논문 필요성 여전
4. **EC national-scale(TRKO202100009605)**: 여전히 원문 미확보, NTIS/RDA 직접 문의 경로 유지

## 6-3. Iteration 7 완료 요약 (2026-08-03, 사용자 직접 제공 PDF 7편 원문 확보)

Iteration 6 준비(§6-2 하단) 항목 중 착색기(온도) 재검색을 scout 6개 에이전트로 병렬 수행하던 중(국내논문 여부 무관 조건으로), 사용자가 직접 다운로드한 PDF 7편을 제공해 전부 원문을 확보해 md화했다. 7편 모두 born-digital(스캔본 아님)이라 `pdftotext -layout`으로 전부 깨끗하게 추출됨(CMap 손실 없음, PyMuPDF 폴백 불필요) — 총 텍스트량 약 497KB(~125~140k 토큰), 사전 견적대로 진행 가능함을 확인 후 착수.

| 논문 | 대상 gap | 결과 |
|---|---|---|
| Sharpley et al.(2013) | p2o5_실태 | **구조적 설명 보강** — "legacy P" 개념(토양P 누적은 시비중단 후 7~27년간 유의한 감소 없음)으로 실태조사 극단적 과잉이 왜 단기간에 안 풀리는지 설명(위 §1) |
| Sugiura et al.(2013) | temp_day(fruit_growth/maturity) | **독립근거 2번째 확보** — 일본 40년 포장실측이 Warrington(1999) 통제환경 결론을 재확인(위 §1), 여전히 partial(bounded range 아님) |
| Gasparatos et al.(2011) | ec | **교차검증(해외)** — 그리스 관행/유기 비교, 측정법(1:1) 불일치로 직접대입 불가, 여전히 partial |
| Zanotelli et al.(2019) | rainfall_by_stage | **방법론 보강(해외)** — 3년 에디covariance 실측 Kc, Ru(2025)와 단위체계 달라 직접대체 불가, 여전히 partial |
| **Ryu et al.(2017)** | **temp_night_min(coloring)** | **최초 filled(국내 RDA 실측)** — 착색기 야간온도 LNT 20.1~23.4℃(촉진) vs HNT 26.1~29.4℃(억제). **이번 배치의 핵심 성과**(위 §1) |
| Merwin & Stiles(1994) | organic | **전용연구 최초 확보(해외)** — 관리방식(멀칭 권장)의 유기물·수량 메커니즘 실증, "적정구간"은 아님. 여전히 partial |
| Cepeda et al.(2021) | gdd(Tbase) | **기각(재인용 함정)** — Tbase=7.22℃가 Chaves(2017) 재인용치라 독립근거로 불채택. 여전히 missing |

**총평**: 7편 중 실제로 registry 상태(missing→filled)가 바뀐 것은 **temp_night_min(coloring) 1건뿐**이지만, 이는 이번 다일(多日) 사과 조사 전체에서 가장 중요한 성과다 — 착색기가 registry상 유일하게 순수 "missing"이었던 항목이었고, 담당자가 제기했던 "착색은 낮온도가 아니라 밤온도/일교차 문제"라는 구조적 가설(F-2)을 국내 RDA 실측으로 처음 실증했다. 나머지 6편 중 5편(Sharpley·Sugiura·Gasparatos·Zanotelli·Merwin&Stiles)은 각자의 gap을 partial 상태에서 근거만 두껍게 보강했고, 1편(Cepeda)은 재인용 체인의 함정을 확인하며 gdd.Tbase가 왜 아직도 안 풀리는지에 대한 반복적 증거만 추가했다. **국내논문 여부 무관 조건을 처음 적용한 이번 배치에서도 실제 "국내" 논문은 Ryu(2017) 1편뿐**이었다는 점은, 사과 온도·화학성 도메인의 국내 정식 심사저널 자료가 얼마나 희소한지를 다시 보여준다.

### Iteration 8 준비
1. **temp_day(coloring, 낮기온)**: Ryu(2017)는 야간온도만 다뤄 낮기온은 여전히 missing — 별도 문헌 필요, 또는 담당자 판단에 따라 "착색기엔 낮기온 자체가 핵심 변수가 아니다"로 결론짓고 지표 자체를 재정의할지 팀 결정
2. **Ryu(2017) 관측창(만개후 70~131일) ↔ 시드 착색기 정의(day_of_year 233~293) 정합성 확인**: DB 반영 전 필수, 만개일 추정 로직과 연결 필요(팀 결정, §5)
3. **Chaves et al.(2017, Acta Hortic. 1160:335-340) 원문 확보**: gdd.Tbase=7.22℃의 최초 도출 근거 확인 — 최우선 후보로 격상(재인용 체인 끝까지 추적)
4. **Merwin & Stiles 컴패니언 논문(1994, JASHS 119:216-222, 토양물리성)**: 같은 실험의 유기물 실측 데이터 추가 확보 가치 있음
5. **EC national-scale(TRKO202100009605)**: 여전히 원문 미확보, NTIS/RDA 직접 문의 경로 유지(3회 연속 이월)
6. **forcing_requirement_bloom·chilling_requirement·temp_night_min(coloring) 신규지표 반영**: 스키마 반영 여부 팀 결정(검색 아님) — 이번에 temp_night_min이 추가돼 신규지표 후보가 실질적으로 3개로 늘어난 상태

### 대기 중 (paywall 문제 해결 필요, 기존 이월)
- Yoon(2010), 2023 비료평가, 전북농기원(2018) 원문 확보 (배 EC/P2O5)
- 경로: RISS 원문 검색, DOI 우회, 저자 직접 요청, 기관 리포지토리

## 6-4. Iteration 8 완료 요약 (2026-08-03, 사용자 직접 제공 PDF 8편 원문 확보)

Iteration 7 준비(§6-3 하단) 항목 중 착색기 낮기온·gdd.Tbase(Chaves 2017)·EC national-scale을 scout 7개 에이전트로 병렬 재검색하던 중, 사용자가 직접 다운로드한 PDF 8편을 제공해 전부 원문을 확보해 md화했다. 8편 모두 born-digital(스캔본 없음)이라 `pdftotext -layout`으로 전부 정상 추출됨(단 Kang 2014는 한글 프로세 CMap 손실이 있었으나 핵심 Table 1은 손실 없이 보존).

| 논문 | 대상 gap | 결과 |
|---|---|---|
| **Kim, Ahn & Yun(2016)** | **temp_day(coloring, 낮기온)** | **최초 partial 전환(국내 홍로 실측)** — 항온챔버 25℃(양호) vs 30~35℃(착색·당 유전자 발현 억제). registry상 유일했던 순수 missing 항목 해소. **이번 배치의 핵심 성과** |
| **Chaves et al.(2017)** | **gdd(Tbase)** | **재인용 함정 최종 해결** — Tbase=7.22/5.55/6.11℃(품종별)가 재인용 아닌 워싱턴주 11지점×4개년 실측 직접도출임을 확인. 한국 품종 미검증이라 partial 유지(단 신뢰도 상승) |
| Kang et al.(2014) | ec(국가기준) | **국가기준 확인 + 신규 문제 발견** — EC≤2.0(기존 allowed_max 출처 확인). 동시에 Bray-1/Lancaster 유효인산 측정법 혼재 문제를 명확히 노출 |
| Ahn et al.(2011) | ec, p2o5_실태 | **지역실측(전북) 추가, 기존 optimal 재검토 신호** — 사과 EC 0.5dS/m(기존 optimal 0.8~1.5보다 낮음), 유효인산 631mg/kg(적정 2.1~3.2배 과잉) |
| Kim et al.(2012, 홍로 60농가) | organic(중요도 재평가) | **반증적 신호 확보** — 유기물 기여율 0.1~5.6%로 낮음(Merwin 1994와 같은 방향). 유효인산-착색 55.9% 신규연결 발견(신규 Gap) |
| Lee et al.(2023) | temp_day(fruit_growth/maturity) | **독립근거 3번째 확보(국내 20년)** — 온도↑→생육가속(홍로>후지), 품종별 반응차 신규 확인. 여전히 partial(bounded range 아님) |
| Treder et al.(2022) | rainfall_by_stage | **방법론 보강(해외)** — "유효강수(강수>ETo)" 개념, 총강수 mm≠실제흡수량 경고. mm구간 자체는 미해결 |
| Kim et al.(2019, CWSI) | rainfall_by_stage(간접) | **reference_only** — 자연강수가 아닌 인공관개(50%/75%ET) 스킴이라 갭을 채우지 못함. 향후 관개스케줄링 기능 참고자료로만 등록 |

**총평**: 8편 중 registry 상태가 실질적으로 전환된 것은 **temp_day(coloring) missing→partial 1건**이지만, 이로써 사과 15개 체크리스트 항목이 전부 filled/partial에 도달했다(100%, Iteration 7의 93%에서 상승). 그러나 이번 라운드의 더 중요한 성과는 백분율이 아니라 **기존 partial 수치들에 대한 재검토 신호**다 — 전북 실측 EC(0.5)가 기존 optimal(0.8~1.5)보다 낮게 나왔고, 유기물의 실제 중요도가 반증적으로 낮다는 두 번째 독립 신호가 확보됐다. gdd.Tbase는 재인용 함정을 완전히 해결(Chaves 2017 원 출처 확보)했으나 한국 품종 미검증이라는 새 조건이 남았다. **결론: 사과 도메인은 이제 "빈 항목 채우기" 단계를 벗어나 "기존 수치의 신뢰도 재검토" 단계로 넘어가야 한다** — 이는 CLAUDE.md §1 "정확성 우선" 철학과 정확히 부합하는 다음 단계다.

## 6-5. Iteration 9 완료 요약 (2026-08-04, 배 화학성 3개 gap — 신규 다운로드 없이 기존 자료 재조명 + 냉해 후보 4편 발굴)

Iteration 8까지 사과에 집중하던 것을 배로 전환. 배 13항목 체크리스트 중 **완전 미착수 상태였던 ec·organic·p2o5**(row 자체가 missing)를 scout 3개 에이전트로 병렬 탐색한 결과, **셋 다 이미 knowledge-base에 확보돼 있던 사과배치 논문(Ahn et al. 2011, 전북 110개소 과종별 비교표)에 배 데이터가 부수적으로 포함**돼 있었음을 재발견했다 — 신규 PDF 다운로드나 md 파일 생성 없이 registry §1만 갱신해 3개 항목을 즉시 missing→partial 전환했다. 별도로 냉해(개엽기·만개기) 임계온도도 탐색해 4편의 후보를 확보했으나 원문 미확보 상태다.

| 갭 | 결과 |
|---|---|
| **ec** | **최초 partial 전환** — Ahn(2011) 배 실측 0.6dS/m + Kang(2014) 과수원 통합상한 2.0. 신규 후보(원문 미확보): Lee & Lee(2011, 경남 25개소, 인용10), Lee et al.(2016, Acta Hortic. 배 단독, 접근차단) |
| **organic** | **최초 partial 전환** — Ahn(2011) 배 실측 35g/kg + Kang(2014) 과수원 통합기준 25~35(**정확히 겹침, 상호검증**). 배 전용 윤성탁(2010)은 기존 KB 보유하나 paywall로 정량수치 미확보 |
| **p2o5** | **최초 partial 전환** — Ahn(2011) 배 실측 859mg/kg(Lancaster법, 적정 200~300의 2.9~4.3배 과잉). 신규 후보(원문 미확보): Park, Lim & Lee(2012, 배 전용) |
| frost_damage(개엽기/만개기) | **미해결, 후보 4편 확보** — Ballard/Proebsting/Tukey(1971, WSU 배전용 고전, 사과 Warrington급 원표 추정)·임순희 외(2012, 국내 RDA 초록)·Lee et al.(2023, Scientia Hort. 인용5, 국내+국제, 만개기 -2.2/-4.4℃)·Ito et al.(2018, 휴면기 LT50, 지표 정의 다름). Lee(2023)와 Ballard(1971) 파생표 수치가 교차검증됨(만개기 -2.2/-4.4℃ 일치) — 원문 확보 시 즉시 filled 가능성 높음 |

**총평**: 이번 라운드의 핵심 교훈은 "새 논문을 찾기 전에 이미 가진 논문을 다시 봐야 한다"는 것이다 — 사과 배치에서 확보한 다과종 비교 논문(Ahn 2011)이 배의 화학성 공백 3개를 동시에 해소하는 근거가 되었다(배 6/13→9/13, 46%→69%). 다만 이 데이터는 배 전용 연구가 아니라 **전북 지역 소표본의 부수적 비교값**이라는 한계가 뚜렷하다 — national-scale·배 전용 검증은 여전히 미해결이며, Kang(2014)과의 수렴(organic 25~35)은 신뢰도를 높이지만 EC(0.6)·유효인산(859)은 아직 단일 지역 관찰치에 불과하다. 냉해는 신규 탐색 성과가 뚜렷해 Ballard(1971)·Lee(2023) 원문만 확보하면 사과처럼 filled 전환이 유력하다.

### Iteration 10 준비
1. **배 냉해(개엽기·만개기) 원문 확보 — 최우선**: Ballard/Proebsting/Tukey(1971, WSU Extension Circular) 스캔본 OCR 재시도 또는 poppler 설치, Lee et al.(2023, Scientia Hortic. DOI 10.1016/j.scienta.2022.111530) 정식 원문 확보. 두 문헌이 만개기 수치에서 이미 교차검증돼 있어 확보 즉시 filled 전환 유력
2. **배 EC/organic/p2o5 배 전용 연구 원문 확보**: Lee & Lee(2011, 경남), Park·Lim·Lee(2012, 배전용 P2O5), Lee et al.(2016, Acta Hortic. 배단독 EC — 접근 차단 재시도), 윤성탁(2010, KCI paywall 우회)
3. **배 EC/organic/p2o5의 national-scale 검증**: 사과와 동일한 구조적 문제(전북 지역 소표본 한계) — TRKO202100009605(5차 농업환경자원변동평가)에 배 세부항이 있는지 확인 필요(사과 EC national-scale 이슈와 동일 경로로 해결 가능)
4. **사과 이월 항목**: 아래 목록(§6-4에서 이월, 여전히 유효) 계속 진행

### 사과 이월 항목 (§6-4에서 이월, 여전히 유효)
1. **사과 EC optimal(0.8~1.5) 재검토**: 전북 실측(0.5)과 기존 6개 주산지 실측(0.8~1.5)의 격차 원인 규명 — 추가 지역 실측 확보 또는 기존 optimal 범위 조정 검토(팀 결정 선행 필요, 검색만으로는 해결 안 됨)
2. **유효인산 Bray-1/Lancaster 측정법 이중표기**: registry §1 p2o5 관련 행에 두 측정법 수치를 명시적으로 구분 표기하는 작업(문서 정리, 검색 아님)
3. **유효인산-착색 55.9% 연결 검증**: 인산 수준별 착색 반응을 직접 다룬 국내외 문헌 탐색(신규 Gap)
4. **temp_day(coloring) 포장 실측 검증**: Kim(2016)의 항온챔버 결과를 포장 대기온 실측으로 재확인하는 국내 후속 연구 탐색
5. **Chaves(2017) 방법론의 후지·홍로 적용**: Von Bertalanffy 커브핏을 한국 주력품종에 적용한 국내 연구 탐색(신규 Gap)
6. **EC national-scale(TRKO202100009605)**: 여전히 PDF 원문 미확보, ScienceON 로그인/기관IP 경유 또는 RDA 직접 문의(4회 연속 이월)
7. **organic 지표의 registry 내 비중 재검토**: 2개 독립 신호(Merwin 회귀왜곡, Kim 2012 기여율 낮음)가 쌓인 만큼, 팀 차원에서 organic 지표의 가중치·활용방식을 재논의할 시점(검색 아님, 팀 결정 사안)
