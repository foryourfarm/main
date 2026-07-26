# 국립농업과학원 농업환경자원 변동평가 (전국 과수원 실측, 2013~2016) — 추출 불가

**요청 KISTI ID**: TRKO202100009605  
**요청 URL**: https://scienceon.kisti.re.kr/srch/selectPORSrchReport.do?cn=TRKO202100009605  
**상태**: ❌ **원문 접근 불가 (404 Not Found)**  
**추출 날짜**: 2026-07-25

---

## 1. 조회 결과

| 시도 | 결과 | 비고 |
|---|---|---|
| KISTI 원문 링크 | 404 Not Found | 선택된 보고서를 찾을 수 없음 |
| RDA 공식 사이트 검색 | 검색 결과 없음 | 농촌진흥청 메인, 흙토람, ASTIS 모두 음성 |
| WebFetch 시도 | HTTP 404 | 보고서 ID 또는 URL 오류 가능성 |

---

## 2. 원문 부재의 영향

### 2.1 요청 목표 (미충족)

```yaml
목표: 사과 EC national-scale 검증
세부사항:
  - 표본수: [확인 필요 — 전국 규모로 추정]
  - 조사 연도/지역: 2013~2016, 전국
  - 측정법: 1:5 물추출법? 포화침출액법? [확인 필요]
  - 사과 EC 평균값: [원문 필요]
  - 단위: dS/m (추정)
```

### 2.2 현재 EC 지표 커버리지 (대체 자료만 사용)

| 논문 | 표본 | EC 값 | 측정법 | 신뢰도 |
|---|---|---|---|---|
| **hongro-fruit-quality-soil-2009.md** | 60농가 | 1.1±0.6 dS/m | 1:5 물추출 | ⚠️ 중간 (품종 특화, 소규모) |
| **sod-orchard-soil-acidity-2009.md** | 4처리 | 0.8±0.3 dS/m | 1:5 물추출 | ⚠️ 낮음 (극소규모, 초생만) |
| **organic-apple-manual-soil-management.md** | 참고치 | 0.8~1.5 dS/m | 1:5 물추출 | ⚠️ 낮음 (범위만, 매뉴얼) |
| **orchards-fertilizer-survey-805farms-2023.md** | 805농가 | — | — | EC 데이터 없음 |

**결론**: 현재 EC 데이터는 **소규모 조사(60~4농가) + 매뉴얼 참고치**만 존재. 
**National-scale(전국 대표성) 검증 불가능**.

---

## 3. 대체 자료 탐색 방안

### 3.1 추천 검색 경로

1. **흙토람(토양환경정보시스템)** https://soil.rda.go.kr/sibi/
   - 토양 검정 누적 데이터베이스
   - 사과 재배지 EC 통계 쿼리 가능성 있음
   - 문의: RDA 토양양분정보팀 (1544-8572)

2. **RDA 공공데이터포털 (data.go.kr)**
   - Dataset #15124016: 작물별 비료사용처방 (2023)
   - EC 관련 통계 포함 가능성 검토 필요

3. **한국과학기술정보연구원(KISTI) 직접 문의**
   - TRKO202100009605 올바른 URL 확인 필요

4. **국립농산물품질관리서비스 (nqs.go.kr)**
   - 전국 과수원 표본 토양 화학성 조사 데이터

### 3.2 대체 학술 논문 (검색 예정 키워드)

```
- "RDA 농업환경자원 변동평가" (2013-2016)
- "국내 사과 재배지 토양 EC 전국 조사"
- "한국 과수원 토양 염류 축적 현황"
- "사과 과수원 토양 전기전도도 지역별 비교"
```

---

## 4. Registry 업데이트 (현 상태 반영)

### 현재 gap: EC indicator "filled" 재평가

**Registry 현 상태**:
```yaml
crop: 사과
indicator: ec
status: filled
source: [hongro-2009, sod-2009, organic-manual]
```

**권장 재분류**:
```yaml
crop: 사과
indicator: ec
status: partial_filled  # "filled"는 과평가
confidence: ⚠️ 낮음~중간
coverage_note:
  - hongro: 품종 특화(홍로만), 소표본(N=60)
  - sod: 초생재배 조건만, 극소규모(N=4 처리)
  - organic: 매뉴얼 범위값, 실측 아님
  - missing: national-scale 대표값 (전국 평균, 지역별 편차)
next_target: RDA 전국 토양 검정 데이터 통합
```

---

## 5. 데이터 신뢰도 평가

| 항목 | 평가 | 문제점 |
|---|---|---|
| **원문 확보** | ❌ 불가 | KISTI 404 오류 |
| **표본 대표성** | ⚠️ 낮음 | 기존 자료는 소규모/특화조건만 |
| **Measurement 통일성** | ⚠️ 중간 | 모두 1:5 물추출법(국제 ECe와 다름) |
| **National coverage** | ❌ 부족 | 지역별·시계열 데이터 전무 |
| **실용성** | ⚠️ 중간 | crop_growth_guide의 EC optimal range(0.8~1.5)는 기존 3편에만 의존 |

