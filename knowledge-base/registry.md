# 도메인 지식 명세서 (Registry)
마지막 갱신: 2026-08-01 (Delta: Iteration 4 — 오이 3편(근권온도 구조확인·노지관수·엽분석) + 상추 5편(EC·pH·온도 재검증) + 감자 5편(괴경냉해·괴경형성·DTR) 소급 반영)
누적 처리 논문 수: 41 (Iteration 4: +13편)

> **Iteration 4 반영 경위**: 이 13편은 이번 갱신 이전에 이미 `knowledge-base/papers/{cucumber,lettuce,potato}/`에 파일로 커밋돼 있었으나(각 파일 말미에 `Registry Delta` 블록 존재), registry-keeper가 실행되지 않아 이 문서에는 한 번도 집계되지 않은 상태였다. 이번에 각 파일의 Registry Delta를 읽어 소급 반영했다.

> 이 파일은 DB.md의 `crop_growth_guide`, `soil_change_rule` 스키마를 기준으로 무엇이
> 채워졌고 무엇이 비었는지만 압축해서 담습니다. 논문 본문은 `papers/` 폴더에만 존재합니다.

## 1. crop_growth_guide 커버리지

| crop | indicator | growth_stage | optimal range | allowed range | weight | status | source(s) |
|---|---|---|---|---|---|---|---|
| 사과 | temp_day(생육기온) | 전기간 | - | - | - | missing | - |
| 사과 | ph | 전기간 | 6.0~6.5 | 5.5~6.8 | - | filled | RDA 비료사용처방, 홍로품종 과실품질 |
| 사과 | ec | 전기간 | 0.8~1.5 | 0.4~2.0 | - | **partial** | papers/apple/hongro-fruit-quality-soil-2009.md(N=60, 품종특화), papers/apple/sod-orchard-soil-acidity-2009.md(N=4처리, 초생), papers/apple/organic-apple-manual-soil-management.md(범위값). **한계**: 소규모 조사+매뉴얼만. national-scale 검증 부재. RDA TRKO202100009605 원문 접근 불가(404) |
| 사과 | organic | 전기간 | 참고치만 있음(단일 실측) | - | - | partial | papers/apple/root-zone-temperature-2001.md |
| 사과 | p2o5 | 전기간 | 30~50 mg/kg | 20~60 | - | filled | RDA 비료사용처방 (Bray-1) |
| 사과 | p2o5_유기 | 전기간 | 40~60 mg/kg | 25~80 | - | filled | 유기재배 매뉴얼 |
| 사과 | p2o5_실제시비 | 전기간 | 10~12 kg/10a | +20% 현장보정 | - | filled | 협회 가이드 |
| 사과 | p2o5_실태 | 전기간 | 평균 22.5 kg/10a | (극단적 과잉) | - | partial | 실태조사 805농가 |
| 사과 | temp_max(고온피해) | 전기간 | 회피 31°C↑ | - | - | filled | Iteration 2-2 (기온 영향) |
| 사과 | frost_damage_budburst | 개엽기 | -5.0°C(10%), -9.4°C(90%) | - | - | filled | Iteration 2-2 (냉해 임계) |
| 사과 | frost_damage_fullbloom | 만개기 | -2.2°C(10%), -3.9°C(90%) | - | - | filled | Iteration 2-2 (냉해 임계) |
| 사과 | gdd(적산온도) | 전기간 | ∑[(Tmax+Tmin)/2 - Tbase] | - | - | partial | Iteration 2-2 (베이스온도 작물별 확정 필요) |
| 배 | temp_day(생육기온) | 전기간 | O(S1~N1 4단계) | O | - | filled | papers/pear/gis-soil-climate-suitability-2019.md |
| 배 | 연평균기온 | 전기간 | O(S1~N1 4단계) | O | - | filled | papers/pear/gis-soil-climate-suitability-2019.md |
| 배 | ph | 전기간 | 5.8~7.0 | - | - | filled | Yara Korea + 충청북도 농업기술원 (Iteration 2-1) |
| 배 | ec | 전기간 | - | - | - | missing | - |
| 배 | organic | 전기간 | - | - | - | missing | - |
| 배 | p2o5 | 전기간 | - | - | - | missing | - |
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
| 사과 | rainfall_by_stage | 전기간 | 개화-결실 120mm, 과실팽창 319mm, 성숙 113mm | - | - | **partial** | Iteration 3-c (Ru et al. 2025) ⚠️ 중국 모델(R²=0.63), 지역 편차 큼 |

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

