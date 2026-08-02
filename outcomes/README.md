# 5작물 채점 이관 계약

2026-08-03 갱신(`knowledge_version` **2026-08-03-v3** / `scoring_version` **2026-08-03-v2**). ForYourFarm에 전달할 5작물(사과·배·상추·감자·오이) 채점 규칙, 실행 코드, 검증 산출물의 복사본이다.

## 2026-08-03 변경 — ForYourFarm 쪽에서 확인할 것

1. **작물 무관 공유 토양 밴드 삭제.** `_shared.json`의 `soil_rules`(pH 6.0~7.0 / 유기물 20~30 / 유효인산 300~550)가 사라졌다. 출처가 확인되지 않은 값이었고, 유효인산 300~550은 RDA 비료사용처방 5차(작물별 200~500)와 국가농업환경변동조사 등급표(최적 200~450) 양쪽에서 반증됐다. **5작물 전부 작물별 문헌 밴드로만 채점된다.** 소비 측에서 공유 밴드를 참조하던 코드가 있으면 작물별 밴드로 바꿔야 한다.
2. **감자 pH 밴드 신설(최대 결함 수정).** 종전엔 감자에 pH 밴드가 없어 공유값 6.0~7.0으로 채점됐는데 감자는 산성 토양 작물이라 방향이 반대였다. RDA 교본 033의 5.0~6.0으로 교체했다.
3. **오이·감자 토양 6지표, 상추 유기물 신설** — RDA 「작물별 비료사용처방」 5차(2022) 진단기준표. 주의: 오이·감자·상추 화학성은 원문이 **시설재배토양 기준**으로 표기하며 노지 기준 유무는 미확인이다(FarmML 실측은 노지 시군구 평균).
4. **물리성 채점축 신설** — `slope_pct`(사과 0-15%, 나머지 0-7%), `gravel_pct`(감자만 0-35%). 등급코드를 등급 상한 %로 환산해 화학 지표와 같은 곡선에 태우고 토양 총점 내부 균등 평균에 합류시킨다. 가중치(토양 60 / 기온 40 / 강수 0)는 바꾸지 않았다.
5. **산출 컬럼 변화.** `soil_score_total`(작물 무관)과 `{지표}_score`(작물 무관)가 사라지고 전부 `soil_score_total_{crop_code}` / `{지표}_score_{crop_code}` 형태만 남는다. `RegionalScore.csv`에 `slope_pct`·`gravel_pct` 원시 컬럼이 추가됐다.
6. **`method` 필드 최초 충전.** 문헌측 측정 프로토콜이 국가 표준으로 확정됐다(pH 1:5 물 / 유기물 Tyurin / 유효인산 Lancaster / 치환성 K·Ca·Mg 1M NH4OAc / 풍건 20 mesh). 실측측(흙토람 API) 추출법은 여전히 미확인이라 `[확인 필요]`가 남아 있다.

7. **EC 채점 개시(오이·감자·상추만).** 처방 5차 'EC 2 이하'. 종전엔 "실측 16/150이라 불가"로 판단했으나 그건 읍면동 단위 조인의 산물이었다 — 흙토람 필지 실측 elcd는 23,973건(86%)·142/160 시군구에 있고, 시군구 폴백으로 **103/150**(이미 채점 중인 Ca·Mg와 같은 커버리지)이 된다. 입력은 `data/ml/soil_ec_by_region.csv`의 **`ec_median`**(평균 아님 — 분포가 오른쪽으로 심하게 치우쳐 시설 염류집적 필지가 지역 대표값을 끌어올린다: 중앙값 0.61 vs 평균 2.11, 최대 30.0). 사과·배는 처방표 EC 칸이 '–'라 밴드를 만들지 않았다. 상추 `allowed_max=2.9`만 휴리스틱이 아닌 실측값(노안성 2004 수량 20% 감소점). ⚠️흙토람 `elcd`가 1:5 비환산인지 지도자료용 ×5인지 미확인 — ×5라면 이 밴드는 통째로 어긋난다 `[확인 필요]`.

