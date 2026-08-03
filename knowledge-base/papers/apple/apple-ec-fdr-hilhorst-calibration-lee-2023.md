# 이재범·김종윤(2023) — FDR 센서를 이용한 사과원 토양 실시간 EC 측정을 위한 Hilhorst 모델의 보정 (Modification of Hilhorst Model for Real-time EC Measurement of Apple Orchard Soil using FDR Sensors)

**Source:** 한국원예학회 학술발표요지, Hortic. Sci. Technol. 41(Suppl II), October 2023, p.323 (P-5 포스터 세션)
**Citation Count:** 확인 불가 (학회 발표요지, 국제 인용지수 미색인)
**Status:** Iteration 6, Approved (reference_only, 원문 확보 완료)

---

## 8단계 정리

### 1. 데이터 수집 방법
FDR 센서(TEROS 12, METER Group)로 토양 bulk EC(σb)를 실시간 측정. NaCl 표준용액 5단계(EC 0, 1, 2, 4, 8 dS/m)를 조제해 각 EC 반응을 3회 반복 측정. 25℃ 조건에서 FDR 센서로 σb를 측정하고(⚠️ 정확한 측정 시간 단위는 PDF 폰트 인코딩 손실로 불확실), 30분 경과 후 안정화된 σb 값을 기록해 σb=0(포화·무수분 기준점)을 추정했다.

### 2. 표본
5단계 EC 농도 × 3반복.

### 3. 메커니즘
FDR 센서의 bulk EC(σb)는 토양수분함량에 의존하므로, σb=0(수분 0 지점의 절편값)을 별도로 추정해 보정하면 Hilhorst 모델을 통해 토양 공극수 EC(pore water EC, σp)를 더 안정적으로 추정할 수 있다. 이 σp는 한국의 관행적인 1:5 물추출법 EC와 관계식으로 환산 가능하다.

### 4. 정량적 결과 ⭐
- σb=0 추정치를 두 가지 방법으로 비교 — 한 방법은 **3.55**, 다른 방법(실측기반)은 **4.1**로 추정됨(⚠️ 두 값의 정확한 산출 방법·단위는 폰트 손실로 불확실 — 원문 재확인 필요).
- Hilhorst 모델로 σp를 추정했을 때, σb=0 보정을 쓰지 않으면 RMSE **2.49**, σb=0 보정을 사용하면 RMSE **1.52**로 개선.
- σp와 관행 1:5 물추출법 EC 간 관계식의 RMSE = **0.20**(양호한 적합) — FDR 센서로 관행적 EC(1:5)를 추정할 수 있음을 확인.

### 5. 산업 적용
FDR 센서 기반 실시간 EC 모니터링 값을 관행적인 1:5 물추출법 EC 값으로 환산해, 기존 토양검정 기준(예: RDA 사과 EC 적정범위 0.8~1.5 dS/m)과 직접 비교 가능하게 만드는 실용적 캘리브레이션을 제공한다.

### 6. 한계
학회 발표요지(1페이지 초록)라 정식 논문 대비 방법론 서술이 소략하다. **PDF 폰트 인코딩(Adobe-Korea1 CMap 누락) 문제로 σ 기호 및 일부 조사·수치 단위가 텍스트 추출 과정에서 손실됐다 — σb=0 추정치(3.55 vs 4.1)의 정확한 의미와 산출법은 원문(포스터/전문) 재확인이 필요하다.** 실험이 표준 NaCl 용액 기준이라 실제 사과원 토양(유기물·질감 등 매트릭스 효과)에서의 재현성은 별도 검증이 필요하다.

### 7. 구조적 문제
이 논문은 registry에 이미 기록된 "사과 EC 측정법(1:5 물추출법 vs 국제표준 ECe 단위 다름, 환산계수 필요)" 이슈에 정확히 대응하는 방법론 자료다. 다만 **optimal_range(적정 EC 수치) 자체를 제공하는 논문이 아니므로, 상추 `lettuce-ec-conversion-factor-lee-2003.md`(reference_only)와 동일하게 취급해야 한다** — 사과 ec의 optimal_min/max(0.8~1.5)를 이 논문 근거로 바꾸면 안 된다.

### 8. 새로운 Gap
σb=0 추정법 2가지(3.55 vs 4.1)의 정확한 차이와 실제 사과원 현장 적용 시 어느 쪽이 더 적합한지 원문 재확인 필요. FDR센서 실측 EC와 1:5 물추출법 EC의 실제 사과원 현장(표준용액이 아닌) 대조 데이터.

---

## Registry Delta

**Crop:** 사과
**Indicator:** ec (측정법, **reference_only**)
**Status:** filled (방법론, 원문 확보 완료) — optimal_range 값 출처 아님
**Value:** FDR센서(TEROS12) bulk EC → σb=0 보정 → Hilhorst 모델 pore water EC(σp) 추정 RMSE 2.49(미보정) → 1.52(보정후) 개선. σp↔1:5 물추출법 EC 관계식 RMSE=0.20.
**Confidence:** 중 (학회발표요지 1p, 인용수 확인불가, 폰트손실로 일부 수치 불확실 — ⚠️ σb=0 값 3.55/4.1은 재확인 필요)
**Source:** 이재범, 김종윤(2023), 한국원예학회 학술발표요지, Hortic. Sci. Technol. 41(Suppl II), p.323
**Note:** optimal_range(0.8~1.5 dS/m) 값의 출처로 쓰면 안 됨. `papers/lettuce/lettuce-ec-conversion-factor-lee-2003.md`와 동일 패턴(reference_only, 측정법 검증용).
