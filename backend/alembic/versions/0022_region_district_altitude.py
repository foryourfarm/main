"""구역·법정동 대표 고도 컬럼 추가 (2026-08-01).

**왜**: 기온은 고도에 직접 지배된다(환경감률 약 0.65℃/100m). 고도를 모르면 두 곳이 깨진다.
  1. 평년치 도너를 수평거리로만 고른다 — 서귀포시는 한라산 지점과 해안 지점이 같은 후보에
     들어 도너 고도 산포가 1,524m였다. 지점쌍 실측에서 고도차 200~500m면 MAE 2.29℃,
     500m 넘으면 5.07℃다.
  2. 구역 평년치를 잘 만들어도 밭이 중산간 400m면 여전히 2.6℃ 틀린다. 우리는 토양 때문에
     이미 읍면동(법정동 말단)까지 받고 있어서 밭 위치를 시군구보다 훨씬 좁게 안다 —
     기온만 해상도가 낮게 남아 있었다.

값은 마이그레이션에 박지 않고 시드에서 적재한다(district가 20,275행이라 INSERT를 박을 수
없고, 좌표원을 나중에 법정구역 SHP로 갈아끼울 예정이기 때문이다).
    생성: scripts/gen_altitude_seed.py  → docs/seed/{region,district}_altitude_seed.csv
    적재: scripts/load_altitudes.py

`district.altitude_source`가 필요한 이유: 리(里)는 소속 읍·면 대표점을, 도시 법정동(3,152건)은
시군구 대표점을 빌려 쓴다. 어느 쪽인지 데이터에 남지 않으면 근사를 실측처럼 쓰게 된다(§18-4).

**`weather_climatology.reference_altitude_m`이 따로 필요한 이유**: 감률 보정은
`밭 고도 - 그 평년치가 대표하는 고도`라 기준선이 틀리면 보정이 오히려 오차를 키운다.
구역 대표점을 기준선으로 쓰면 안 된다 — 실측 비교(농업기상 114구역, 관측지점 고도 vs
구역 대표점)에서 MAE 40m·p90 92m·**최대 370m(남원시: 지점 474m vs 대표점 104m)**였다.
370m는 2.4℃라 "보정"이 그만큼 틀어놓는다. 그래서 기준 고도를 행마다 실어 ETL이 정확히
채운다(농업기상=집계에 들어간 읍면동 고도 평균, AWS=도너 지점 고도의 거리가중 평균).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 정수 m로 충분하다 — SRTM 30m의 검증 오차가 MAE 8.8m라 소수점은 없는 정밀도다.
    op.add_column("region", sa.Column("altitude_m", sa.Integer(), nullable=True))
    op.add_column("district", sa.Column("altitude_m", sa.Integer(), nullable=True))
    op.add_column("district", sa.Column("altitude_source", sa.String(), nullable=True))
    op.add_column(
        "weather_climatology", sa.Column("reference_altitude_m", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("weather_climatology", "reference_altitude_m")
    op.drop_column("district", "altitude_source")
    op.drop_column("district", "altitude_m")
    op.drop_column("region", "altitude_m")
