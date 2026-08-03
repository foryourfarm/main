# Cepeda, Vélez-Sánchez & Balaguera-López (2021) — Analysis of Growth and Physicochemical Changes of the Apple cv. Anna in a High Altitude Tropical Climate

**Source:** Revista Colombiana de Ciencias Hortícolas 15(2):e12508, DOI: 10.17584/rcch.2021v15i2.12508 (스페인어/영어 병기 제목)
**Citation Count:** 미확인(소규모 지역저널)
**Status:** Iteration 7, Approved (gdd 간접 참고, 콜롬비아 — Tbase 독립검증 아님, 재인용 주의)

---

## 8단계 정리

### 1. 데이터 수집 방법
콜롬비아 보야카(Boyacá)주 파이파(Paipa), 고도 2,525m 고산열대기후, '안나(Anna)'/MM.106 대목 사과나무 대상 만개 후 100일간(수확까지) 10일 간격 파괴적 표본채취(생중량·건중량·직경·색상·경도·적정산도(TTA)·호흡률 등 측정).

### 2. 표본
1개 품종('Anna')×1개 지역(파이파)×1개 시즌, 만개후 10일 간격 총 10회 표본점.

### 3. 메커니즘
과실 생장을 로지스틱(logistic) 모델로 적합(생중량·건중량·직경 모두 R²>0.99). 생장축은 달력일(DAA)이 아니라 **적산온도(GDD)**로 표준화 — 이때 사용한 공식은 `GDD = ((Tmax+Tmin)/2) - Tbase`, **Tbase=7.22℃를 Chaves et al.(2017)에서 그대로 인용**(원저자가 직접 도출한 값이 아니라 선행연구 값을 적용한 것).

### 4. 정량적 결과 ⭐
- 수확 시점: **만개후 100일 = 892.37 GDD**(Tbase 7.22℃ 기준)
- 생장단계 전환점(GDD): 세포분열기 종료 159.61 GDD, 급속 비대기 455.39~589.32 GDD, 성숙 전환 823.59 GDD
- 호흡률: 159.61 GDD에서 정점(61.93 mg CO2/kg/h) → 수확기(892.37 GDD)에 4.23까지 감소
- 경도: 455.39 GDD에서 정점(62.19N) → 수확기 38.38N까지 감소
- 적정산도(TTA): 319.79 GDD에서 정점(1.20%) → 수확기 0.71%까지 감소
- **색상지수(CI)**: 수확 시점에도 CI<0(여전히 녹색) — '안나' 품종이 이 고산열대 저위도 조건에서 착색 불량 문제를 가짐(저자는 Lancaster 1992를 인용해 "고온이 안토시아닌 생합성을 억제"한다며 착색 개선을 위해 수확전 서늘한 야간온도가 필요하다고 제언)

### 5. 산업 적용
로지스틱 생장모델(R²>0.99)이 GDD 기준으로 매우 잘 적합됨을 보여, "이 Tbase=7.22℃가 최소한 이 재배조건에서는 생장 예측에 유용하게 작동한다"는 간접적 정황을 제공. 다만 저자가 이 Tbase 자체를 검증한 것이 아니라 Chaves(2017)의 값을 그대로 가져와 적용했을 뿐.

### 6. 한계
콜롬비아 고산열대(2,525m, 저위도·연중 서늘) 기후 — 한국의 온대 계절형 기후와 근본적으로 다름. **Tbase=7.22℃는 이 논문의 독자적 검증치가 아니라 Chaves et al.(2017)의 재인용값**이므로, 이 논문만으로는 gdd.Tbase를 "filled" 또는 "partial(독립근거)"로 올릴 근거가 되지 못함. 1개 품종·1개 지역·1개 시즌 소규모 관찰연구.

### 7. 구조적 문제 ⭐⭐
registry의 사과 gdd(Tbase) 행은 여전히 missing 상태이며, 이 논문은 **그 공백을 직접 메우는 자료가 아니다** — Tbase 7.22℃ 값의 최초 출처는 Chaves et al.(2017, Acta Hortic. 1160:335-340, "Modeling fruit growth of apple")이고, 이번 7편 PDF 배치에는 **Chaves 원문 자체가 포함되지 않았다**. Cepeda(2021)는 그 값을 "적용"해 로지스틱모델을 잘 적합시켰다는 **간접적·정황적 뒷받침**만 제공한다. registry에 이 논문을 근거로 Tbase를 "확정"처럼 기술하면 명세 왜곡(CLAUDE.md §3-4 "추측 금지")이므로, **Chaves(2017) 원문을 직접 확보하기 전까지는 gdd.Tbase를 partial/missing 그대로 유지**해야 한다.
착색 관련해서는 Ryu et al.(2017, 이번 배치의 착색기 filled 논문)의 "고온이 안토시아닌 억제" 결론과 정확히 같은 방향(Lancaster 1992 인용)이라 — 별개 지역·품종에서 같은 기전이 재확인된다는 점에서 착색기 gap에 대한 **보조적 정성적 지지 증거**로만 병기 가능.

### 8. 새로운 Gap
Chaves et al.(2017) 원문 직접 확보(Tbase=7.22℃의 최초 도출 근거·표본·검증 방법 확인 필수). 한국 사과 재배지(온대 계절형)에서의 독자적 GDD Tbase 회귀분석.

---

## Registry Delta

**Crop:** 사과
**Indicator:** gdd(적산온도, Tbase)
**Status:** missing 유지(변화 없음) — 이 논문은 간접 정황 참고자료일 뿐, Tbase 자체의 독립 근거가 아님
**Value:** (신규 수치 없음) Chaves et al.(2017)의 Tbase=7.22℃를 재인용해 적용한 결과, 로지스틱 생장모델이 R²>0.99로 잘 적합됨을 확인(콜롬비아 고산열대, '안나' 품종) — Tbase 값 자체의 독립 검증은 아님.
**Confidence:** 낮음(Tbase는 재인용, 원저자 직접 도출 아님) / 한국 적용성 낮음(고산열대 vs 온대계절)
**Source:** Cepeda, D.F., Vélez-Sánchez, J.E., Balaguera-López, H.E. (2021), Rev. Colomb. Cienc. Hortic. 15(2):e12508
**Note:** ⚠️ 이 논문을 근거로 registry에 "Tbase=7.22℃ 확정"처럼 기술하면 안 됨 — 최초 출처인 Chaves et al.(2017, Acta Hortic. 1160:335-340)를 직접 확보해 검증해야 함(Iteration 8 최우선 후보로 등록). 착색 관련 서술(고온→착색억제, Lancaster 1992 인용)은 Ryu(2017)의 착색기 filled 결론과 방향이 일치해 보조 정성적 지지로만 병기.
