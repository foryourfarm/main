# Warrington, Fulton, Halligan & de Silva (1999) — Apple Fruit Growth and Maturity are Affected by Early Season Temperatures

**Source:** Journal of the American Society for Horticultural Science (JASHS) 124(5):468-477
**Citation Count:** 155
**Status:** Iteration 6, Approved (fruit_growth/maturity 온도, 해외/뉴질랜드 — 사용자 직접 제공 PDF)

---

## 8단계 정리

### 1. 데이터 수집 방법
뉴질랜드 HortResearch National Climate Laboratory(Palmerston North)의 통제환경(controlled environment, CE) 챔버. 'Delicious', 'Golden Delicious', 'Braeburn', 'Fuji', 'Royal Gala' 5품종(M.9 대목, 화분재배)을 대상으로 1993~1997년에 걸친 4개 실험(Expt.1~4)에서 다양한 최고/최저기온 조합(9/3, 13/3, 16/6, 19/3, 19/9, 22/12, 25/9, 25/15℃ 등)을 만개후일수(DAFB, Days After Full Bloom) 구간별로(주로 10~40, 40~80, 10~80, 1~40 DAFB) 처리했다. 과실직경을 버니어캘리퍼스로 주2회(CE 처리 중) 또는 격주(야외 이전 후) 측정했고, 수확 시 과중·가용성고형물함량(SSC)·경도·전분지수·배경색을 측정했다.

### 2. 표본
실험별 품종당 2~16주 반복(품종·실험마다 상이). 1996~97년 실험(Expt.4)은 처리를 두 개의 서로 다른 CE 챔버에 분산 배치해 챔버 간 효과를 직접 검증했다.

### 3. 메커니즘
사과 과실은 개화 후 35~45일 지속되는 세포분열기(cell division phase)와 이후 수확까지 이어지는 세포확장기(cell expansion phase) 두 단계로 성장한다. 초기 40 DAFB(세포분열 위주 구간)가 이후 40 DAFB(세포확장 위주 구간)보다 온도에 훨씬 민감하다. 저온(9/3, 13/3℃)에 오래 노출된 과실을 야외로 옮기면 확장속도가 급격히 증가하는 보상반응이 관찰됐는데, 이는 저온 조건에서 세포분열기가 40 DAFB를 넘어 계속 연장됐음을 시사한다(기존 포장 연구에서는 보고된 적 없는 현상).

### 4. 정량적 결과 ⭐
- **10~40 DAFB 평균기온(6~20℃ 범위)과 과실확장속도(mm/day) 사이 유의한 선형관계**(모든 품종 P≤0.01). 회귀식(Fig. 3): Braeburn y=0.0747x-0.25, Delicious y=0.0655x-0.27, Golden Delicious y=0.0619x-0.29, Fuji y=0.0726x-0.36 — **기울기 0.062~0.075 mm·day⁻¹·℃⁻¹**.
- 9/3℃ vs 25/15℃ 처리 간 확장속도 최대 8배 차이(Expt.2). 40 DAFB까지 온도차에 따라 확장속도 최대 4배 차이(Expt.1, 13/3 vs 22/12℃).
- 수확기 성숙지표(Table 5, 6): 고온처리군일수록 SSC↑, 배경색(황색화)↑, 경도↓, 전분지수(전분분해)↑ — 대부분 P≤0.05~0.001로 유의. 예: 'Braeburn' 1~40DAFB 13/3℃ vs 22/12℃ → SSC 10.4%→12.0%, 경도 73.6N→58.9N, 전분지수 0.3→2.2, 배경색 4.4→5.8(모두 P≤0.001).
- 40~80 DAFB 구간에 부여한 온도처리는 과중·성숙지표에 거의 영향 없음(세포분열 종료 후 민감도 급감) — 30~40일 구간(개화 후 30~40일)이 수확성숙 결정에 가장 critical하다는 기존 포장연구(Blanpied and Ben-David 1970; Eggert 1960; Kronenburg 1988)와 일치.
- 야간온도 단독 처리(Blankenship 1987, 52DAFB부터 부여)는 SSC·경도에 영향 없었음 — 40DAFB 이후 온도처리가 무의미하다는 본 연구 결과와 부합.

