# 검색 로그 / 이미 채택된 논문 목록

> scout은 이 파일과 대조해서 중복 후보를 걸러낸다. registry-keeper가 매 사이클 끝에 갱신한다.

## Iteration 4 (2026-08-01) — 오이 근권온도 구조확정 + 상추 EC/pH 재검증 + 감자 괴경냉해/DTR (소급 반영)

> 이 13편은 registry-keeper 미실행 상태로 파일만 커밋돼 있다가 이번에 소급 반영됐다. 각 파일 말미의 `Registry Delta` 블록을 그대로 registry.md에 옮겼다.

### Iteration 4-오이 (3편, 전부 approved)
| 논문 | 저자 | 연도 | 상태 | 핵심 발견 |
|---|---|---|---|---|
| Distinct Impacts of Air/Root-Zone Temp on Cucumber | Wang, Gao & Tian | 2018 | approved/reference_only | temp_day≠temp_soil 구조를 실험으로 확정(수치는 미제공) |
| Water Use Efficiency of Cucumber (Greenhouse/Field) | Abdel Rahman & Al-Wahaibi | 2004 | approved/partial | 노지 관수 회귀식, 온실:노지≈1:3 (오만, 한국 미검증) |
| 시설재배 오이 엽중 무기성분 함량 | 이주영 외 | 2011 | approved/filled+partial | 적정 토양온도 18~20℃(P09와 수렴), 화학성 실태치 |

### Iteration 4-상추 (5편, 전부 approved)
| 논문 | 저자 | 연도 | 상태 | 핵심 발견 |
|---|---|---|---|---|
| EC 환산계수(간척지, 포화침출↔1:5) | Lee 외 | 2003 | approved/reference_only | 상추 EC 실측치에 적용 불가(저자 스스로 명시), 문헌간 EC 편차는 단위문제 아님을 반증 |
| Field Evaluation of Lettuce for Heat Tolerance | Lafta 외 | 2017 | approved/filled | 적온 18℃(재인용), allowed_max 30 노지실측 뒷받침 |
| 염류집적이 상추 발아·생육에 미치는 영향 | 강보구 외 | 1996 | approved/filled | EC 실측(수량최고 3.50 무비, 입모율 회귀식) |
| 인산석고 유래 소석회처리 퇴비-상추 | 윤진주 외 | 2025 | approved/partial | pH·유기물·유효인산 실측(협소구간) |
| Lettuce Yield/Quality High Tunnel vs Open-Field | Wallace 외 | 2012 | approved/partial | 적온 18.5℃(재인용, Lafta와 동일계보 가능성) |

### Iteration 4-감자 (5편, 전부 approved)
| 논문 | 저자 | 연도 | 상태 | 핵심 발견 |
|---|---|---|---|---|
| Snow Compaction for Frost-Killing Potato | Shimoda & Hirota | 2018 | approved/filled | 토양동결심도 0.3m↑ 시 자란모 괴경 고사(방제용) |
| Effective Killing of Volunteer Tubers by Soil Frost | Yazaki 외 | 2013 | approved/partial | 토양서리 기반 고사(수치 원문 재확인 필요) |
| 기온상승에 따른 감자 생육·수량 변화 | 이인하 외 | 2024 | approved/reference_only | 품종별(수미/조풍) 민감도 차이, ΔT 상대값(절대환산 불가) |
| Freezing Behavior of Potato Tubers in Soil | Boydston 외 | 2006 | approved/filled | 괴경 동결치사 -1.5~-2.8℃(인용34, 6년 포장실측) |
| High Temp/Daylength/Solar Radiation Effect on Potato | Kim & Lee | 2016 | approved/filled+partial | tuber allowed_max=27 강력재확인, DTR 신규지표 발견 |

### 통과율 / throughput (Iteration 4)
- 신규 발견: 13편 (전부 사용자 제공 PDF, scout 자동검색 아님)
- 승인: 13/13 (100%) — 전부 텍스트 추출 성공(스캔본 없음)
- registry 반영: filled 7, partial 5, reference_only(수치 미사용) 3 — 일부 중복 status(한 논문이 여러 지표에 걸침)

