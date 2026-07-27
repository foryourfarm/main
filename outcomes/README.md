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

산출물 재생성은 원시 데이터가 있는 FarmML 루트에서 실행한다.
두 스크립트가 `scripts/ml/scoring.py`를 import 하므로 그쪽에도 같은 파일이 있어야 한다:

```powershell
python scripts/ml/build_answer_data.py
python scripts/ml/crop_literature_anchor_experiment.py
python scripts/ml/build_regional_score.py
python scripts/ml/test_crop_literature_anchor.py
```

ForYourFarm 이관 후 계약 검증:

```powershell
python outcomes/scripts/ml/test_crop_literature_anchor.py
```

점수는 문헌 기준 대비 점진 편차 점수이며, 성과 예측이나 ML 정확도 주장이 아니다.
