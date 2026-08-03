# 검색 키워드 큐

> 우선순위 순서대로 나열. registry-keeper가 매 사이클 끝에 재정렬한다.
> scout이 키워드 하나를 소비하면 이 목록에서 제거하고 search-log.md로 이동시킨다.

## Iteration 11 최우선 Gap (Iteration 10 후 발굴/이월, 2026-08-04)

0. **배 냉해(개엽기·만개기, 봄철) 원문 확보 — 최우선, 4회 연속 이월** — 임순희 외(2012, 원예과학기술지 30(2):102) 초록 원문 확보. **Lee, Ryu, Jeong, Cho, Lee & Han(2023), Scientia Horticulturae 307:111530, DOI 10.1016/j.scienta.2022.111530** 정식 원문 확보 최우선(만개기 -2.2/-4.4℃, Ballard 1971 파생표와 교차검증됨). ⚠️Yim(2014)은 겨울 휴지아 내동성으로 확인돼 이 gap을 채우지 못함 — 재검색 시 반드시 "휴면기 vs 개엽/만개기" 생육단계를 먼저 확인할 것
1. **배 EC/organic/p2o5 national-scale 또는 3번째 배전용 실측** — 배 전용 실측 2건(Ahn 2011 전북 859mg/kg, Lee 2016 완주 2050mg/kg)이 유효인산에서 2.4배 편차 — 원인 규명을 위한 3번째 지역 실측, 또는 TRKO202100009605(5차 농업환경자원변동평가)에 배 세부항 존재 여부 확인(사과 EC 이슈와 동일 경로). Lee & Lee(2011, 경남 25개소, EC), Park·Lim·Lee(2012, 배전용 P2O5), Lee et al.(2016, Acta Hortic. 1146:41-48, 배단독 EC, 접근차단 재시도), 윤성탁(2010, KCI paywall 우회, organic)
2. **배 winter_bud_freezing_hardiness 신규 지표 스키마 반영 여부** (검색 아님, 팀 결정) — 사과에 없는 배 전용 개념
3. **사과 EC optimal(0.8~1.5) 재검토** (검색보다 팀 결정 선행) — 전북 실측(0.5)이 기존 optimal보다 낮음
4. **유효인산 Bray-1/Lancaster 이중표기 정리** (검색 아님, 문서작업) — 사과·배 공통 문제로 확대 확인됨
5. **유효인산-착색 55.9% 연결 검증** — 사과 Kim(2012) 발견, 인산-착색 반응 문헌 탐색
6. **temp_day(coloring) 포장 실측 검증** — Kim(2016) 항온챔버 결과의 포장 재확인
7. **Chaves(2017) 방법론의 후지·홍로 적용** — Von Bertalanffy 커브핏 국내 품종 실측
8. **사과 EC national-scale(TRKO202100009605) PDF** — 4회 연속 이월
9. **organic 지표 registry 내 비중 재검토** (팀 결정)
10. **forcing_requirement_bloom·chilling_requirement·temp_night_min(coloring, 사과) 신규 지표 스키마 결정** (팀 결정)
11. **5작물 공통 토양 화학성 공백** — 오이·감자는 처방기준 없음, 상추는 협소구간만
12. **배 대기온 고온 피해 임계값** (scout-4b, 이월)
13. **한국 실측 강수 임계값** — 절대 mm구간 여전히 미해결(scout-4a, 이월)
14. **토양질감별 과습 임계값** / **ETc 절대값 환산** — 차순위 이월

> 관련 문서: `knowledge-base/registry.md`(§6-6 Iteration 10 완료 요약)

## Iteration 10 결과 (2026-08-04, 참고 — 재검색 불필요)

> 사용자 제공 PDF 3편(Yim 2014, Lee 2016, Cho 2023)을 전부 원문 확보·md화 완료.

- ~~배 frost_damage(개엽기/만개기, 봄철)~~ → **여전히 미해결(4회 연속 이월)** — Yim(2014)은 겨울 휴지아 내동성으로 확인돼 타겟 불일치(기각), 대신 신규지표 `winter_bud_freezing_hardiness`로 filled. 원 gap은 임순희(2012)·Lee(2023) 원문 확보 필요, Iteration 11 #0으로 이월
- ~~배 ec/organic/p2o5 배전용 검증~~ → **2번째 실측 확보**(Lee 2016, 완주) — 유효인산이 전북 실측(Ahn 2011)의 2.4배로 편차 확인, 3번째 실측 또는 national-scale 자료 필요로 Iteration 11 #1 이월
- ~~배 temp_night_min~~ → **최초 partial 전환**(Cho 2023, 나주 3개년 실측, 관찰적 상관관계 — 사과 Ryu 2017의 통제실험보다 신뢰도 낮음)

