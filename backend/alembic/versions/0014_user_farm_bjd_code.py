"""user_farm에 읍면동(bjd_code) 보존 — 설정 화면의 밭 수정에 필요 (DB.md §3.7)

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-26

지금까지 읍면동은 등록 시점에만 쓰이고(토양 기준값 조회 키) 어디에도 남지 않았다. 그래서
설정 화면에서 "이 밭의 읍면동이 어디였는지"를 보여줄 수도, 지역을 바꿀 때 새 읍면동을
고른 결과를 유지할 수도 없다. 밭의 위치는 (시/군, 읍면동) 한 쌍이 온전한 사실이므로 저장한다.

기존 행 backfill: `soil_state.base_source` 문구에 조회에 쓴 읍면동 코드가 남아 있어 거기서
뽑는다. 단 통합 지역은 "통합전코드"가 박혀 있어 district 마스터에 없을 수 있으므로
존재하는 코드만 채운다(FK 위반 방지). 못 채운 행은 NULL — 유저가 설정에서 다시 고르면 된다.
그래서 NOT NULL로 걸지 않는다(과거 행을 추측으로 메우지 않는다, §18-4).
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE user_farm ADD COLUMN bjd_code CHAR(10) REFERENCES district(bjd_code);

        UPDATE user_farm uf
           SET bjd_code = substring(ss.base_source from '읍면동 ([0-9]{10})')
          FROM soil_state ss
         WHERE ss.user_farm_id = uf.id
           AND substring(ss.base_source from '읍면동 ([0-9]{10})') IS NOT NULL
           AND EXISTS (
                 SELECT 1 FROM district d
                  WHERE d.bjd_code = substring(ss.base_source from '읍면동 ([0-9]{10})')
               );
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE user_farm DROP COLUMN bjd_code;")
