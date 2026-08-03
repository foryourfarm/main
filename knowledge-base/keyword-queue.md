# 검색 키워드 큐

> 우선순위 순서대로 나열. registry-keeper가 매 사이클 끝에 재정렬한다.
> scout이 키워드 하나를 소비하면 이 목록에서 제거하고 search-log.md로 이동시킨다.

## Iteration 7 최우선 Gap (Iteration 6 후 발굴/이월, 2026-08-03)

> **사용자 지정 조건**: ①국내논문 우선 ②스캔본 지양 ③정확성 보장.

0. **[보류, 국내논문 0편] 사과 착색기(coloring) `temp_day`/`temp_night_min`** — Iteration 5에서 scout 실행, 국내 문헌 인용수 기준 통과작 없어 보류 유지. 재개하려면: (a) 인용수 기준 완화(국내 학회 초록집 허용) 또는 (b) RDA 사과연구소 회색문헌으로 전환 — 사용자 확인 필요. 여전히 registry상 missing
1. **사과 gdd Tbase — 학술논문 경로 소득 없음, 회색문헌으로 전환** — Iteration 4~6 합계 국내 후보 5편(Lee 2015, 김진희 2019, 김수옥·윤진일 2010 등) 전부 GDD 아닌 근접개념(냉각요구시간·냉해위험도)으로 확인됨. **다음은 RDA 사과연구소/국립원예특작과학원의 적산온도 기반 재배력·수확기예측 기술서(회색문헌) 확인**이 더 유망(scout 재실행보다 직접 문의 권장)
2. **forcing_requirement_bloom·chilling_requirement 신규 지표 스키마 결정** (검색 아님, 팀 결정) — DB 스키마에 이 지표들 자체가 없음
3. **사과 EC national-scale 원문 확보** — TRKO202100009605(RDA 5차사업 보고서) 메타데이터는 확인됐으나 원문 다운로드가 JS세션에 막힘. **다음은 학술검색이 아니라 NTIS 재검색/RDA 국립농업과학원 직접 문의**가 필요(scout 재실행 불필요)
4. **5작물 공통 토양 화학성(pH/EC/유기물/P2O5) 공백** — 배는 전부 missing, 오이·감자는 처방기준 없음, 상추는 협소구간만
5. **배 대기온 고온 피해 임계값** — FST 47.1°C는 과실표면온도. 재배자가 측정 가능한 대기온 기준값 필요 (scout-4b, 이월)
6. **한국 실측 강수 임계값 (지역·토양질감별)** — 배·오이 전부 중국/외국 자료. 사과는 김미리·김승규(2014)로 방향성만 확보, 절대 mm구간은 여전히 미해결 (scout-4a, 이월)
7. **토양질감별 과습 임계값** / **ETc 절대값 환산** — 차순위 이월

> 관련 문서: `docs/guide-seed-known-issues.md`(P1/F-2), `docs/temperature-scoring.md`(§4), `knowledge-base/registry.md`(§6-2 Iteration 6 완료 요약)

## Iteration 6 결과 (2026-08-03, 참고 — 재검색 불필요)

> 사용자가 직접 PDF 4편(Warrington 1999, 김미리·김승규 2014, 이재범·김종윤 2023, 김수옥·윤진일 2010)을 다운로드해 제공, 전부 원문 확보·md화 완료.

- ~~사과 fruit_growth/maturity 온도~~ → **partial 확보**(Warrington 1999, 해외자료·bounded range 아님, 사용자가 국내우선 예외로 직접 선택)
- ~~사과 rainfall_by_stage 원문~~ → **해결**(김미리·김승규 2014 전문 확보, 8개 계수+3모형비교)
- ~~사과 ec 측정법 원문~~ → **해결**(이재범·김종윤 2023 전문 확보, reference_only 확정)
- ~~사과 gdd Tbase(김수옥·윤진일 2010)~~ → 원문은 확보했으나 **여전히 미해결** — GDD 아닌 Chill Day 모형(냉각요구시간)으로 확인, 위 Iteration 7 #1로 재이월. 부산물로 chilling_requirement 2번째 근거 + forcing_requirement_bloom 신규지표 발견

## Iteration 5 결과 (2026-08-02, 참고 — 재검색 불필요)

- ~~사과 organic~~ → **해결**(신규 검색 아님, 기존 보유 논문 hongro-fruit-quality-soil-2009 + organic-apple-manual 교차반영)
- ~~사과 gdd Tbase 후보 검증~~ → 3편 전부 미해결(1 blocked, 2 reject) — 단 부산물로 **chilling_requirement 신규지표 발견**
- ~~사과 EC/rainfall 국내후보 검증~~ → 6편 확인했으나 전부 원문 미확보(caution/blocked) — Iteration 6에서 2편 원문 확보로 해소
- **신규 발견(검색 대상 아님, 팀 결정 사안)**: chilling_requirement 스키마 반영 여부, 일교차(DTR) 지표 반영 여부, temp_soil 지표 신설 여부 — registry.md §5/§6 참고

## Iteration 4에서 해결/부분해결된 항목 (참고, 재검색 불필요)

- ~~감자/배 괴경/근부 냉해~~ → 감자는 **해결**(Boydston 2006, 인용34, 6년 포장실측 -1.5~-2.8℃). 배 괴경/근부 냉해는 여전히 미착수(배는 애초 괴경이 없는 작물이라 해당 없음 — 이 항목은 사실상 감자 전용으로 재정의 필요)
- ~~오이 근권온도 vs 대기온 혼동~~ → **구조적으로 해결**(Wang 2018 + 이주영 2011), 단 대기온 자체의 수치는 여전히 미확보

