# 자동 도메인 지식 수집 루프 — 아키텍처 & 오케스트레이터 지침

> **이 문서는 세 가지 역할을 합니다:**
> 1. 오케스트레이터 지침 (main loop 절차)
> 2. 전체 시스템 아키텍처 설명
> 3. 각 에이전트의 가벼운 참고 지침

---

## 1. 시스템 개요

**목표:** 농업 도메인 지식(작물별 생육 기준, 토양 기준)을 자동으로 수집하고 registry.md에 체계적으로 기록

**4-에이전트 구조:**
```
scout (논문 검색)
  ↓
conflict-checker (후보 검증)
  ↓
extractor (원문 읽기 & 정리)
  ↓
registry-keeper (상태 파일 갱신)
  ↓
ORCHESTRATOR (정지 조건 확인)
```

**데이터 흐름:**
```
keyword-queue.md (우선순위 키워드)
  ↓
[scout → conflict-checker → extractor → registry-keeper] × N cycles
  ↓
registry.md (최종 상태)
search-log.md (시도 기록)
papers/ (정리본 파일들)
```

---

## 2. 4-에이전트 아키텍처

```
┌──────────────────────────────────────────────────────────┐
│             ORCHESTRATOR (메인 루프)                      │
│   역할: 상태 파일 읽기, 서브에이전트 호출 조율             │
│   정지 조건 판정, 진행 상황 보고                          │
└──────────────────────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┬────────────────┐
        │               │               │                │
        ▼               ▼               ▼                ▼
   ┌─────────┐    ┌──────────┐    ┌─────────┐     ┌──────────────┐
   │ scout   │    │conflict- │    │extractor│     │registry-     │
   │         │───→│checker   │───→│         │────→│keeper        │
   │         │    │          │    │         │     │              │
   └─────────┘    └──────────┘    └─────────┘     └──────────────┘
     검색 3~5편    검증(승인/      원문 읽기 &    registry.md
     (메타만)     주의/거절)       8단계 정리      갱신
```

**상태 파일 (ORCHESTRATOR가 관리):**
```
knowledge-base/
├── registry.md              ← 핵심 상태 (crop_growth_guide, soil_change_rule)
├── keyword-queue.md         ← 다음에 검색할 키워드 우선순위
├── search-log.md            ← 이미 시도한 검색어 + 결과
└── papers/
    ├── apple/
    │   ├── hongro-2009.md
    │   └── ...
    └── pear/
        └── ...
```

---

## 3. 한 사이클(iteration)의 흐름

### 🔄 반복 절차

```
while iteration < max_iterations:
    iteration += 1
    
    # 사용자 중단 확인
    if "멈춰" in 최근_메시지:
        break
    
    # 1. SCOUT 호출
    keyword = keyword-queue.md의 최상단 키워드
    scout_result = scout(keyword, already_seen=search-log.md)
    
    if scout_result.no_result:
        keyword-queue.md에서 제거
        continue
    
    # 2. CONFLICT-CHECKER 호출
    checker_result = conflict_checker(
        candidates=scout_result.candidates,
        existing_papers=registry.md에서 관련 부분
    )
    
    approved = [c for c in checker_result.validation_results if c.status == "approve"]
    caution = [c for c in checker_result.validation_results if c.status == "caution"]
    
    # 3. EXTRACTOR 호출 (병렬 가능)
    deltas = []
    for paper in approved + caution:
        delta = extractor(
            paper_metadata=paper,
            caution_note=paper.extractor_instruction if paper.status == "caution" else None
        )
        deltas.append(delta)
    
    # 4. REGISTRY-KEEPER 호출
    keeper_result = registry_keeper(
        deltas=deltas,
        searched_queries=scout_result.searched_queries
    )
    
    # 5. 정지 조건 확인
    if keeper_result.stop_recommended:
        break
    
    # 6. 간단히 보고
    print(f"[{iteration}/{max_iterations}] "
          f"+{len(deltas)}편 처리, "
          f"filled: {keeper_result.newly_filled}")

# 루프 종료 후 최종 요약 보고
```

---

## 4. 에이전트별 책임

### 🔍 SCOUT (논문 검색)

**입력:**
- `gap_keyword`: 검색 대상 키워드 (예: "사과 EC 적정범위")
- `already_seen`: search-log.md의 관련 부분 (중복 검색 방지)

**역할:**
- 한국/영어 모두 Aira MCP로 검색
- 중국 논문 절대 제외
- 인용수 10회 이상만 수용 (최근 1년은 5회 이상)
- 관련성 높은 3~5편만 반환

**출력:**
```yaml
candidates:
  - title: "..."
    citationCount: 45  # 신뢰도 근거
    doi: "..."
    abstract: "..."
    relevance_note: "..."
    fetch_hint: "DOI 접근 가능" | "학위논문" | "..."
```

