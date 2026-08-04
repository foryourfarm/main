# Kim, Choi, Cho, Yun, Park, Kim, Jeon & Lee (2019) — Response of Crop Water Stress Index (CWSI) and Canopy Temperature of Apple Tree to Irrigation Treatment Schemes

**Source:** Journal of the Korean Society of Agricultural Engineers 61(5):23-31, DOI: 10.5389/KSAE.2019.61.5.023, 농촌진흥청 국립농업과학원(NAS)·국립원예특작과학원(NIHHS)
**Citation Count:** 미확인
**Status:** Iteration 8, Approved (rainfall_by_stage/관개 보조자료, 국내 — mm 적정구간 아님, 관개기준 방법론)

---

## 8단계 정리

### 1. 데이터 수집 방법
'시나노 스위트(Sinano Sweet)' 사과나무(4년생, 2×3.4m 재식), 2018년 6~9월(76일간), 3개 관개처리(Tr-1 무관수/천수의존, Tr-2 일증발산량(ET)의 50% 관수, Tr-3 75% 관수) × 3반복. 적외선센서(SI-431)로 수관온도(Canopy temperature) 측정, 기상관측(기온·상대습도·일사·풍속)과 함께 이론적 작물수분스트레스지수(CWSI) 산출·비교.

### 2. 표본
1개 품종('Sinano Sweet') × 3개 관개처리 × 3반복, 단일 생육시즌(2018), n=1,290(개별 관측치 기준).

### 3. 메커니즘
CWSI는 수관온도(Tc)와 기온(Ta)의 차(Tc-Ta)를 습윤기준(Twet)·건조기준(Tdry) 대비 정규화해 산출(Idso 1981 empirical / Jackson 1981 theoretical 방식). 관수량이 늘면 증발냉각효과로 수관온도가 낮아지고 Tc-Ta가 작아져 CWSI가 낮아진다는 원리.

### 4. 정량적 결과 ⭐
- 평균 수관온도: Tr-1(무관수) 34.6±3.7℃, Tr-2(50%ET) 33.5±3.7℃, Tr-3(75%ET) 32.6±3.9℃ — Tr-3에서 가장 낮음
- Tc-Ta: Tr-1 2.92±0.78℃, Tr-2 1.83±0.64℃, Tr-3 1.01±0.47℃ — 관수량↑ → Tc-Ta↓ (통계적으로 유의, Duncan's test A/B/C 그룹 구분)
- CWSI: Tr-1 0.79±0.10, Tr-2 0.71±0.11, Tr-3 0.64±0.09 — 관수량↑ → CWSI↓(수분스트레스 완화)
- CWSI는 일사량(R=0.684)·풍속(R=0.541)·상대습도(R=-0.524)와 상관, 기온과의 상관은 상대적으로 낮음(R=0.406)
- 기온 40℃ 초과 시점에서 Tr-1 수관온도 37.4℃, Tr-2 38.4℃, Tr-3 38.8℃로 역전되는 구간 관찰(고온 극한에서는 관수 효과 패턴이 달라짐, 저자는 증산 한계로 추정)

### 5. 산업 적용
CWSI 기반 관개 스케줄링(관수 시점·양 결정)의 국내 사과 적용 가능성을 실증. 관수량을 "% of ET" 단위로 정의해 지역별 ET0 데이터만 있으면 이식 가능한 스케줄링 프레임 제공.

### 6. 한계
단일 품종·단일 시즌(2018)·3반복의 소규모 실험. **관수량이 "mm 절대량"이 아니라 "ET 대비 비율(%)"로만 정의**되어 있어, registry가 원하는 "생육단계별 강수 총량 mm" 형태로 직접 전환하려면 해당 지역·연도의 일별 ET 데이터가 별도로 필요. 자연강우가 아닌 인공관개 스킴이라 rainfall_by_stage(자연강수 의존형) 지표와는 성격이 다름 — 관개 지표(별도 트랙)로 분류 필요.

### 7. 구조적 문제 ⭐⭐
이 논문은 registry의 rainfall_by_stage(자연강수 총량)나 gdd/temp_day 어느 것도 직접 채우지 못한다. 대신 **"관개 스케줄링"이라는 전혀 다른 지표軸**(자연강수 의존이 아니라 인공관수 결정 로직)을 제시한다. CLAUDE.md §1의 "단기 실시간 대응" 철학과 연결하면, 향후 이 앱이 "오늘 관수해야 하는가"를 판단하는 기능을 추가한다면 이 논문의 CWSI 프레임이 유용할 수 있으나, **현재 DB 스키마(`crop_growth_guide.rainfall_by_stage`)의 범위 밖**이다 — 신규 지표(`irrigation_schedule` 또는 `cwsi_threshold`) 신설 여부는 팀 결정 사안.

### 8. 새로운 Gap
한국 사과 주산지별 일별 ET0(기준증발산량) 데이터 확보. CWSI 임계값(예: Erdem 2010의 브로콜리 CWSI 0.51 기준처럼 사과에 특화된 관개결정 임계값) 설정.

---

## Registry Delta

**Crop:** 사과
**Indicator:** rainfall_by_stage(간접 참고) / **신규 지표 후보**: 관개스케줄링(CWSI 기반)
**Status:** rainfall_by_stage는 변화 없음(partial 유지, 이 논문은 자연강수 지표가 아님) / 신규 지표 후보는 partial(방법론 확인, DB 미반영)
**Value:** 관수량(50%/75% ET) 증가 시 수관온도 최대 2℃, CWSI 0.15 감소(무관수 대비 75%ET에서 0.79→0.64). 자연강수 mm 적정구간과는 무관.
**Confidence:** 중(국내 RDA 실측, 단일 품종·단일 시즌)
**Source:** Kim, M. et al. (2019), J. Korean Soc. Agric. Eng. 61(5):23-31
**Note:** ⚠️ 이 논문은 rainfall_by_stage 갭을 채우지 않음(자연강수가 아니라 인공관개 스킴 실험). 향후 "관개 스케줄링" 기능을 앱에 추가할 경우를 위한 참고자료로만 등록. 스키마 반영 여부는 검색이 아니라 팀 결정 사안.