### 커버리지 상향 (13항목 체크리스트 기준)
- 감자: 4/13 → 5/13 (tuber allowed_max 실측 재확인)
- 오이: 2/13 → 3/13 (화학성 missing→partial)
- 상추: 1/13 → 4/13 (temp_day filled, ec 신규 filled, 화학성 partial)
- 신규 지표 후보 7개 발견(13항목 체크리스트 밖, §5/§6 registry.md 참고)

---

## Iteration 3 (2026-07-25) — 감자 고온/냉해 + 배 일소 피해 + 강수 mm 임계값 확정

### Iteration 3-a: 감자 고온/냉해 임계값 (4편 approved)
- **발견**: 5편
  1. Lal et al. (2022): >22°C 부작용, 30°C↓45% 수확량 ✓ approved
  2. Zhang et al. (2024): 야간 ≥28°C 괴경형성 중단 ✓ approved
  3. Stegner et al. (2019): -3°C 잎냉해, -2.3±0.4°C 빙핵 형성 ✓ approved
  4. Boguszewska et al. (2022): 38/25°C 극단 조건 주석 ✓ approved
  5. Tu et al. (2023): S. tuberosum 냉해값 미명시 → rejected
- **상태**: ✓ registry 반영 완료 (filled 4개 신규)
- **추가 정보**: 감자 고온 분기점이 재배 목적(초기 식재)과 기간에 따라 상이 → 다중 지표로 분리 기록

### Iteration 3-b: 배 고온 피해 (2편 approved)
- **발견**: 3편
  1. McClymont et al. (2016): 과실표면온도(FST) 47.1°C 일소 피해 임계 ✓ approved
  2. Goodwin et al. (2018): 방충망 시 일소 10% 감소 (참고용) ⚠️ caution (주 효과 아님)
  3. Hayama et al. (2014): 원문 미확보 → blocked_paywall
- **상태**: ✓ registry 반영 (filled 1, caution 1, blocked 1)
- **주의**: FST(과실표면온도) ≠ 대기온. 별개 현상(태양복사+증발산)으로 구분 기록

### Iteration 3-c: 강수 mm 기준값 (1편 filled, 4편 partial)
- **발견**: 5편
  1. Zhang et al. (2025 Review): 일 강수 30-50mm 과습 임계 ✓ approved → **FILLED** (일반 원리)
  2. Wang et al. (2025): 온실 오이 봄/가을 기간별 수분수요 (225-240, 105-120 mm) ⚠️ partial (온실만)
  3. Ye et al. (2019): 배 270mm/시즌(DP-5, 2회 관개) ⚠️ partial (중국, 환경 상이)
  4. Mora et al. (2025): 감자 수분수요 ETc 상대값 ⚠️ partial (절대값 미정, ETc 기준값 필요)
  5. Ru et al. (2025): 사과 생육단계별 강수(개화 120, 과실팽창 319, 성숙 113 mm) ⚠️ partial (중국, R²=0.63)
- **상태**: ✓ registry 반영 (filled 1: soil_change_rule, partial 4: crop_growth_guide)

### 통과율 / throughput (Iteration 3)
- 이번 사이클 신규 발견: 13편
- conflict_checker 승인: 7편 (53.8%)
- extractor 처리 가능: 9편 (69.2% complete)
- 실제 registry 반영: filled 7개, partial 4개, blocked/rejected 2개
- **coverage 상향**:
  - 감자: missing → filled (고온 2 + 냉해 2 = 4개)
  - 배: missing → filled (일소 1 + partial 강수 1)
  - 사과: partial 강수 (단계별 추가)
  - 오이: partial 강수 (온실, 노지 미정)
  - 강수: partial → filled (과습 임계, 일반 원리)

### 커버리지 통계 (Iteration 3 최종)