## Iteration 9 결과 (2026-08-04, 참고 — 재검색 불필요)

> 배 ec/organic/p2o5(완전 미착수 3개)를 scout으로 탐색. **신규 다운로드 없이 기존 사과배치 논문(Ahn 2011)의 배 부수데이터를 재발견해 즉시 반영** — md 파일 신규 생성 없음, registry.md만 갱신.

- ~~배 ec~~ → **최초 partial 전환**(Ahn 2011 배실측 0.6dS/m + Kang 2014 상한 2.0). 배 전용 신규후보(Lee&Lee 2011, Lee 2016) 원문 미확보로 Iteration 10 #1 이월
- ~~배 organic~~ → **최초 partial 전환**(Ahn 2011 배실측 35g/kg, Kang 2014 기준과 정확히 겹침 — 상호검증). 윤성탁(2010) 정량수치 미확보로 이월
- ~~배 p2o5~~ → **최초 partial 전환**(Ahn 2011 배실측 859mg/kg Lancaster법, 적정 2.9~4.3배 과잉). Park·Lim·Lee(2012) 원문 미확보로 이월
- ~~배 frost_damage(개엽기/만개기)~~ → **미해결이나 후보 4편 확보**(Ballard 1971, 임순희 2012, Lee 2023, Ito 2018) — Lee(2023)와 Ballard(1971) 파생표가 이미 교차검증(만개기 -2.2/-4.4℃), Iteration 10 #0 최우선으로 이월

## Iteration 9 최우선 Gap (Iteration 8 후 발굴/이월, 2026-08-03) [해결됨, 참고용]

> **사용자 지정 조건(Iteration 7부터 유지)**: 미해결 gap은 ①국내논문 여부 무관 ②스캔본 지양 ③정확성 보장. **Iteration 8부터 추가**: 신규 논문 탐색보다 기존 partial 수치의 재검토가 우선순위로 부상.

0. **사과 EC optimal(0.8~1.5) 재검토 — 검색보다 팀 결정 선행** — 전북 실측(Ahn 2011, 0.5 dS/m)이 기존 optimal 하한(0.8)보다 낮게 나옴. 기존 optimal은 6개 주산지(hongro N=60) 기반 — 지역편향인지 재검토 필요. 추가 지역 실측 탐색은 이 팀 결정 이후 진행
1. **유효인산 Bray-1/Lancaster 이중표기 정리** (검색 아님, 문서작업) — Kang(2014)·Kim(2012)·Ahn(2011) 3편 모두 200~900mg/kg대(Lancaster법 추정)로, registry 기존 Bray-1(30~50mg/kg)과 10배 이상 차이. registry §1 p2o5 행에 측정법 명시 필요
2. **유효인산-착색 55.9% 연결 검증** — Kim et al.(2012)에서 발견된 신규 연결고리. 인산 수준별 착색 반응을 직접 다룬 국내외 문헌 탐색
3. **temp_day(coloring) 포장 실측 검증** — Kim(2016)의 항온챔버(적출과실) 결과를 포장 대기온 실측으로 재확인하는 국내 후속 연구 탐색
4. **Chaves(2017) 방법론의 후지·홍로 적용** — Von Bertalanffy 커브핏을 한국 주력품종 만개~수확 과실직경 성장에 적용한 국내 연구 탐색
5. **사과 EC national-scale(TRKO202100009605) PDF 원문** — ScienceON 초록/목차까지만 접근, PDF는 여전히 막힘. NTIS 재검색/RDA 국립농업과학원 직접 문의 필요(scout 재실행 불필요, 4회 연속 이월)
6. **organic 지표 registry 내 비중 재검토** (검색 아님, 팀 결정) — Merwin(1994) 회귀왜곡 + Kim(2012) 기여율 낮음(0.1~5.6%), 2개 독립신호 축적
7. **forcing_requirement_bloom·chilling_requirement·temp_night_min(coloring) 신규 지표 스키마 결정** (검색 아님, 팀 결정) — 여전히 미결정, 총 3개
8. **5작물 공통 토양 화학성(pH/EC/유기물/P2O5) 공백** — 배는 전부 missing, 오이·감자는 처방기준 없음, 상추는 협소구간만
9. **배 대기온 고온 피해 임계값** — FST 47.1°C는 과실표면온도. 재배자가 측정 가능한 대기온 기준값 필요 (scout-4b, 이월)
10. **한국 실측 강수 임계값 (지역·토양질감별)** — 배·오이 전부 중국/외국 자료. 절대 mm구간은 여전히 미해결(scout-4a, 이월). Treder(2022)의 "유효강수" 개념을 한국 데이터로 재산출하는 것도 후보
11. **토양질감별 과습 임계값** / **ETc 절대값 환산** — 차순위 이월