---

## 6. 권고 액션

### 6.1 즉시 (1주일 내)

- [ ] RDA 토양양분정보팀 문의 (1544-8572)
  - "TRKO202100009605 올바른 URL 또는 대체 자료"
  - "2013~2016 과수원 전국 실측 EC 데이터 공개 여부"

- [ ] 흙토람(soil.rda.go.kr) 직접 조회
  - 사과 재배지 EC 통계(전국, 지역별) 접근성 확인

### 6.2 중기 (2~4주)

- [ ] KISTI 보고서 정정된 URL 또는 PDF 획득 시 재추출
- [ ] 대체 national-scale 데이터 발굴 및 정리
- [ ] Registry의 EC indicator 상태 업데이트

### 6.3 Registry 보완 필요 항목

```yaml
# 추가할 구조적 gap
crop_growth_guide.ec:
  current_optimal_range: "0.8~1.5 dS/m (1:5 물추출)"
  basis:
    - hongro(N=60): 1.1±0.6
    - sod(N=4): 0.8±0.3  
    - organic(범위): 0.8~1.5
  
  confidence_level: "medium_at_best"
  
  missing_data:
    - national_average: "필수 — 현재 전국 표준값 부재"
    - by_region: "경주, 청송, 무주, 장수 등 지역별 편차"
    - by_cultivation_type: "초생·유기·관행 간 EC 비교"
    - by_growth_stage: "전기간 단일값 → 생육 단계별 분화 필요"
    
  int_unit_note: "1:5 물추출법(국내 표준) ≠ ECe(국제 표준). 환산계수 미정"
```

---

## 7. 원본 추구 현황

**KISTI 보고서 추적 기록**:

```
요청: 국립농업과학원 농업환경자원 변동평가 (2013~2016)
KISTI ID: TRKO202100009605
직접 URL: https://scienceon.kisti.re.kr/srch/selectPORSrchReport.do?cn=TRKO202100009605

결과:
  ❌ HTTP 404 Not Found
  
가능한 원인:
  1. KISTI 서버 일시 오류
  2. 보고서 ID 오타 또는 버전 변경
  3. 보고서 비공개/삭제됨
  4. 접근 권한 제한 (인증 필요)
  
검토자 확인 사항:
  - KISTI에서 올바른 논문 URL 재확인 필요
  - 혹은 RDA 공식 사이트에서 동일 보고서의 대체 URL 검색
```

---

## 8. 결론

**본 추출 미완료 (0% 달성)**

| 단계 | 상태 | 비고 |
|---|---|---|
| 1. KISTI 보고서 다운로드/열람 | ❌ 불가 | 404 오류 |
| 2. 사과 EC 수치 찾기 | ❌ 불가 | 원문 부재 |
| 3. 측정법 확인 | ❌ 불가 | 원문 부재 |
| 4. 표본수·지역·연도 기록 | ❌ 불가 | 원문 부재 |
| 5. 기존 자료와 비교 | ⚠️ 부분 | 대체 자료로만 가능 |
| 6. 8단계 정리본 작성 | ❌ 불가 | 원문 데이터 필수 |

**Registry Delta**:
```yaml
status: "attempted_not_found"
paper_title: "[미확보] 농업환경자원 변동평가 (국립농업과학원, 2013~2016)"
saved_path: "knowledge-base/papers/apple/rda-national-orchard-soil-ec-2021.md"
crop: 사과
coverage_delta:
  crop_growth_guide:
    - indicator: ec
      crop: 사과
      growth_stage: 전기간
      has_optimal_range: true
      has_allowed_range: false
      status: partial (national-scale 검증 필요)
      current_basis: "소규모 조사(N≤60) + 매뉴얼 범위"
      note: "KISTI 논문 접근 불가로 national-scale 검증 중단"
      
new_gap_keywords: 
  - "RDA 전국 토양 검정 EC 통계"
  - "사과 재배지 EC 전국 평균 및 지역별 분포"
  - "흙토람 데이터베이스 EC 통계 쿼리"
  
recommended_next_action: "RDA 토양양분정보팀 직접 문의 또는 흙토람 조회"

one_line_summary: "KISTI 원문 접근 불가(404). 대체 national-scale 자료 탐색 필요."
```

---

**마지막 검토**: 2026-07-25  
**상태**: ❌ **원문 미확보 — 재시도 필요**  
**기술 담당자**: RDA 토올양분정보팀, KISTI 문의 권장  
**다음 액션**:
- [ ] KISTI 또는 RDA에 보고서 위치 문의 (진행 중)
- [ ] 흙토람에서 national-scale EC 통계 쿼리 시도
- [ ] 대체 RDA 보고서(2023 업데이트) EC 데이터 확인
