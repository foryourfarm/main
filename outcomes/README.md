# 사과·배 온도 채점 이관 로직

2026-07-25 생성. 메인 프로젝트에 적용할 실행 규칙과 산출물만 담은 복사본이다.

- `memory/crop_rules/`: 기계가 읽는 적용 규칙 JSON. 사과 적지 14.5~18.5℃/가능지 13.5~19.5℃, 배 적지 18.5~21.5℃/가능지 17~23℃.
- `scripts/ml/`: 앵커, 점수 생성 스크립트, 회귀검사.
- `AnswerData.csv`, `data/ml/`, `RegionalScore.csv`: 현재 산출 결과.

재생성 순서:

```powershell
python scripts/ml/build_answer_data.py
python scripts/ml/crop_literature_anchor_experiment.py
python scripts/ml/build_regional_score.py
python scripts/ml/test_crop_literature_anchor.py
```

점수는 문헌 기준 대비 점진 편차 점수이며, 성과 예측이나 ML 정확도 주장이 아니다.