> 관련 문서: `docs/guide-seed-known-issues.md`(P1/F-2), `docs/temperature-scoring.md`(§4), `knowledge-base/registry.md`(§6-4 Iteration 8 완료 요약)

## Iteration 8 결과 (2026-08-03, 참고 — 재검색 불필요)

> 사용자가 직접 PDF 8편(Kang 2014, Treder 2022, Kim CWSI 2019, Chaves 2017, Lee 2023, Kim coloring 2016, Kim soil-contribution 2012, Ahn 2011)을 다운로드해 제공, 전부 원문 확보·md화 완료.

- ~~사과 착색기(coloring) temp_day(낮기온)~~ → **최초 partial 전환**(Kim et al. 2016, 국내 홍로 항온챔버) — registry상 유일했던 순수 missing 항목 해소. 포장 실측 검증은 Iteration 9 #3으로 이월
- ~~사과 gdd Tbase (Chaves 2017 원문 확보)~~ → **재인용 함정 최종 해결** — 직접도출 확인, 단 한국 품종 미검증이라 partial 유지. 후지·홍로 적용은 Iteration 9 #4로 이월
- ~~사과 EC national-scale~~ → **부분 진전**(ScienceON 초록/목차 접근), PDF는 여전히 막혀 Iteration 9 #5로 이월. 대신 국가기준(Kang 2014)·지역실측(Ahn 2011) 확보로 EC optimal 자체의 재검토 필요성 발견(Iteration 9 #0)
- ~~사과 organic~~ → Kim(2012)에서 중요도 반증 신호 추가 확보, Iteration 9 #6(팀 결정)으로 이월
- ~~사과 temp_day(fruit_growth/maturity)~~ → **독립근거 3번째 확보**(Lee 2023, 국내 20년), 여전히 partial
- ~~사과 rainfall_by_stage~~ → **방법론 보강**(Treder 2022 유효강수 개념 / Kim CWSI 2019는 reference_only), mm구간은 여전히 미해결
- **신규 발견(검색 대상 아님)**: 유효인산 Bray-1/Lancaster 측정법 혼재(Iteration 9 #1), 유효인산-착색 55.9% 연결(Iteration 9 #2)

## Iteration 7 결과 (2026-08-03, 참고 — 재검색 불필요)

> 사용자가 직접 PDF 7편(Sharpley 2013, Sugiura 2013, Gasparatos 2011, Zanotelli 2019, Ryu 2017, Merwin&Stiles 1994, Cepeda 2021)을 다운로드해 제공, 전부 원문 확보·md화 완료.

- ~~사과 착색기(coloring) temp_night_min~~ → **최초 filled**(Ryu 2017, 국내 RDA 완주 실측) — 이번 배치의 핵심 성과. temp_day(낮기온)는 여전히 missing, Iteration 8 #0으로 이월
- ~~사과 fruit_growth/maturity 온도~~ → **독립근거 2번째 확보**(Sugiura 2013, 일본 40년 포장실측), 여전히 partial
- ~~사과 ec~~ → **교차검증 추가**(Gasparatos 2011, 그리스, 측정법 불일치로 직접대입 불가), national-scale은 여전히 미해결
- ~~사과 organic~~ → **전용연구 최초 확보**(Merwin&Stiles 1994, 미국, 관리방식 메커니즘), 여전히 partial
- ~~사과 p2o5_실태~~ → **구조적 설명 보강**(Sharpley 2013, legacy P 개념), optimal_range 수치는 변화 없음
- ~~사과 rainfall_by_stage~~ → **방법론 보강**(Zanotelli 2019, 이탈리아 Kc계수), 여전히 partial
- ~~사과 gdd Tbase~~ → **기각**(Cepeda 2021, Tbase가 Chaves 2017 재인용치로 확인돼 불채택) — Chaves(2017) 원문 확보로 Iteration 8 #1 이월

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
