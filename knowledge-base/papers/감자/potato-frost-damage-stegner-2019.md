# Stegner et al. (2019) — Potato Leaf Freezing by Infrared Thermography

**Source:** Primary Experimental, PMC6914373  
**Citation Count:** 중간~높음  
**Status:** Iteration 3-a, Approved

---

## 8단계 정리

### 1. 데이터 수집 방법
Infrared Differential Thermal Analysis (IDTA) + DTA  
냉각율 3 K/h to -3°C  
잎 시료 (S. tuberosum var. Agria Bio)

### 2. 표본
- DTA: 10회 (단일 잎)
- IDTA: 3회
- 얼음 유도 감수성: N=6 (접종), N=14 (과냉각)
- 현장: 5월-8월 2018 채수

### 3. 메커니즘
첫 얼음핵형성(-2.3°C) → 60초 내 잎 전체 결빙(비치명적)  
10-78분 후 diffuse freezing(치명적) → 세포 침윤, 조직 변색

### 4. 정량적 결과 ⭐

| 지표 | 수치 |
|------|------|
| 잎 냉해 임계 | -3°C (완전 냉해) |
| 얼음핵형성 | -2.3±0.4°C |
| 현장 빙핵 범위 | -0.5~-3.0°C |
| 첫 exotherm | 2.5K 이상, ~20분 지속 |

### 5. 산업 적용
- 제상 스프링클러 임계(-2.5°C 이하)
- 야간 기온 경보(Agria 기준 -3°C)
- 생육기 늦서리 대응

### 6. 한계
- 단일 품종 Agria Bio (다품종 비교 미흡)
- 실험실 정밀 냉각(현장 자연 냉각과 차이)
- **잎만 측정(괴경/뿌리 냉해 미정)**

### 7. 구조적 문제
정상 (SE 0.4°C 명확, IR thermography 신뢰도 높음)

### 8. 새로운 Gap
- 다품종 냉해 임계 스펙트럼
- **괴경 냉해 임계(현장 튜버 생존 온도)** ← 중요
- 토양 온도 vs 엽온 괴리

---

## Registry Delta

**Crop:** 감자  
**Indicator:** temp_min_frost_damage_leaf  
**Status:** filled  
**Value:** -3°C (S. tuberosum 잎 냉해) | Ice nucleation -2.3±0.4°C  
**Confidence:** 높음 (SE 0.4°C, IR thermography, 18회 DTA/IDTA)  
**Source:** Stegner et al. 2019  
**Method:** Infrared thermography (ThermaCAM S60) + DTA