### 5. 산업 적용
조기 계절온도로부터 최종 과중·품질을 예측하는 구획모델(compartment model, Austin et al. 1999)의 기초 입력값으로 활용됨. 뉴질랜드 냉량 봄철 시즌의 과실 소과(小果) 문제를 온도-생장속도 관계로 정량 설명.

### 6. 한계
통제환경(포트재배, CE챔버) 실험이라 포장 실측과 완전히 같지 않을 수 있음(저자도 반복성 논의에서 명시). 뉴질랜드 5품종 한정 — 한국 주요 품종(후지는 포함, 홍로는 미포함)·기후 미검증. **"적정범위"가 아니라 "온도-속도 연속 선형관계"라 optimal_min/max(구간) 형태로 바로 대입 불가.** 이 연구범위(최고 25℃) 안에서는 고온측 악영향 임계값이 확인되지 않음 — 단, 'Royal Gala'가 22/12℃ 처리에서 원인불명 낙과가 광범위하게 발생해 자료가 누락된 사례가 있어(Expt.4), 고온 상한이 이 범위보다 낮을 가능성을 완전히 배제하지는 못함.

### 7. 구조적 문제 ⭐⭐
이 논문은 registry의 사과 `temp_day`(fruit_growth/maturity 단계, 기존 상태 missing)를 채우는 유일한 실험 데이터이지만, **DB 스키마의 optimal_min/optimal_max(구간) 형태와 근본적으로 안 맞는다.** 이 논문은 "구간을 벗어나면 나쁘다"가 아니라 "온도가 높을수록 계속 빨라진다"는 무경계 단조증가 관계를 보여준다. 담당자가 기대하는 "적정범위" 개념과 이 논문의 "속도-온도 반응함수" 개념이 다르므로, ① 이 값을 참고자료(reference)로만 쓰고 optimal_range는 계속 missing으로 두거나, ② 스키마를 확장해 선형계수를 별도로 저장하는 방안 중 팀 결정이 필요하다.

### 8. 새로운 Gap
한국 품종(후지·홍로 등) 대상의 동일 실험(포장 또는 통제환경) 부재. 고온측 악영향 임계값(28℃ 이상 처리)을 직접 검증한 데이터 부재. 'Royal Gala' 고온 낙과의 원인 규명 문헌.

---

## Registry Delta

**Crop:** 사과
**Indicator:** temp_day (fruit_growth + maturity, 선형관계 — optimal_min/max 형태 아님)
**Status:** partial (bounded range 아님, 해외자료, 국내 검증 없음)
**Value:** 과실비대기(10~40 DAFB) 확장속도 = 0.062~0.075 mm/day 증가 per ℃(6~20℃ 구간, 품종별 회귀식). 고온일수록 성숙(SSC↑·배경색↑·경도↓·전분분해↑) 가속. 최초 40 DAFB가 이후 40 DAFB보다 온도민감도 훨씬 큼(세포분열기 vs 세포확장기).
**Confidence:** 높음(인용155, NZ HortResearch 정밀 통제환경, 5품종×4개년 실험) / 한국 적용성은 낮음(해외자료, 미검증)
**Source:** Warrington, I.J., Fulton, T.A., Halligan, E.A., de Silva, H.N. (1999), JASHS 124(5):468-477
**Note:** "적정범위(optimal_min/max)"가 아니라 "온도-생장속도 선형관계식"이라 현재 crop_growth_guide 스키마(구간 기반)에 직접 대입 불가. 사용자가 "국내논문 우선" 원칙을 이번엔 의도적으로 벗어나 직접 선택한 예외 자료 — 향후 한국 조건 비교 기준으로 참고할 것.