점수 영향(150지역 평균, 총점):

| 작물 | 개정 전 | 밴드 전환 후 | EC 추가 후 |
|---|---|---|---|
| 사과 | 57.8 | 58.6 | 58.6 |
| 배 | 77.2 | 77.7 | 77.7 |
| 상추 | 72.2 | 73.1 | 75.7 |
| 감자 | 91.6 | 79.7 | 81.6 |
| 오이 | 93.1 | 78.2 | 80.4 |

감자·오이 하락은 버그가 아니라 느슨한 출처미상 공유 밴드가 실제 문헌 기준으로 바뀐 결과다. EC 추가로 소폭 오르는 이유는 국내 노지 EC가 실제로 낮기 때문이다 — 150지역 중 기준(2 dS/m)을 넘는 곳은 **2곳뿐**이라 변별력 자체는 작다. 그래도 넣은 이유는 염류집적 지역을 놓치지 않기 위해서다.

- `memory/crop_rules/`: 공통 규칙과 작물별 규칙 JSON.
- `memory/indicator_dispersion.json`: 실측 분포 기반 위험구간 감쇠폭.
- `scripts/ml/`: 로그 채점 곡선, KNN 결측 대체, 산포도·앵커·지역 점수 생성기와 회귀검사.
- `AnswerData.csv`, `RegionalScore.csv`, `data/ml/crop_literature_anchor_experiment.csv`: FarmML 데이터로 재생성한 계약 산출물.
- `data/99_codebook_modified.csv`: 물리성 등급코드 정의(2026-08-03 추가). `slope_code`·`subsoil_gravel_code`가 어떤 % 구간을 뜻하는지의 단일 소스이며, `_shared.json`의 `physical_code_maps` 환산표가 이 정의와 일치하는지 `test_physical_scoring.py`가 대조한다.

## 이관 패키지 구성

### 운영 계약

- `memory/crop_rules/*.json`: 5작물 승인 규칙과 공유 가중치·물리성 코드 환산표.
- `scripts/ml/`: 결정론적 점수 계산·KNN 대체·산출물 생성기와 회귀검사.
- `AnswerData.csv`: 44개 문헌 기준 라벨 정의.
- `RegionalScore.csv`: 150지역 원시값·대체 계보·작물별 가중점수·MLCM·백분위 결과.
- `data/ml/soil_ec_by_region.csv`: 150지역 EC 중앙값과 읍면동/시군구 매칭 단계.
- `data/99_codebook_modified.csv`: 경사·자갈 등급코드 원문 정의.

### 버전·대체 감사

- `data/ml/regional_score_manifest.json`: `knowledge_version=2026-08-03-v3`, `scoring_version=2026-08-03-v2`, 가중치·MLCM 근사·결측 대체·작물별 구성지표 계약.
- `data/ml/imputation_validation.json`, `data/ml/imputation_outliers.csv`: KNN 후보 비교와 이상치 감사 자료.
- `data/ml/crop_literature_anchor_manifest.json`: 문헌 앵커 실험의 `provisional=true`·정확도 주장 금지 경계를 명시한다.

### 판단자료 — 운영 점수에 미반영

- `data/ml/ec_score_sensitivity.csv`, `docs/ml/ec_score_sensitivity.md`: EC 1:5 원값/이미 ×5 환산 두 시나리오. 원값 가정은 오이·감자·상추 각각 2/150지역 감점, ×5 가정은 모두 0/150지역 감점이다. **EC 밴드와 운영 점수는 바꾸지 않는다.**
- `data/ml/national_grade_score_comparison.csv`, `data/ml/national_grade_multiplier_sensitivity.csv`, `docs/ml/national_grade_score_comparison.md`: 국가 25/50/75/90/100 등급과 현재 로그 곡선 비교. 현재 `RISK_SD_MULTIPLIER=2.0`은 Spearman 0.98006, 평균편차 +1.03844, MAE 2.05164이며 3.0의 MAE 개선이 0.03874점뿐이라 **2.0 유지** 판단이다.
- `data/ml/pear_temperature_risk.csv`, `docs/ml/pear_temperature_risk.md`: 150지역 배 온도편차 정보. 저위험 99·중위험 31·고위험 6·12개월 미충족 14지역이며 `scored_in_suitability=false`다.

