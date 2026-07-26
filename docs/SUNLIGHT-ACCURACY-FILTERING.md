# 일조시간 정확도 필터링 및 FE 표시 규칙

> 기준일: 2026-07-26
> 상태: 구현 완료 (DB 환경 필요)
> 범위: 계산값 신뢰도 기반 포함/제외 + FE 표시 방법

---

## 1. 정확도 기준 (§3)

**일조시간은 confidence >= 0.90인 경우만 적합도 계산에 포함된다.**

### 1.1 포함 기준

| 방식 | 신뢰도 | 포함 | 비고 |
|------|--------|------|------|
| 실측 ASOS | 0.95 | ✅ | 105개 관측소 실측 평년값 |
| Angstrom + 보정 | 0.76~0.87 | ❌ | 신뢰도 미달(< 0.90) |
| Angstrom 기본 | 0.70 | ❌ | 신뢰도 미달 |

### 1.2 미달 시 처리

정확도 < 0.90인 계산값은:
1. **자동 제외**: `climatology_service._add_sunlight_to_climatology()`에서 필터링
2. **결과**: `gather_indicator_values()`에 `None` 전달 → `calculate_suitability()`에서 누락
3. **FE 영향**: 다른 기상 지표만으로 적합도 판정 (sunlight 항목 자체가 breakdown에 없음)

---

## 2. 실장 위치

### 2.1 Backend Code Changes

**파일**: `backend/app/services/`

| 파일 | 변경 | 효과 |
|------|------|------|
| `sunlight_calculation.py` | `SunlightResult` dataclass에 `is_calculated: bool` 필드 추가 | 계산값 vs 실측 구분 |
| `climatology_service.py` | `_add_sunlight_to_climatology()`에서 `confidence >= 0.90` 필터 추가 | 미달 신뢰도 자동 제외 |
| `suitability_service.py` | `compute_farm_suitability()`에서 breakdown의 sunlight 항목에 method/is_calculated/confidence 추가 | FE에 메타데이터 전달 |

### 2.2 코드 흐름

```
load_climatology()
  └─ _add_sunlight_to_climatology()
       ├─ 실측값 (confidence=0.95) → 항상 포함
       ├─ 계산값 → confidence >= 0.90 필터링
       └─ 미달 → None (포함 안 함)

gather_indicator_values()
  └─ sunlight_by_month.get(month)?.value → None이면 제외

calculate_suitability()
  └─ sunlight 값이 None → breakdown에서 "missing" 상태

compute_farm_suitability()
  └─ breakdown["sunlight"] 메타데이터 추가
       ├─ method: "measurement" | "angstrom_only" | "angstrom_corrected"
       ├─ is_calculated: false | true
       └─ confidence: 0.0~1.0 (계산값만)
```

---

## 3. FE 표시 규칙

### 3.1 Breakdown 응답 형식

```json
{
  "sunlight": {
    "value": 8.2,
    "score": 72.0,
    "weight": 0.15,
    "status": "allowed",
    "method": "angstrom_corrected",
    "is_calculated": true,
    "confidence": 0.82
  }
}
```

### 3.2 표시 로직 (FE 개발자용)

```typescript
// sunlight 항목이 있으면 (confidence >= 0.90인 것만)
if (breakdown.sunlight) {
  const { value, is_calculated, confidence, method } = breakdown.sunlight;
  
  // 기본 표시
  showValue(value);  // 예: 8.2시간
  
  // 계산값 판정
  if (is_calculated) {
    // 작은 텍스트로 출처 표시
    showSmallText(`계산값 (${method}, 신뢰도: ${(confidence*100).toFixed(0)}%)`);
    // 예: "계산값 (angstrom_corrected, 신뢰도: 82%)"
  }
  // 실측값이면 (is_calculated=false) → 별도 표시 없음
}

// sunlight 항목이 없으면 (confidence < 0.90)
// → 다른 지표만으로 적합도 판정, 별도 알림 불필요
```

### 3.3 UI/UX 가이드

**계산값 표시 위치:**
- 지표값 바로 아래 또는 옆에 작은 텍스트 (폰트 크기 85~90%)
- 색상: 회색 또는 보조 색상
- 라벨: "계산값 (신뢰도: XX%)"

**예시:**
```
일조시간: 8.2시간
  계산값 (신뢰도: 82%)  ← 작은 텍스트
```

**실측값:**
```
일조시간: 5.4시간
  (별도 표시 없음)
```

---

## 4. 미달 시나리오 (confidence < 0.90)

현재 구현에서 정확도 미달인 경우:

### 4.1 자동 제외 (현재 동작)
- 계산값 신뢰도가 0.90 미만 → sunlight 항목 자체가 response에 없음
- FE는 토양(pH, EC, 유효인산, 유기물)과 기온/강수만으로 판정

### 4.2 향후 개선 (선택사항)
만약 "제외 시 정확도가 더 낮으면 포함" 로직을 추가하려면:
1. FE에서 두 가지 시나리오 점수 수신 (포함/미포함)
2. FE 판단 로직: 포함 시 점수 vs 미포함 시 점수 비교
3. 더 높은 쪽 선택

현재는 백엔드가 이미 최적을 판단하므로(신뢰도 0.90 기준) 이 로직이 불필요합니다.

---

## 5. 테스트 결과

### 5.1 정확도 필터링 검증

```
✅ 실측 (0.95): 포함 (기대: 포함)
✅ Angstrom (0.70): 제외 (기대: 제외)
✅ Angstrom+보정 (0.78): 제외 (기대: 제외)
```

### 5.2 메타데이터 추가 검증

```
SunlightResult.is_calculated:
  - measurement: False (실측값)
  - angstrom_*: True (계산값)

breakdown["sunlight"]["method"]:
  - "measurement" (실측)
  - "angstrom_only" (기본 계산)
  - "angstrom_corrected" (보정 계산)
```

---

## 6. 문서 링크

- `docs/long-term-tab-api.md` §3.1 — breakdown 구조
- `docs/long-term-tab-api.md` §5.1 — 일조시간 계산 방식
- `CLAUDE.md` §3 — AI 협업 규칙 (결정론 우선 등)
- `PRD.md` §8 — 일조시간 데이터 전략

---

## 7. 남은 작업

- [ ] PostgreSQL DB 환경 설정 후 마이그레이션 실행
- [ ] 적합도 계산 엔드포인트 테스트 (`GET /api/v1/farms/{farm_id}/suitability`)
- [ ] FE에서 breakdown 응답 파싱 및 메타데이터 표시 구현
- [ ] E2E 테스트: 여러 지역/월에 대해 포함/제외 시나리오 검증
