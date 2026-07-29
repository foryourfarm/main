# 5작물 채점 이관 계약

2026-07-25 생성. 메인 프로젝트에 적용할 5작물(사과·배·상추·감자·오이)의
실행 규칙과 산출물만 담은 복사본이다.

- `memory/crop_rules/`: 공통 규칙과 5작물별 적용 규칙 JSON.
- `scripts/ml/`: 앵커, 채점 곡선(`scoring.py`), 점수 생성 스크립트, 회귀검사.
- `AnswerData.csv`: 문헌 밴드 표(중앙값·양끝). 채점 곡선과 무관해 그대로 유효하다.

채점 곡선이 2026-07-27 로그로 개정돼(`scripts/ml/scoring.py`) 이전 점수 산출물
`RegionalScore.csv`와 `data/ml/crop_literature_anchor_experiment.csv`는 삭제했다.
낡은 숫자를 유효한 산출물처럼 남겨두지 않기 위함이며, 아래 절차로 재생성해야 한다.
재생성 전까지 `test_crop_literature_anchor.py`의 CSV 검사 블록은 파일이 없어 건너뛴다
(곡선 계약·앵커 검사는 그대로 돈다).

## 결측·이상치 처리 (2026-07-29 개정)

`scripts/ml/imputation.py` 신규. 종전의 "점수 공간에서 최근접 5개 단순평균"을
**원시값 공간의 거리역수 가중 KNN**으로 교체했다. 이유·설계는 그 모듈 docstring에 있다.

- k와 예측인자 구성(공간전용 vs 다변량)을 홀드아웃 CV로 **측정해서** 고른다.
  1차 실행 결과(정규화 MAE, 낮을수록 좋음): 전역평균 0.7507 / 종전 방식 0.6039 /
  KNN 공간전용 k=5 0.4651 / **KNN 다변량 k=5 0.4300** 채택 — 종전 대비 28.8% 개선.
  전체 비교표는 `data/ml/imputation_validation.json`.
- 이상치는 이웃 대비 KNN 잔차(modified z>3.5)로 **탐지·플래그만** 하고 값은 바꾸지 않는다.
  판정된 20건을 전수 확인한 결과 전부 실재 가능한 극단값이었다(고지대 저온, 시설재배
  인산 과다, 화산토 유기물) — 치환하면 제품이 경고해야 할 신호를 지운다.
  치환은 `build_regional_score.REPLACE_KNN_OUTLIERS` 한 줄로 켠다. 원본값은 항상
  `data/ml/imputation_outliers.csv`에 보존된다.
- `RegionalScore.csv`에 변수별 `{변수}_impute_method` / `_impute_source`(빌린 지역·거리)
  / `_outlier` 컬럼이 추가됐다. 근사를 확정값처럼 보이게 하지 않기 위한 표기다.

## 재생성 절차

데이터는 레포 루트 `/data`를 읽는다(`outcomes/data/`는 이관되지 않았다):

```powershell
python outcomes/scripts/ml/build_answer_data.py
python outcomes/scripts/ml/build_indicator_dispersion.py   # 감쇠폭 선행 산출 (아래 참조)
python outcomes/scripts/ml/crop_literature_anchor_experiment.py
python outcomes/scripts/ml/build_regional_score.py
```

## 위험구간 감쇠폭 (2026-07-29 개정)

채점 곡선은 이전부터 로그였지만 **위험구간(허용경계 밖) 감쇠 거리가 완충폭 1배**로 묶여
있었다. 완충폭은 `allowed = optimal 폭 ±50%` 휴리스틱에서 나오므로 optimal이 좁은 지표는
완충폭도, 위험구간도 함께 좁아졌다 — 3중 압축이라 채점이 사실상 이진이었다.

이제 감쇠 거리를 **그 지표의 전국 실측 산포도**로 정한다
(`build_indicator_dispersion.py` → `memory/indicator_dispersion.json`,
`risk_width = 2.0 x robust_sd`, `robust_sd = 1.4826 x MAD`).
표준편차 대신 robust 추정치를 쓰는 이유: 유효인산 실측 1288mg/kg(시설재배 인산 과다, 실재값)
하나가 전국 채점 척도를 늘려버리면 안 된다.

이진성 완화 결과(150지역, 0점 건수):

| 지표 | 전 | 후 |
|---|---|---|
| 상추 pH | 107 | 44 |
| 사과 기온 | 92 | 35 |
| 상추 Ca | 56 | 6 |
| 상추 K | 50 | 4 |
| 상추 Mg | 41 | 0 |
| 상추 유효인산 | 22 | 4 |

배수 2.0은 문헌 근거가 아니라 명시적 휴리스틱이다 — 실제 감수 곡선 문헌 확보 시 교체
대상(`[확인 필요]`). 백엔드 룰 엔진에도 같은 감쇠폭이 적재된다(마이그레이션 0020,
`crop_growth_guide.risk_width`) — 두 구현의 점수가 갈리면 안 되는 계약이다.
산포도를 낼 수 없는 지표(`temp_night_min`, `rainfall_daily`)는 NULL로 두고 종전 완충폭으로
폴백한다 — 척도를 지어내지 않는다.

계약 검증:

```powershell
python outcomes/scripts/ml/test_crop_literature_anchor.py
python outcomes/scripts/ml/test_imputation.py
```

점수는 문헌 기준 대비 점진 편차 점수이며, 성과 예측이나 ML 정확도 주장이 아니다.