## ForYourFarm 적용 체크리스트

1. 공유 토양 밴드 폴백을 제거하고 작물별 `soil_overrides`만 읽는다.
2. `band_score`의 단측 밴드와 로그 감쇠 동작을 `scripts/ml/scoring.py`와 동일하게 맞춘다.
3. `RegionalScore.csv`의 작물별 컬럼만 사용하고 가중점수와 MLCM을 같은 척도로 해석하지 않는다.
4. EC 측정 스케일 확정 전까지 1:5/×5 경고를 제품 설명과 운영 로그에 유지한다.
5. 국가 등급 비교와 배 위험 플래그는 설명·검토용으로만 이관하며 적합도 점수에 합산하지 않는다.
6. `regional_score_manifest.json`의 버전과 구성지표를 실제 배포 코드의 계약 버전으로 기록한다.

## 의도적으로 제외한 항목

- `data/ml/region_crop_insights.csv`와 `data/ml/run_manifest.json`: 구형 선형 곡선·토양 3지표·강수 25%를 사용하는 탐색 산출물이라 현재 60/40/0 로그 채점 계약과 다르다.
- `scripts/collect_weather_daily.py`, `scripts/build_weather_daily_indicators.py`, `data/03_weather_daily.csv`: 연간 endpoint의 실시간 canary와 218관측소→150지역 수집이 API 요청 제한으로 완료되지 않았다. 완료 전 고정 이관 계약에 넣지 않는다.
- `scripts/ml/build_validation_reports.py`: FarmML 원시·가공 입력에 의존하는 분석 생성기다. ForYourFarm에는 검증이 끝난 고정 CSV와 보고서만 전달한다.
- 원시 문헌·탐색 문서·Streamlit 화면: 근거 연구 및 내부 확인용이며 운영 계약이 아니다.

연구 산출물은 FarmML 루트에서 다음 순서로 재생성한다.

```powershell
python scripts/ml/build_indicator_dispersion.py
python scripts/ml/crop_literature_anchor_experiment.py
python scripts/ml/build_answer_data.py
python scripts/ml/build_regional_score.py
python scripts/ml/test_crop_literature_anchor.py
python scripts/ml/test_imputation.py
python scripts/ml/test_physical_scoring.py
```

이관 복사본은 다음 명령으로 검증한다.

```powershell
python outcomes/scripts/ml/test_crop_literature_anchor.py
python outcomes/scripts/ml/test_imputation.py
python outcomes/scripts/ml/test_physical_scoring.py
```

고정 판단자료 검증 기준은 다음과 같다.

- EC 민감도 900행 = 150지역 × 3작물 × 2시나리오.
- 국가 등급 상세 750행 = 150지역 × 5지표, multiplier 민감도 25행 = 5지표 × 5후보.
- 배 위험 150행, 위험 수준은 `low|medium|high|unknown`, 모든 행의 `scored_in_suitability=false`.
- `RegionalScore.csv` 150지역 유일성과 모든 점수의 0~100 범위 유지.

채점은 문헌 밴드 대비 점진 편차 점수다. 최적구간 100점, 최적구간 직후 95점, 허용경계 60점이며 위험구간은 `risk_width`까지 로그 감쇠한다. 결측치는 원시값 공간 거리역수 가중 KNN으로 대체하고 방법·출처를 `RegionalScore.csv`에 남긴다.

`outcomes/`는 수동 이관 경계다. ForYourFarm은 FarmML의 `data/`, `memory/`, `scripts/`를 직접 import하지 않고 검증된 이 디렉터리만 복사해 사용한다.
