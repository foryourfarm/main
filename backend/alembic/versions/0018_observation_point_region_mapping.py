"""관측지점 → 구역 매핑 컬럼 추가 (MappingReport.md §6.4)

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-26

왜 필요한가: 관측망이 두 계층인데 **지점코드가 서로 조인되지 않는다.**

| 계층 | 관측망 | 지점 수 | 코드 형식 | 역할 |
|---|---|---|---|---|
| 1차 | 농업기상(농진청) | 216 | `230802A001` | 주 데이터원. 일사량·일조시간이 여기에만 있다 |
| 2차 | 기상청 AWS | 534 | `108` | 1차의 결측 보완 + 농업기상 지점 없는 구역 커버 |

따라서 "농업기상이 비면 AWS로 채운다"를 성립시키는 연결 키는 지점코드가 아니라
**region_id**다. 그 배정 결과를 담을 자리가 없어서 추가한다.

`network`를 두는 이유: 두 관측망이 구분 없이 섞이면 결측 보완 로직이 "지금 1차인지 2차인지"를
판단할 수 없다. 코드 체계가 다른 데이터를 한 테이블에 넣을 때는 구분자가 필요하다.

`region_id`가 NULL 허용인 이유: 배정에 실패하는 지점이 실제로 있다(예: 독도·격렬비도 등
행정구역 격자 밖 도서, `동방로거테스트` 같은 테스트 지점). NOT NULL로 묶으면 적재가
통째로 실패한다 — 배정 못 한 지점은 NULL로 두고 조회에서 제외한다(§12).
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE kma_observation_point
            ADD COLUMN region_id INTEGER REFERENCES region(id),
            ADD COLUMN network   VARCHAR(16) NOT NULL DEFAULT 'kma_aws',
            ADD COLUMN nx        INTEGER,
            ADD COLUMN ny        INTEGER;

        COMMENT ON COLUMN kma_observation_point.region_id IS
            '지점이 속한 시군구. NULL이면 배정 실패(행정구역 격자 밖 도서·테스트 지점).';
        COMMENT ON COLUMN kma_observation_point.network IS
            '관측망: agri=농업기상(1차, 일사량 보유) / kma_aws=기상청 AWS(2차, 결측 보완).';
        COMMENT ON COLUMN kma_observation_point.nx IS
            '기상청 격자 X. 구역-지점 거리 계산용(위경도 대신 정수 격자로 비교 — 농업기상 지점은 위경도가 없다).';

        -- 구역별 지점 조회가 주 질의 패턴이다(구역 → 그 구역 지점들).
        CREATE INDEX ix_observation_point_region ON kma_observation_point (region_id, network);
        -- 격자 거리 최근접 탐색용(구역에 지점이 없을 때 인접 지점을 찾는다).
        CREATE INDEX ix_observation_point_grid ON kma_observation_point (nx, ny);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS ix_observation_point_region;
        ALTER TABLE kma_observation_point
            DROP COLUMN IF EXISTS network,
            DROP COLUMN IF EXISTS region_id;
        """
    )