## 차순위 (Iteration 2 미완료 + partial 강화)

6. 배 강수 partial 강화 (270mm → 한국 지역별 기준값)
7. 사과 강수 partial 강화 (단계별 → 한국 지역별 단계별)
8. 오이 강수 노지 기준값 (현재 온실만)
9. 감자 강수 기준값 (ETc 절대값 필요)

## 최우선 (5작물 화학성 구간 공백 → 기온/강수 로직 완성)

1. ✓ 사과 토양 pH 적정범위 (FILLED: 6.0~6.5, 5.5~6.8)
2. ✓ 배 토양 pH 적정범위 (FILLED: 5.8~7.0 in Iteration 2-1)
3. ✓ 감자 고온/냉해 (FILLED: Iteration 3-a 완료)
4. ✓ 배 일소 피해(FILLED) / 강수(PARTIAL): Iteration 3-b/c 완료
5. ✓ 강수 과습 임계값 (FILLED: 일 30-50mm in Iteration 3-c)
6. 배 토양 EC 적정범위 (대체 키워드/자료원) — [Iteration 1 신규] Yoon(2010) paywall, 국내 다른 실측 논문 또는 흙토람 통계 탐색
7. 배 P2O5 실태/기준 (대체 키워드/자료원) — [Iteration 1 신규] 2023 비료평가·전북농기원(2018) paywall, RDA 표준영농교본(배나무재배) 원문 우선 확인
8. 오이 토양 화학성 적정 pH EC 유효인산
9. 감자 토양 화학성 적정 pH EC 유효인산
10. 상추 토양 화학성 적정 pH EC 유효인산
11. 사과 토양 EC 적정범위 (PARTIAL 대체자료 필요)

## 중순위 (기존 차순위, Iteration 2 미완료 → 일부 Iteration 3 적용)

12. ✓ **오이/상추 기온 영향 고온** (FILLED: 30°C in Iteration 2-2) / 감자 기온(FILLED: Iteration 3-a)
13. ✓ **배 GDD** (FILLED: 85°C in Iteration 2-2) / 오이·감자·상추 GDD 베이스온도 확정 필요
14. ✓ **강수 과다 mm 임계값** (FILLED: 일 30-50mm in Iteration 3-c) / 작물별 민감도 차이 확인 필요
15. Yoon(2010)/2023 비료평가/전북농기원(2018) 원문 확보 경로 탐색 (RISS 원문 PDF, 기관 리포지토리, 저자 직접 요청, DOI 우회) — [재시도 후보]
16. 기온 ↔ 지중온도 환산 모델 (한국 지역별)
17. 배나무 표준 시비량 kg/10a (P2O5)
18. 사과나무 표준 시비량 kg/10a (PARTIAL: 실태조사 22.5 kg/10a)
19. 오이 감자 상추 표준 시비 처방 흙토람 (P0 지표 필요)

## 후순위 (검증 강화 + 지역·작물별 세분화)

20. apple soil nutrient optimal range Korea (P2O5 FILLED, EC PENDING)
21. cucumber potato lettuce soil suitability criteria Korea
22. 작물별 토양적성도 오이 감자 상추
23. 사과 P2O5 극단적 과잉의 원인 분석 (역사적 축적 vs 현장 관성)
24. **[Iteration 3 신규]** 배 FST(과실표면온도) ↔ 대기온 환산 모델 (현장 재배자 기준값 필요)
25. **[Iteration 3 신규]** 한국 토양질감별 강수 포화도 모델 (논토·밭토 구분)
26. **[Iteration 3 신규]** 감자/배/사과 냉해 기관별 세분화 (지상부 vs 괴경·근부)

## 인용 논문에서 발견한 후보 (extractor가 넘긴 것들, 아직 직접 검색 안 함)

### Iteration 2 이전 후보
- 김호정·심교문·현병근, "기후 및 토양 정보에서 최대저해인자법을 이용한 재배적지 구분의 통합에 관한 연구" (한국농림학회지 18(3)) — 사과 버전 확인 필요
- 농촌진흥청(2016), "토양·기후 요인을 종합적으로 고려한 과수 재배적지 구분" — 5작물 중 몇 종이나 커버하는지 확인
- Kim et al.(2016), "Land suitability assessment... using MLCM" — 사과·배 동시 수록 여부 확인
- RDA(2000), "표준영농교본, 배나무재배" — 시비 표준량 원출처 (P2O5도 포함 확인 필요)
- Seungho Lee 등(2008), "기후변화가 농업 생태에 미치는 영향... 나주" — 만개일 예측 모델 참고
- 배경학 외(이화여대), "사과 토양 EC 기준 시험" — EC 대체자료 (웹검색 필요)
- 한토학회지 특집, "원예작물 토양 화학성" — 오이·감자·상추 P, K, EC 기준 (기사 검색 필요)

### Iteration 3 신규 후보
- 감자 냉저장 연구 (국립원예특작과학원, 농과원) — 괴경·근부 냉해 임계값
- 한국 지역별 ET0(기준증발산량) 통계 (기상청, 농과원) — ETc 절대값 환산 필요
- 한국 토양질감별 포장용수량·하한함수량 (토양환경정보시스템, 흙토람) — 강수 임계값 지역화
