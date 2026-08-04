# Zanotelli, Montagnani, Andreotti & Tagliavini (2019) — Evapotranspiration and Crop Coefficient Patterns of an Apple Orchard in a Sub-Humid Environment

**Source:** Agricultural Water Management 226:105756, DOI: 10.1016/j.agwat.2019.105756 (오픈액세스)
**Citation Count:** 54
**Status:** Iteration 7, Approved (rainfall_by_stage 보강, 해외/이탈리아 — mm 절대구간 아닌 Kc 계수 형태)

---

## 8단계 정리

### 1. 데이터 수집 방법
이탈리아 남티롤(Alto Adige, 아디제강 유역, 224m 고도) 유기재배 사과원('Fuji'/M9, 2000년 식재, 3×1m 밀식), 2013~2015년(3개년) 에디covariance(eddy covariance) 타워로 실제증발산량(ETa) 직접 측정. FAO56 Penman-Monteith식으로 기준증발산량(ETo) 계산, 실험적 작물계수(Kcexp = ETa/ETo) 도출.

### 2. 표본
3개년(2013~2015) 연속 측정, 생육기(3~10월, DOY 60~304) 매일 단위 ETa/ETo. FAO56 4단계 생육기 구분(초기/전개/성숙/후기) 적용.

### 3. 메커니즘
Kc는 계절에 따라 종모양(bell-shaped) 곡선을 그리며, FAO 표준표(Kc_mid=1.20)보다 실측값이 낮게 나옴(과수 캔버스가 짧은 잔디 기준면보다 대기와 더 밀착 결합돼 있어 증발수요 반응이 다름, Jarvis 이론). Kc 잔차(Kcexp - 평균Kc)는 대기 수증기압부족(VPD)과 양의 상관 — 건조할수록(VPD↑) 실제 물 수요가 표준보다 더 높아짐.

### 4. 정량적 결과 ⭐
**생육단계별 실측 Kc(Table 2, 3개년 평균)**:
| 생육단계 | DOY 구간 | Kc(FAO표준) | Kc(현지보정) | **Kc(실측, K̄cexp)** |
|---|---|---|---|---|
| 초기(Kc_ini, 발아~착과) | 60~99 | 0.50 | 0.50 | **0.657±0.021** |
| 전개(Kc_dev, 엽전개) | 100~165 | (선형식) | (선형식) | (선형식) |
| **성숙(Kc_mid, 최대엽면적)** | 166~258 | 1.20 | 1.183±0.011 | **1.013±0.008**(FAO의 85%) |
| 후기(Kc_end, 낙엽전) | 259~304 | 0.95 | 0.799±0.014 | **0.835±0.022** |

- 생육기(3~10월) 총 ETo: **762, 735, 788 mm**(2013~2015) / 총 ETa(보정후): **764, 683, 745 mm**
- 일평균 ETa **2.7~2.9 mm/day**, 7월 최대 **6.3~6.8 mm/day**
- VPD<0.5kPa일 때 Kc **0.91**, VPD 0.5~1.5kPa일 때 Kc **1.01~1.02**, VPD>1.5kPa일 때 Kc **1.12**(다중회귀에서 VPD가 잔차 변동의 78% 설명, 전천radiation 16%, 풍속6%)

### 5. 산업 적용
과수 실제 물 수요는 FAO 표준표보다 15%(성숙기) 낮으므로, 표준표를 그대로 쓰면 관수량을 과다 산정할 위험. VPD 기반 일별 보정이 관수 효율화에 유용.

### 6. 한계
이탈리아 아디제강 유역(sub-humid, 연간 강수 573~1277mm, 관개병행) 자료 — 한국 몬순기후(여름 집중강우)와 강수 패턴이 다름. **mm 단위 절대 강수량이 아니라 "Kc 계수"** 형태라, registry가 요구하는 "생육단계별 mm 최적구간"으로 바로 대입 못함(로컬 ETo 자료가 있어야 Kc×ETo로 mm 환산 가능). 관수 실험(자연강우+관개 병행)이라 순수 강수량 기준이 아님.

### 7. 구조적 문제
registry의 사과 rainfall_by_stage(Ru et al. 2025, 중국모델, 개화-결실120mm/과실팽창319mm/성숙113mm)와 **형태 자체가 다르다** — Ru는 "총량 mm", Zanotelli는 "Kc 계수(ETo에 곱해야 mm가 나옴)". 다만 Zanotelli는 **3년 에디covariance 직접측정**(간접 추정 아님)이라 방법론적 신뢰도가 매우 높고, "FAO 표준표를 그대로 쓰면 15% 과다산정"이라는 정량적 경고는 어느 나라에나 적용 가능한 일반적 시사점. 한국형 rainfall_by_stage를 새로 만들 때 이런 Kc 기반 방법론을 참고할 가치가 있음(단, 이탈리아 수치 자체를 한국에 그대로 이식하면 안 됨).

### 8. 새로운 Gap
한국 사과원의 에디covariance 또는 실측 기반 Kc 곡선(현재 한국은 이런 직접측정 자료가 없음 — 중국모델(Ru 2025)에만 의존). 한국 몬순기후에서 Kc-VPD 관계가 이탈리아 사례와 같은 방향인지 검증.

---

## Registry Delta

**Crop:** 사과
**Indicator:** rainfall_by_stage (**신규 방법론**, mm 절대구간 아닌 Kc 계수)
**Status:** partial (직접 mm 환산 불가, 방법론적 참고자료)
**Value:** 생육단계별 실측 Kc — 초기 0.657, 성숙기 1.013(FAO표준의 85%), 후기 0.835. 생육기 ETo 735~788mm/년, ETa 683~764mm/년. VPD가 Kc 일별변동의 78% 설명(VPD↑→Kc↑).
**Confidence:** 높음(인용54, 3년 에디covariance 직접측정, 오픈액세스) / 한국 적용성은 낮음(이탈리아 sub-humid 기후, 몬순 아님)
**Source:** Zanotelli, D., Montagnani, L., Andreotti, C., Tagliavini, M. (2019), Agric. Water Manag. 226:105756
**Note:** Ru et al.(2025, 중국모델)과 단위체계가 달라(Kc계수 vs mm총량) 직접 대체 불가. "FAO 표준표가 실제보다 15~30% 높게 잡힐 수 있다"는 방법론적 경고는 한국형 rainfall_by_stage 재검증 시 참고할 가치 있음.