| 지표 | Iteration 2 | Iteration 3 | 변화 |
|---|---|---|---|
| **crop_growth_guide** | | | |
| - filled | 15/29 (52%) | 22/29 (76%) | **+7** |
| - partial | 7/29 (24%) | 5/29 (17%) | **-2** |
| - missing | 7/29 (24%) | 2/29 (7%) | **-5** |
| **soil_change_rule** | | | |
| - filled | 5/6 (83%) | 6/6 (100%) | **+1** |
| - partial | 1/6 (17%) | 0/6 (0%) | **-1** |
| **논문 통과율** | | | |
| - scout_found | - | 13 | - |
| - conflict_approved | - | 7 (53.8%) | - |
| - extractor_complete | - | 9/13 (69.2%) | - |
| - extractor_partial | - | 3/13 (23.1%) | - |
| - blocked/rejected | - | 2/13 (7.7%) | - |
| **누적 논문 수** | 15 | **28** | **+13** |

**주요 성과:**
- 감자: 0 → 4 filled (고온 2 + 냉해 2)
- 배: 1 → 3 (배 일소 추가)
- 강수: partial → filled (과습 임계, 일반 원리)
- 사과/오이: partial 강수 추가 (단계별·온실)

---

## Iteration 2 (2026-07-25) — 강수/기온 영향 로직 + 배 화학성 대체 자료 발견

### Iteration 2-2: 강수/기온 영향 로직 확정
- **발견**: 5개 항목 완료
  1. 강수 과다: 토양 산소 부족 → 뿌리 부패 (mm 기준값 아직 미정)
  2. 가뭄: AWR <100(제한급수), <50(심각); -0.2~-0.3 MPa 임계값
  3. 고온 피해:
     - 사과: 31°C 이상
     - 오이: 30°C 이상
     - 상추: 30°C 이상
  4. 저온/냉해 (사과 확정):
     - 개엽기: -5.0°C (10%), -9.4°C (90%)
     - 만개기: -2.2°C (10%), -3.9°C (90%)
  5. GDD: ∑[(Tmax+Tmin)/2 - Tbase]; 배 85°C 확정
- **상태**: ✓ registry 반영 완료 (crop_growth_guide + soil_change_rule)
- **미완료**: 감자 기온 영향, 오이/감자/상추 GDD 베이스온도, 강수 mm 임계값

### Iteration 2-1: 배 화학성 대체 자료 발견
- **발견**: 배 pH 완성
  - 배 pH: 5.8~7.0 (공개 자료 확정, Yara Korea + 충청북도 농업기술원)
- **상태**: ✓ registry 반영 (filled)
- **미완료**: 배 EC, 배 P2O5 (흙토람 비공개, 다음 방법: 직접 문의)

### 통과율 / throughput (Iteration 2)
- 이번 사이클 신규 발견: 7개 (배 화학성 1 + 온도/강수 로직 6)
- 실제 registry 반영: filled 1, partial 7 추가
- coverage 상향: 사과 4개→7개 (+75%), 배 2개→4개 (+100%), 오이·상추 각각 1개, 감자 0개

---

## Iteration 1 (2026-07-25) — 배 화학성 보강 시도, 전량 paywall 차단

### 검색/발견
- scout 발견: 5편 (배 pH/EC/P2O5 관련)
- conflict-checker 승인: 3편 (Yoon 2010, 2023 비료평가, 전북농기원 2018) — 나머지 2편(caution)도 유료 확인되어 이번 사이클 미처리
- extractor 처리: 3편 → **3편 모두 blocked_paywall** (원문 미확보, 초록만 접근 가능)

### 결과 상세
| 논문 | crop | indicator | 상태 | 비고 |
|---|---|---|---|---|
| Yoon (2010) | 배 | EC | blocked_paywall | 수치 미확보, 원문 유료 |
| 2023 비료평가 | 배 | P2O5_실태 | blocked_paywall | 배 개별 수치 미확보 |
| 전북농기원 (2018) | 배 | pH, P2O5 | blocked_paywall | 수치 미확보, 원문 유료 |

### registry.md 반영
- 변경 없음 (신규 filled/partial 데이터 0건). 배 pH/EC/P2O5/organic은 여전히 missing.

### 통과율 / throughput
- scout_found: 5
- conflict_checker_approved: 3 (60%)
- extractor_processed: 3
- delta_returned(실제 데이터 반영): 0
- success_rate: 0% (3/3 blocked_paywall)

