# 5작물 채점 이관 계약

2026-08-01 갱신. ForYourFarm에 전달할 5작물(사과·배·상추·감자·오이) 채점 규칙, 실행 코드, 검증 산출물의 복사본이다.

- `memory/crop_rules/`: 공통 규칙과 작물별 규칙 JSON.
- `memory/indicator_dispersion.json`: 실측 분포 기반 위험구간 감쇠폭.
- `scripts/ml/`: 로그 채점 곡선, KNN 결측 대체, 산포도·앵커·지역 점수 생성기와 회귀검사.
- `AnswerData.csv`, `RegionalScore.csv`, `data/ml/crop_literature_anchor_experiment.csv`: FarmML 데이터로 재생성한 계약 산출물.

연구 산출물은 FarmML 루트에서 다음 순서로 재생성한다.

```powershell
python scripts/ml/build_indicator_dispersion.py
python scripts/ml/crop_literature_anchor_experiment.py
python scripts/ml/build_answer_data.py
python scripts/ml/build_regional_score.py
python scripts/ml/test_crop_literature_anchor.py
python scripts/ml/test_imputation.py
```

이관 복사본은 다음 명령으로 검증한다.

```powershell
python outcomes/scripts/ml/test_crop_literature_anchor.py
python outcomes/scripts/ml/test_imputation.py
```

채점은 문헌 밴드 대비 점진 편차 점수다. 최적구간 100점, 최적구간 직후 95점, 허용경계 60점이며 위험구간은 `risk_width`까지 로그 감쇠한다. 결측치는 원시값 공간 거리역수 가중 KNN으로 대체하고 방법·출처를 `RegionalScore.csv`에 남긴다.

`outcomes/`는 수동 이관 경계다. ForYourFarm은 FarmML의 `data/`, `memory/`, `scripts/`를 직접 import하지 않고 검증된 이 디렉터리만 복사해 사용한다.