## 4. 커버리지 통계 (Iteration 4 최종, 2026-08-01)

> **denominator 주의**: "13"은 Iteration 3까지 쓰던 고정 체크리스트(작물당 temp_day/temp_night_min/frost×2/temp_max/gdd/ph/ec/organic/p2o5류/rainfall)를 기준으로 한 근사치이며 실제 스키마 제약은 아니다. Iteration 4에서 이 체크리스트 **밖의 신규 지표 후보**(temp_soil, rainfall_optimal_field, diurnal_temp_range, tuber_initiation_optimal_temp, soil_frost_depth_snow_compaction, soil_frost_tuber_killing, temp_min_frost_damage_tuber — 총 7개)가 발견됐다. 이들은 기존 13항목 분모에는 넣지 않고 별도로 표기한다(넣으면 "채워짐 비율"이 인위적으로 부풀려짐). reference_only 논문(구조 검증·측정법 검증용, 수치 자체는 못 씀) 3편도 분모에서 제외.

### crop_growth_guide (기존 13항목 체크리스트 기준)
- 작물별 filled+partial 합산 변화는 아래 "작물별 커버리지" 표 참고(정확한 산정은 크롭별로만 의미 있음 — 5작물을 하나의 분모로 합산하면 왜곡됨)
- 신규 지표 후보(13항목 체크리스트 밖): 7개 (partial 상태 다수, 스키마 반영 여부 팀 결정 대기)
- reference_only(수치 사용 불가, 구조/방법론 검증용): 3편 — Wang et al.(2018, 오이 temp_day/temp_soil 분리 근거), Lee et al.(2003, 상추 EC 측정법), 이인하 외(2024, 감자 ΔT 상대값)

### soil_change_rule
- 변동 없음: filled 6/6 (100%) — Iteration 4에서 soil_change_rule 관련 신규 논문 없음

### 작물별 커버리지 (filled + partial, 13항목 체크리스트 기준)
| 작물 | Iteration 3 | Iteration 4 | 상태 |
|---|---|---|---|
| 사과 | 10/13 (77%) | 10/13 (77%) | 변동 없음(이번 라운드는 오이·상추·감자만 다룸) |
| 배 | 6/13 (46%) | 6/13 (46%) | 변동 없음 |
| 감자 | 4/13 (31%) | **5/13 (38%)** | tuber allowed_max=27 실측 재확인(신규 filled) — 화학성·강수는 여전히 missing |
| 오이 | 2/13 (15%) | **3/13 (23%)** | 화학성이 missing→partial(우수농가 실태치). temp_day 근권온도 혼동 구조는 확정됐으나 수치 자체는 아직 missing |
| 상추 | 1/13 (8%) | **4/13 (31%)** | temp_day 정식 filled(재인용 수렴+노지실측) + ec 신규 filled + 화학성 missing→partial |

**신규 지표 후보 현황(13항목 밖, 별도 트랙)**: 오이 2개(temp_soil filled, rainfall_optimal_field partial) / 감자 5개(temp_min_frost_damage_tuber filled, tuber_initiation_optimal_temp partial, diurnal_temp_range partial, soil_frost_depth_snow_compaction filled, soil_frost_tuber_killing partial) — DB.md `crop_growth_guide.indicator` 목록에 추가할지, 어떤 걸 크롭할지는 §5 구조적 이슈 참고.

---

## 5. 알려진 구조적 이슈 (팀 결정 필요)

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

### 대기 중 (paywall 문제 해결 필요, 기존 이월)
- Yoon(2010), 2023 비료평가, 전북농기원(2018) 원문 확보 (배 EC/P2O5)
- 경로: RISS 원문 검색, DOI 우회, 저자 직접 요청, 기관 리포지토리
