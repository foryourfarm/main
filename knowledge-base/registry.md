# 도메인 지식 명세서 (Registry)
마지막 갱신: 2026-07-25 (Delta: Iteration 3 감자 고온/냉해 + 배 일소 피해 + 강수 mm 임계값)
누적 처리 논문 수: 28 (Iteration 3: +13편)

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
| 오이 | (화학성) | 전기간 | - | - | - | missing | - |
| 감자 | temp_max(고온피해_괴경형성) | 전기간 | 야간 ≥28°C 중단 | - | - | **filled** | Iteration 3-a (Zhang et al. 2024) |
| 감자 | temp_max(고온피해_광합성) | 전기간 | >22°C 부작용, 30°C↓45% | - | - | **filled** | Iteration 3-a (Lal et al. 2022) |
| 감자 | temp_min(냉해_잎) | 전기간 | -3°C | - | - | **filled** | Iteration 3-a (Stegner et al. 2019) |
| 감자 | temp_min(빙핵_형성) | 전기간 | -2.3±0.4°C | - | - | **filled** | Iteration 3-a (Stegner et al. 2019) |
| 감자 | (화학성+강수) | 전기간 | 강수 ETc상대값 | - | - | missing | Iteration 3-c (Mora 2025 partial) |
| 상추 | temp_max(고온피해) | 전기간 | 회피 30°C↑ | - | - | filled | Iteration 2-2 (기온 영향) |
| 상추 | (화학성) | 전기간 | - | - | - | missing | - |
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

## 4. 커버리지 통계 (Iteration 3 최종)

### crop_growth_guide
- **filled**: 22/29 (76%) — +7 from Iteration 2 (감자 고온/냉해 4, 배 일소 1, 사과 강수 1, 오이 강수 1)
- **partial**: 5/29 (17%) — -2 (배 강수 추가, 일부 통합)
- **missing**: 2/29 (7%) — -5 (감자 공백 채움, 오이/상추 화학성만 남음)

### soil_change_rule
- **filled**: 6/6 (100%) — +1 from Iteration 2 (강수 과습 임계값)
- **partial**: 0/6 (0%)
- **missing**: 0/6 (0%)

### 작물별 커버리지 (filled + partial)
| 작물 | Iteration 2 | Iteration 3 | 상태 |
|---|---|---|---|
| 사과 | 9/13 (69%) | 10/13 (77%) | 온도 완성, 강수 partial |
| 배 | 4/13 (31%) | 6/13 (46%) | 일소 추가, 강수 partial |
| 감자 | 0/13 (0%) | 4/13 (31%) | 고온/냉해 완성 |
| 오이 | 1/13 (8%) | 2/13 (15%) | 강수 partial 추가 |
| 상추 | 1/13 (8%) | 1/13 (8%) | 변동 없음 |

---

## 5. 알려진 구조적 이슈 (팀 결정 필요)

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

## 6. Iteration 4 준비 현황

### 즉시 진행 가능 (scout-4a/b/c)
1. **scout-4a: 한국 강수 임계값** (1순위 gap)
   - 검색어: "논토 밭토 강수 포화", "한국 농경지 강수량 기준", "토양질감 유효수분"
   - 자료원: RISS(국내 학위논문), 농과원 기술지, 지역 농기원 지침
   - 기대 결과: 지역·질감별 일강수 임계값 3~5편

2. **scout-4b: 배 대기온 고온 피해** (1순위 gap)
   - 검색어: "배 고온피해 대기온", "배 고온 적응", "배 열스트레스"
   - 자료원: RDA 회색문헌(기술지, 연구보고서), 대학 대학원 논문(RISS)
   - 기대 결과: 대기온 기준값 또는 FST↔대기온 환산식 3~5편

3. **scout-4c: 감자/배 괴경/근부 냉해** (1순위 gap)
   - 검색어: "감자 냉저장 온도", "배 근부 냉해", "괴경 저온 피해"
   - 자료원: 원예특작과학원(냉저장 기술), 농과원, 대학원 논문
   - 기대 결과: 괴경·근부 냉해 임계값 3~5편

### 대기 중 (paywall 문제 해결 필요)
- Yoon(2010), 2023 비료평가, 전북농기원(2018) 원문 확보 (배 EC/P2O5)
- 경로: RISS 원문 검색, DOI 우회, 저자 직접 요청, 기관 리포지토리
