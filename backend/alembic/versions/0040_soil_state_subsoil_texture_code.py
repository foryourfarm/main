"""soil_state.subsoil_texture_code 신설 — 심토토성 원본 등급코드 보존 (finalplan.md P1).

**왜**: `soil_profile_client.get_soil_profile`이 흙토람 심토단면정보 API의
`Deepsoil_Qlt_Code`("01"~"06"/"99")를 한글 텍스트(`DEEPSOIL_TEXTURE`)로 바꾸면서 원본 코드를
버리고 있었다(`:43`). `crop_growth_guide.code_scores`(마이그레이션 0038, 등급코드→점수
배점표)는 한글이 아니라 등급코드로 조회하므로 원본을 보존할 컬럼이 필요하다.

기존 `soil_state.soil_texture`(한글, `chat_service`가 씀)는 그대로 둔다 — 이 컬럼은 그 대체가
아니라 채점용 원본 코드를 **추가로** 보존하는 것이다.

**자료형**: smallint. 값은 1~6 또는 99(기타)만 허용한다. API가 주는 코드는 2자리 문자열
("01"~"06"/"99")인데 `code_scores` JSONB 키는 "1"~"6"/"99"(선행 0 없음)라 정규화(선행 0 제거)
후 정수로 저장한다 — 정규화 위치는 `soil_profile_client._normalize_texture_code`(API 응답을
받는 시점, DB에 들어가기 전)다. 목록 밖 코드는 추측하지 않고 None으로 둔다.

**🔴 적재 배선은 이 마이그레이션의 범위 밖이다.** `get_soil_profile`은 PNU(19자리 지번코드)를
요구하는데 `user_farm`에는 `bjd_code`(법정동코드)만 있어 **호출자가 지금 0건**이다. 즉 이
컬럼은 컬럼·모델만 먼저 두는 것이고 당장 프로덕션에서 채워지지 않는다. 새 호출 경로를 만드는
것은 계획에 없는 별도 작업이라 여기서 손대지 않는다 — 이 사실을 다음 사람이 착각하지 않게
컬럼·모델 주석에도 남긴다.

CHECK 제약은 `code_scores` 배점표가 아는 값 밖의 코드가 조용히 들어오는 것을 막는다
(값이 있는데 배점표에 없는 키로 조회되면 채점이 조용히 스킵될 수 있다).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0040"
down_revision: str | None = "0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ALLOWED_CODES_SQL = "1, 2, 3, 4, 5, 6, 99"


def upgrade() -> None:
    op.add_column(
        "soil_state", sa.Column("subsoil_texture_code", sa.SmallInteger(), nullable=True)
    )
    op.execute(
        "ALTER TABLE soil_state ADD CONSTRAINT ck_soil_state_subsoil_texture_code "
        f"CHECK (subsoil_texture_code IS NULL OR subsoil_texture_code IN ({_ALLOWED_CODES_SQL}))"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE soil_state DROP CONSTRAINT IF EXISTS ck_soil_state_subsoil_texture_code"
    )
    op.drop_column("soil_state", "subsoil_texture_code")