**핵심 기준:**
- 인용수 낮음 → 제외 (신뢰도 부족)
- 중국 논문 → 제외
- 관련성 낮음 → 제외

---

### ✅ CONFLICT-CHECKER (후보 검증)

**입력:**
- `candidates`: scout에서 받은 논문들
- `existing_papers_summary`: registry.md의 기존 기준값들

**역할:**
- 기존 데이터와 명백한 모순 감지
- 인용수 기반 신뢰도 평가
- 온도/화학성/단위 충돌 검사

**출력:**
```yaml
validation_results:
  - status: "approve" | "caution" | "reject"
    citationCount_verdict: "높음" | "중간" | "낮음"
    conflict_notes: "..."
    extractor_instruction: "원문 읽을 때 주의할 점"
```

**판정 기준:**
- ✅ **approve**: 기존과 일관성 + 인용수 충분 (10+)
- ⚠️ **caution**: 약간 불명확하지만 참고 가치 있음 + 인용수 미흡
- ❌ **reject**: 명백한 모순 또는 인용수 부족 (< 10, 예외 제외)

---

### 📄 EXTRACTOR (원문 읽기 & 정리)

**입력:**
- `paper_metadata`: conflict-checker 결과 중 1편
- `caution_note`: conflict-checker 주의사항

**역할:**
- 원문 읽기 (paywall 접근 불가면 abstract로만)
- **8단계 템플릿**으로 정리:
  1. 데이터 수집 (표본수, 방법)
  2. 전처리 (이상치)
  3. 로직 (분석 방식)
  4. 결과 (핵심 수치)
  5. 활용방안 (registry 연결)
  6. 보완 (한계)
  7. 구조적 이슈 (발견된 문제)
  8. 새로운 gap (다음 검색 키워드)
- 파일 저장: `knowledge-base/papers/<crop>/<slug>.md`
- delta 반환 (registry 갱신용)

**출력:**
```yaml
status: "done" | "blocked_paywall"
saved_path: "knowledge-base/papers/apple/..."
coverage_delta:
  - crop: "사과"
    indicator: "EC"
    optimal_range: "0.8~1.5 dS/m"
    new_status: "filled"
    note: "..."
new_gap_keywords:
  - keyword: "사과 대목별 EC 민감도"
    priority: "P1"
```

---

### 📋 REGISTRY-KEEPER (상태 갱신)

**입력:**
- `deltas`: extractor들이 반환한 delta 리스트
- `searched_queries`: scout가 사용한 검색어

**역할:**
- registry.md 업데이트 (crop_growth_guide, soil_change_rule)
- search-log.md에 이번 사이클 기록
- keyword-queue.md 갱신 (새 gap 우선순위 정렬)

**출력:**
```yaml
newly_filled: ["crop_growth_guide.EC (사과)", ...]
newly_partial: ["crop_growth_guide.Organic (사과)"]
still_missing_high_priority: ["crop_growth_guide.temp_day (사과)", ...]
stop_recommended: false | true
```

**책임:**
- 중복 source 제거
- status 전이 규칙 적용 (missing → partial → filled)
- 새 gap을 우선순위 순으로 정렬
- 모든 파일 기록 일관성 유지

---

## 5. 상태 파일 관리

### registry.md (핵심)

**구조:**
```markdown
# Table 1: crop_growth_guide
| Crop | Indicator | Optimal Range | Status | Sources |
|------|-----------|---------------|--------|---------|
| 사과 | pH | 6.0~6.5 | filled | [rda-2023, hongro-2009] |
| 사과 | EC | 0.8~1.5 dS/m | filled | [hongro-2009, sod-2009] |
| 사과 | temp_day | ? | missing | [] |

# Table 2: soil_change_rule
| Rule | Crop | Trigger | Effect | Status |
|------|------|---------|--------|--------|
| EC_quality | 사과 | EC > 1.6 | 착색 저하 | filled |

# Table 3: 알려진 구조적 이슈
| Issue | Status | Context |
|-------|--------|---------|
| EC 측정법 표준화 | Open | 1:5 vs ECe 환산 필요 |

# Table 4: 메타정보
**갱신 날짜:** 2026-07-25
**커버리지:** filled 12 / partial 5 / missing 13 (56.7%)
```

**갱신 규칙:**
- status: missing → partial → filled (상향만)
- sources: 중복 제외하고 추가
- unit: 명시적으로 기재
- note: 측정법/한계 기록

### keyword-queue.md