### 메모
- 배 관련 화학성(pH/EC/P2O5) 국내 자료가 전반적으로 paywall/초록집 형태로만 유통되는 경향 확인. 정부/학술지 출처라 신뢰도는 높으나 원문 확보 경로(RISS 원문 PDF, 기관 리포지토리, DOI 우회) 별도 탐색 필요.
- 다음 사이클: (a) 배 pH/EC/P2O5 대체 키워드로 재검색, (b) 이번 3편은 원문 확보 재시도 후보로 큐에 보류(재추천 대상에서 완전 제외하지 않음).

## Iteration 3 논문 상세 (새로 채택)

### 감자 고온/냉해 (Iteration 3-a)
| 논문 | 저자 | 연도 | 상태 | 핵심 수치 |
|---|---|---|---|---|
| High temperature impacts on potato | Lal et al. | 2022 | approved | >22°C 부작용, 30°C↓45% 수확량 |
| Tuber formation temperature thresholds | Zhang et al. | 2024 | approved | 야간 ≥28°C 괴경형성 중단 |
| Frost damage in Solanum tuberosum | Stegner et al. | 2019 | approved | -3°C 잎냉해, -2.3±0.4°C 빙핵 |
| Extreme conditions potato physiology | Boguszewska et al. | 2022 | approved | 38/25°C 극단 조건 |
| Solanum tuberosum frost resistance | Tu et al. | 2023 | rejected | S. tuberosum 냉해값 미명시 |

### 배 고온/일소 (Iteration 3-b)
| 논문 | 저자 | 연도 | 상태 | 핵심 수치 |
|---|---|---|---|---|
| Surface temperature and sunscald in pear | McClymont et al. | 2016 | approved | FST 47.1°C 일소 임계 |
| Shade management in pear orchards | Goodwin et al. | 2018 | caution | 방충망 10% 감소 (참고용) |
| Pear heat stress mitigation | Hayama et al. | 2014 | blocked_paywall | 원문 미확보 |

### 강수 mm 기준 (Iteration 3-c)
| 논문 | 저자 | 연도 | 작물 | 상태 | 핵심 수치 |
|---|---|---|---|---|---|
| Waterlogging and rainfall thresholds | Zhang et al. | 2025 | 일반 | approved/filled | 일 30-50mm 과습 임계 |
| Water requirement in greenhouse cucumber | Wang et al. | 2025 | 오이 | approved/partial | 봄 225-240mm, 가을 105-120mm (온실) |
| Irrigation for pear production | Ye et al. | 2019 | 배 | approved/partial | 270mm/시즌 (중국) |
| Water-use efficiency in potato | Mora et al. | 2025 | 감자 | approved/partial | ETc 상대값 (절대값 미정) |
| Rainfall requirements for apple | Ru et al. | 2025 | 사과 | approved/partial | 개화 120, 과실팽창 319, 성숙 113mm (중국, R²=0.63) |

---

## 이미 채택되어 정리 완료된 논문 (다시 추천하지 말 것)

### Cycle 1-2 (수동 시드, 6편)
- 신고배 재배지 내 수체 및 토양의 탄소 및 질소 저장량 (이태규 외, 2013)
- 질소 시용수준에 따른 배 신고 실생묘의 생육과 질소관련물질의 변화 (김송남 외, 2006)
- 과원의 근권 온도가 토양 공기 및 화학성과 사과나무 생육에 미치는 영향 (박진면·오성도, 2001)
- 지목과 토양적성도를 활용한 사과 재배적지 선정에 관한 연구 (백창엽 외, 2023)
- GIS 기반의 토양 및 기후조건 통합 배 과수의 적지 평가 (김호정·심교문, 2019)
- 배 생육 기간 중 온도 환경이 세포벽 구성 물질 변화에 미치는 영향 (백윤주, 2022)

### Cycle 3 (자동 루프, 9편 + EC 3편 + Iteration 3: 13편)

#### Iteration 2-2에서 확정 (6편)
- 홍로 품종 과실품질과 토양 pH의 관계 [사과 pH filled]
- RDA 비료사용처방 (표준영농교본) [사과 pH + P2O5 filled]
- 전국 805농가 토양 화학성 실태조사 [사과 P2O5 극단적 과잉 partial]
- 유기재배 매뉴얼: 작물별 토양 화학성 기준 [유기 P2O5 filled]
- 협회 가이드: 현장 시비량 보정 (P2O5 10~12 kg/10a + 20%) [현장값 filled]
- 초생재배 토양산도 안정화 [사과 초생재배 pH 6.2~6.4]

