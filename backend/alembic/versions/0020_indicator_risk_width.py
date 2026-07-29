"""지표별 위험구간 감쇠폭(risk_width) 컬럼 추가 및 적재 (2026-07-29).

**왜**: 채점 곡선의 위험구간(허용경계 밖) 감쇠 거리를 종전엔 완충폭(허용~최적 간격) 1배로
잡았다. 완충폭은 `allowed = optimal 폭 ±50%` 휴리스틱에서 나오므로 optimal이 좁은 지표는
완충폭도, 위험구간도 함께 좁아졌다 — 3중 압축이라 채점이 사실상 이진이 됐다.
outcomes 산출물에서 측정한 결과(150지역): 상추 pH 0점 107건, 사과 기온 0점 92건,
상추 Ca 0점 56건. 감쇠폭을 전국 실측 산포도로 바꾼 뒤 각각 44 / 35 / 6건으로 줄었다.

**값의 출처**: `outcomes/scripts/ml/build_indicator_dispersion.py`가 실측 데이터
(`data/01_soil_chemistry_modified.csv` 103~126지역, `data/03_weather_monthly_modified.csv`
2025년 150지역)에서 산출한 `risk_width = 2.0 x robust_sd`, `robust_sd = 1.4826 x MAD`.
표준편차 대신 robust 추정치를 쓴 이유: 유효인산 실측 최대 1288mg/kg(시설재배 인산 과다
축적, 실재값)이 표준편차를 부풀린다. 이상치 하나가 전국 채점 척도를 늘려선 안 된다.
전체 근거는 `outcomes/memory/indicator_dispersion.json`.

**한계 [확인 필요]**
- 배수 2.0은 문헌 근거가 아니라 명시적 휴리스틱이다(정규 가정에서 전국 지역 약 95% 포함
  폭). 실제 감수 곡선 문헌 확보 시 교체 대상.
- `temp_day`는 작물별 앵커월 산포도(2.00~2.89℃)의 평균 하나를 전 작물에 쓴다. 작물별
  분리가 더 정확하지만, crop_id 매핑을 잘못 짚는 위험보다 단일값 근사를 택했다.
- `temp_night_min`·`rainfall_daily`는 지역간 산포도를 낼 실측이 없어 NULL로 둔다 →
  룰 엔진이 종전 완충폭 기준으로 폴백한다. 숨기지 않고 명시한다.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# indicator → risk_width. 출처는 모듈 docstring.
RISK_WIDTH = {
    "ph": 0.4641,
    "organic": 9.2069,
    "p2o5": 275.3322,
    "k": 0.5041,
    "ca": 3.7777,
    "mg": 1.2632,
    "temp_day": 2.2408,
}

SOURCE_NOTE = (
    "risk_width=2.0 x robust_sd(1.4826 x MAD), 전국 실측 산포도. "
    "출처 outcomes/memory/indicator_dispersion.json (2026-07-29)"
)


def upgrade() -> None:
    op.add_column("crop_growth_guide", sa.Column("risk_width", sa.Numeric(), nullable=True))
    op.add_column("crop_growth_guide", sa.Column("risk_width_source", sa.String(), nullable=True))
    bind = op.get_bind()
    for indicator, width in RISK_WIDTH.items():
        bind.execute(
            sa.text(
                "UPDATE crop_growth_guide SET risk_width = :w, risk_width_source = :s "
                "WHERE indicator = :i"
            ),
            {"w": width, "s": SOURCE_NOTE, "i": indicator},
        )


def downgrade() -> None:
    op.drop_column("crop_growth_guide", "risk_width_source")
    op.drop_column("crop_growth_guide", "risk_width")