**구조:**
```markdown
## P0 (즉시 필요)
1. 사과 야간 최저기온 냉해 임계값
2. 사과 생육단계별 낮 온도

## P1 (보충 필요)
1. 사과 대목별 EC 민감도
2. 배 화학성 기본 기준

## P2 (참고)
1. EC 측정법 환산계수
```

**갱신 규칙:**
- extractor의 new_gap_keywords를 모두 수집
- 우선순위 (P0 > P1 > P2) 순 정렬
- 중복 제거 (같은 키워드 이미 있으면 제외)

### search-log.md

**구조:**
```markdown
## Cycle 1 — 2026-07-25

### 검색어
- "사과 EC 적정범위" (Aira)
- "apple soil EC optimal" (Aira)

### 결과
- 발견: 8편
- scout 통과: 6편
- 승인: 3편
- 처리됨: 3편 ✅

### 메모
- Korean coverage: good
```

**갱신 규칙:**
- 매 사이클 새 섹션 추가
- 최신 사이클이 맨 위
- 발견/채택 논문 수 기록

---

## 6. 정지 조건

**ORCHESTRATOR가 매 반복 후 체크:**

```
1️⃣ 사용자가 "멈춰" 말함?
   → YES: 즉시 중단, 현황 요약 보고

2️⃣ registry.md 커버리지 충분?
   (5작물 × 6지표 중 90% 이상 filled/partial?)
   → YES: "목표 달성" 보고, 종료

3️⃣ 이번 사이클에서 신규 논문 0편?
   (deltas 길이 == 0?)
   → YES: "더 이상 찾을 논문 없음" 보고, 종료

4️⃣ max_iterations 도달?
   (기본 15회, 사용자 지정 가능)
   → YES: "최대 반복 도달" 보고, 종료

5️⃣ 모두 아니면?
   → 다음 반복으로 (Step 1 scout 호출)
```

**중단 시 최종 보고:**
```
이 사이클은 XX번 반복했습니다.

✅ 새로 filled: crop_growth_guide.EC (사과), ...
⚠️ 새로 partial: crop_growth_guide.Organic (사과)
❌ 여전히 missing: crop_growth_guide.temp_day (사과), ...

[구조적 이슈가 있으면 함께 보고]
```

---

## 7. 오케스트레이터 절차 (research-loop 기반)

### 사전 설정

```python
# 초기 변수
iteration = 0
max_iterations = 15  # 사용자 지정 가능
deltas = []
```

### 메인 루프

```
# 시작 전
read knowledge-base/registry.md (상태만 파악)
read knowledge-base/keyword-queue.md

while iteration < max_iterations:
    iteration += 1
    
    # [매 반복마다] 사용자 중단 확인
    if "멈춰" in 최근_메시지:
        # "중단 처리" 절차로 이동
        break
    
    # Step 1: keyword 결정
    keyword = keyword-queue.md의 최상단
    if keyword가 없으면:
        사용자에게 보고("모든 키워드 소진")
        break
    
    # Step 2: SCOUT 호출
    scout_result = Task(agent="scout", prompt=f"""
        gap_keyword: {keyword}
        already_seen: <search-log.md에서 관련 부분만 발췌>
    """)
    
    # [매 Task 후] 사용자 중단 확인
    if "멈춰" in 최근_메시지:
        break
    
    if scout_result.no_result:
        keyword-queue.md에서 {keyword} 제거
        search-log.md에 "결과없음" 기록
        continue  # 다음 반복
    
    # Step 3: CONFLICT-CHECKER 호출
    checker_result = Task(agent="conflict-checker", prompt=f"""
        candidates: {scout_result.candidates}
        existing_papers_summary: <registry.md 관련 행 발췌>
    """)
    
    if "멈춰" in 최근_메시지:
        break
    
    # Step 4: EXTRACTOR 호출 (병렬 가능)
    approved_caution = [c for c in checker_result.validation_results 
                        if c.status in ["approve", "caution"]]
    
    deltas = []
    for candidate in approved_caution:
        delta = Task(agent="extractor", prompt=f"""
            paper_metadata: {candidate}
            caution_note: {candidate.extractor_instruction if candidate.status == "caution"}
        """)
        deltas.append(delta)
        
        if "멈춰" in 최근_메시지:
            break  # 이미 시작한 extractor는 완료, 다음은 스킵
    
    if "멈춰" in 최근_메시지:
        break
    
    # Step 5: REGISTRY-KEEPER 호출
    if len(deltas) > 0:
        keeper_result = Task(agent="registry-keeper", prompt=f"""
            deltas: {deltas}
            searched_queries: {scout_result.searched_queries}
        """)
    else:
        continue  # 처리할 논문 없으면 다음 반복
    
    if "멈춰" in 최근_메시지:
        break
    
    # Step 6: 정지 조건 확인
    if keeper_result.stop_recommended:
        사용자에게 보고(keeper_result.stop_reason)
        break
    
    # Step 7: 진행 상황 간단히 보고
    print(f"[{iteration}/{max_iterations}] "
          f"+{len(deltas)}편 처리, "
          f"신규 filled: {keeper_result.newly_filled}")

# 루프 종료 후
사용자에게 최종 요약 보고
```