#### EC 강화 (3편)
- 홍로 품종 과실품질과 토양 EC의 관계 (hongro-fruit-quality-soil-2009) [사과 EC: 0.8~1.5 filled]
- 초생재배 과원 토양산도 변화와 EC (sod-orchard-soil-acidity-2009) [사과 EC: 0.4~1.2 추가 filled]
- 유기 재배 관리 매뉴얼: 토양 EC 기준 (organic-apple-manual-soil-management) [사과 EC: 0.8~1.5 표준 filled]

#### Iteration 3 신규 (13편)
**감자 고온/냉해 (4편)**
- Lal et al. (2022): 감자 고온 영향 [temp_max filled]
- Zhang et al. (2024): 감자 야간 고온 괴경형성 [temp_max filled]
- Stegner et al. (2019): 감자 냉해 임계 [temp_min filled]
- Boguszewska et al. (2022): 감자 극단 조건 [참고용]

**배 고온/일소 (2편)**
- McClymont et al. (2016): 배 일소 FST 47.1°C [temp_max sunburn filled]
- Goodwin et al. (2018): 배 방충망 일소 감소 [참고용]

**강수 mm 기준 (5편)**
- Zhang et al. (2025): 강수 과습 임계 30-50mm [soil_change_rule filled]
- Wang et al. (2025): 오이 온실 강수 [rainfall_greenhouse partial]
- Ye et al. (2019): 배 강수 270mm [rainfall_optimal partial]
- Mora et al. (2025): 감자 수분수요 [rainfall partial]
- Ru et al. (2025): 사과 단계별 강수 [rainfall_by_stage partial]

#### Iteration 4 (13편, 2026-08-01 소급 반영)
**오이 (3편)**
- Wang, Gao & Tian (2018): 기온·근권온도 별개 메커니즘 [temp_day/temp_soil 구조 확정, reference_only]
- Abdel Rahman & Al-Wahaibi (2004): 온실·노지 관수 효율 [rainfall_optimal_field partial]
- 이주영 외 (2011): 오이 엽중 무기성분 [temp_soil filled, 화학성 partial]

**상추 (5편)**
- Lee 외 (2003): EC 환산계수(간척지) [reference_only, 상추 적용 불가]
- Lafta 외 (2017): 노지 내열성 평가 [temp_day filled]
- 강보구 외 (1996): 염류집적 발아·생육 [ec filled]
- 윤진주 외 (2025): 소석회처리퇴비-상추 [ph/organic/p2o5 partial]
- Wallace 외 (2012): High Tunnel vs Open-Field [temp_day partial]

**감자 (5편)**
- Shimoda & Hirota (2018): 적설압축 방제 [soil_frost_depth_snow_compaction filled]
- Yazaki 외 (2013): 토양서리 자란모 방제 [soil_frost_tuber_killing partial]
- 이인하 외 (2024): 온도구배하우스 [reference_only, ΔT 상대값]
- Boydston 외 (2006): 괴경 동결거동 [temp_min_frost_damage_tuber filled]
- Kim & Lee (2016): 고온·일장·일사 영향 [temp_day tuber allowed_max filled, DTR 신규]

## 원문 접근 실패 (paywall/초록만) — 재시도 후보, 재추천 제외하지 않음

- Yoon (2010), 배 EC 관련 — blocked_paywall (Iteration 1)
- 2023 비료평가 보고서, 배 P2O5_실태 — blocked_paywall (Iteration 1)
- 전북농기원 (2018), 배 pH·P2O5 — blocked_paywall (Iteration 1)

## 실행한 검색 쿼리 기록 (쿼리 | 결과 상태 | 날짜)

- 배 토양 pH EC P2O5 적정범위 (관련 유사 쿼리) | 5편 발견, 3편 승인 후 전량 paywall | 2026-07-25

## 검색했으나 결과 없음으로 처리된 키워드

*(3회 이상 검색해도 관련 논문을 못 찾은 키워드는 여기로 옮기고 큐에서 제거)*
