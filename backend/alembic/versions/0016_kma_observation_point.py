"""기상청 관측지점(AWS/지상) 마스터 테이블 (DB.md §3.3 인접)

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-26

`kma_observation_point`: 기상청 관측지점 번호(STN) → 지점명·위경도·고도. 과거 실측
기상(일통계) 조회 시 지점 식별과 region 매핑에 쓴다(app/models/kma_observation_point.py).

**시드는 이 파일에 넣지 않는다.** 지점이 500여 개라 마이그레이션에 INSERT를 박으면
파일이 비대해지고, 무엇보다 앞선 리뷰에서 지적된 대로 "일부만 넣고 나머지는 나중에"가
되면 마이그레이션이 스스로 미완성 데이터를 적재한다(CLAUDE.md §10 — 마스터 데이터는
마이그레이션/시드로 적재하되 부분 샘플은 금지). `district`(5,066행)가 이미
`scripts/load_districts.py` + CSV 패턴을 쓰므로 지점 시드도 같은 방식으로 별도 PR에서
적재한다 — 출처는 기상청 지점정보(AWS/ASOS 지점 목록).

Revises가 0013인 이유: 원래 사이에 있던 0014(region_grid 시드)를 폐기했다. region_grid는
좌표를 계산해 채우는 대신 기상청 배포 격자 엑셀에서 만든 `docs/seed/region_grid_seed.csv`를
`scripts/load_region_grid.py`가 256/256 적재한다(계산기는 격자 경계 41건이 어긋난다 —
`scripts/gen_region_grid_seed.py` docstring 참고).
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE kma_observation_point (
            point_code  VARCHAR(10) PRIMARY KEY,
            name        VARCHAR(100) NOT NULL,
            lat         DOUBLE PRECISION NOT NULL,
            lon         DOUBLE PRECISION NOT NULL,
            altitude    INTEGER NOT NULL
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS kma_observation_point;")