### 중단 처리 ("멈춰")

```
if 사용자가 "멈춰" 명령했으면:
    # 현재 반환받은 결과까지는 정상 처리
    # (예: registry-keeper가 이미 응답했으면 반영)
    
    # 다음 단계는 시작하지 않음
    
    # 지금까지의 진행 요약 보고:
    print(f"사용자 요청으로 루프를 중단했습니다.")
    print(f"처리된 사이클: {iteration}회")
    print(f"신규 filled: {모든 keeper_result의 newly_filled}")
    print(f"여전히 missing: {최종 registry.md의 missing 상태}")
    
    break
```

---

## 8. 빠른 참고 (각 에이전트용)

### SCOUT를 호출하는 사람
```
입력: gap_keyword (예: "사과 EC 적정범위")
반환: candidates (3~5편, citationCount 포함)
핵심: 중국 논문 제외, 인용수 10+ 기준
```

### CONFLICT-CHECKER를 호출하는 사람
```
입력: candidates (scout에서 받은 것)
반환: status (approve/caution/reject)
핵심: 인용수 낮으면 거절, 명백한 모순 거절
```

### EXTRACTOR를 호출하는 사람
```
입력: paper_metadata (conflict-checker 승인된 것)
반환: delta (8단계 정리본 경로 + 구조화된 정보)
핵심: 8단계 필수, 원문 미접근 시 blocked_paywall 표기
```

### REGISTRY-KEEPER를 호출하는 사람
```
입력: deltas (extractor들이 반환한 것)
반환: keeper_result (새로운 gap, 정지 권장 여부)
핵심: 중복 제거, status 전이 규칙 적용, 파일 갱신
```

---

## 9. 설계 원칙

| 원칙 | 설명 |
|------|------|
| **컨텍스트 최소화** | ORCHESTRATOR는 registry.md + keyword-queue.md만 읽음 |
| **에이전트 독립성** | 각 에이전트는 독립된 context, 결과 요약만 반환 |
| **결정론적 출력** | 같은 입력 → 같은 출력 (RNG 없음) |
| **점진적 개선** | 매 사이클마다 새로운 gap 발견 & 우선순위 재정렬 |
| **사용자 통제** | 언제든 "멈춰"로 중단, max iteration 설정 가능 |
| **정직한 기록** | 모든 변경사항 registry.md에 기록 |

---

## 10. 문제 해결

| 상황 | 처리 방법 |
|------|---------|
| **scout가 no_result 반환** | keyword-queue에서 제거, 다음 반복으로 진행 |
| **conflict-checker가 전부 reject** | extractor 호출 없음, deltas 비어있음, 다음 반복으로 |
| **extractor가 paywall 접근 불가** | blocked_paywall로 표기, abstract만으로 진행 또는 block |
| **registry-keeper 갱신 실패** | 경고하고 다음 반복으로 (중단하지 않음) |
| **keyword-queue 완전히 소진** | "모든 키워드 소진" 보고, 루프 종료 |
| **커버리지 90% 달성** | "목표 달성" 보고, 루프 종료 |

---

## 11. 사용 예시

```
사용자: "루프를 20번 돌려줘"

[시스템이 4-에이전트 루프 실행]

[반복 1] scout: 6편 발견 → conflict-checker: 3편 승인 
         → extractor: 3편 처리 → registry-keeper: EC filled
         [1/20] +3편 처리, 신규 filled: crop_growth_guide.EC (사과)

[반복 2] scout: 4편 발견 → conflict-checker: 2편 승인 
         → extractor: 2편 처리 → registry-keeper: pH partial
         [2/20] +2편 처리, 신규 partial: crop_growth_guide.pH (배)

...

[반복 12] 커버리지 90% 달성
          최종 보고: filled 18 / partial 9 / missing 3
          루프 종료
```

---

## 12. 향후 확장

- **다중 언어 논문:** 일본어, 독일어 추가 (현재 한국/영어)
- **동시성 제어:** 현재 순차 실행, 병렬 실행 고려
- **캐싱:** 검색 결과 캐시해 중복 호출 방지
- **검증 강화:** conflict-checker 검증 단계 추가 (예: 3명 독립 검증)
- **자동 초록 생성:** extractor 작업 보조

---

**이 문서는 모든 에이전트와 ORCHESTRATOR의 성경입니다.**
질문이 있으면 여기로 돌아오세요.
