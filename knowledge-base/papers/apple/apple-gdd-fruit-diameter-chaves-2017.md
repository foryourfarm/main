# Chaves, Salazar, Schmidt, Dasgupta & Hoogenboom (2017) — Modeling Fruit Growth of Apple

**Source:** Acta Horticulturae 1160:335-340, DOI: 10.17660/ActaHortic.2017.1160.48, X International Symposium on Modelling in Fruit Research and Orchard Management (ISHS), AgWeatherNet/Washington State University
**Citation Count:** 미확인(Acta Horticulturae 학회논문집, 인용추적 어려움 — Cepeda et al. 2021이 이 논문을 재인용한 것으로 이미 확인된 바 있음)
**Status:** Iteration 8, Approved — **gdd(Tbase) 핵심 원 출처 확보 (재인용 함정의 최초 지점)**

---

## 8단계 정리

### 1. 데이터 수집 방법
미국 워싱턴주 동부 Yakima·Columbia valley 11개 지점, 2010~2013년 4개 생육시즌. 'Cripps Pink', 'Gala', 'Red Delicious' 3개 품종 대상, 만개(full bloom) 후 매주 2회 과실 50개의 적도직경(equatorial diameter)을 측정. 각 과원에서 가장 가까운 AgWeatherNet 자동기상관측소의 일별 기온 자료를 사용.

### 2. 표본
3개 품종 × 11개 지점 × 4개 생육시즌(2010~2013), 지점당 50개 과실.

### 3. 메커니즘
적산온도(GDD, `TT = Σ(Ti - Tb)`)로 생육의 물리적 시간(physiological time)을 표준화. **기준온도(Tb)는 Von Bertalanffy 통계모델(지수형 생장곡선, `dD/dt = a·k·e^(-kt)`)을 과실직경 실측 데이터에 커브핏(curve-fitting)하는 과정에서 모델 파라미터로 통계적으로 역산**(고정값을 가정하고 대입한 것이 아니라, 데이터로부터 추정한 값). 일별 직경 시뮬레이션은 오일러 적분법(Euler integration) 사용.

### 4. 정량적 결과 ⭐
- **기준온도(Tb) 도출값**: 'Cripps Pink' 7.22℃, 'Gala' 5.55℃, 'Red Delicious' 6.11℃ — **품종별로 다름**
- 모델 성능: RSME(직경 예측오차) 최소 0.015cm('Gala', East Wenatchee 2011) ~ 최대 0.118cm('Red Delicious', Konnowac Pass 2010), 전반적으로 상대오차 3% 미만
- 'Gala'가 요구온도가 가장 낮아 생장속도가 가장 빠르고 가장 먼저 수확됨. 'Cripps Pink'는 요구온도가 높아 가장 늦게 수확
- 세 품종 모두 지점·연도에 따라 최종 과실 크기 편차 존재('Red Delicious'·'Gala'가 'Cripps Pink'보다 유의하게 큼)

### 5. 산업 적용
AgWeatherNet 포털(www.weather.wsu.edu)에 프로토타입으로 구현되어, 관측소 인근 농가가 국지 기온만으로 과실 직경을 일 단위로 예측하도록 지원. 수확·수확후처리 물류 계획에 실용화.

### 6. 한계
①미국 워싱턴주(건조 대륙성 기후) 특정 3개 품종('Cripps Pink', 'Gala', 'Red Delicious') 한정 — 한국 주력 품종(후지·홍로)은 다루지 않음. ②대상 구간이 "**만개 후~수확**"의 **과실 직경(지름) 성장**이며, registry가 원래 기대한 "개화~수확 전체 생육기 GDD"와는 정확히 일치하지 않을 수 있음(같은 개념이지만 측정 대상이 좁음). ③품종별로 Tb가 5.55~7.22℃로 갈리는데, 이는 "사과 전체의 단일 Tb"가 존재하지 않고 **품종 특이적**이라는 것을 시사 — 후지/홍로에 그대로 대입 불가.

### 7. 구조적 문제 ⭐⭐
이전 라운드(Iteration 7)에서 Cepeda et al.(2021)이 이 논문의 Tb=7.22℃를 재인용해 사용한 것을 확인하고 "재인용 체인이라 독립 근거 아님"으로 기각한 바 있다. 이번에 원 논문(Chaves 2017)을 직접 확보한 결과, **이 값 자체는 재인용이 아니라 11개 지점·4개년·50과실/지점의 실측 데이터로부터 Von Bertalanffy 커브핏을 통해 직접 도출된 것**임이 확인됐다 — 즉 재인용 체인의 "막다른 끝"이 아니라 "진짜 원출처"에 도달한 것이다. 다만 이 값을 registry의 사과 gdd.Tbase에 그대로 "filled"로 채택하기에는 ①미국 특정 3품종 한정, ②한국 주력품종(후지/홍로) 미검증이라는 한계가 남아있다. **결론: gdd.Tbase는 "partial"로 격상 가능**(재인용 아닌 최초 실측 도출값 확보) — 단 "품종 특이적, 한국 품종 미검증"이라는 조건을 반드시 병기해야 함. Lee et al.(2023, 이번 배치의 다른 논문)이 만개~수확 기간의 온도-생육 관계를 다루므로, 두 논문을 결합해 후지/홍로용 Tb를 별도 추정하는 것이 다음 단계로 유망.

### 8. 새로운 Gap
후지·홍로 품종 대상 만개~수확 과실직경 성장의 Tbase 국내 실측(Von Bertalanffy 또는 유사 커브핏 방법). 미국 3개 품종 Tb(5.55~7.22℃)가 온대 계절형 기후에서도 유효한지 검증.

---

## Registry Delta

**Crop:** 사과
**Indicator:** gdd(적산온도, Tbase)
**Status:** missing → **partial로 격상**(재인용 아닌 최초 실측 도출값 확보, 그러나 한국 품종 미검증이라 filled는 아님)
**Value:** Tbase = 7.22℃('Cripps Pink'), 5.55℃('Gala'), 6.11℃('Red Delicious') — Von Bertalanffy 커브핏으로 워싱턴주 11지점×4개년 실측 데이터에서 직접 도출(재인용 아님). 모델 상대오차 <3%.
**Confidence:** 중(정식 심사 학회논문집, ISHS Acta Hortic., 그러나 미국 품종·건조 대륙성 기후 한정)
**Source:** Chaves, B. et al. (2017), Acta Hortic. 1160:335-340, DOI: 10.17660/ActaHortic.2017.1160.48
**Note:** ⚠️ Cepeda et al.(2021)이 이 값을 재인용했던 것과는 별개로, **이 원 논문 자체는 독립적 실측 도출**이다. 다만 후지·홍로 등 한국 주력 품종에 대한 값이 아니므로 "filled"로 올리려면 국내 품종 실측이 추가로 필요. Iteration 8의 최우선 후속 과제였던 "Chaves(2017) 원문 확보"가 이번에 해결됨.
