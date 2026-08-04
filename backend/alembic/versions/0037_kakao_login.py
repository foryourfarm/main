"""카카오 로그인 — `users.kakao_id` + 이메일·비밀번호 NULL 허용.

**기존 인증 축을 그대로 쓴다.** 분리 토큰(access 본문 / refresh httpOnly 쿠키)은 손대지 않고,
"이 계정이 누구인지"를 확인하는 방법만 하나 늘어난다(docs/auth-security.md).

`email`·`password_hash`를 NULL 허용으로 푸는 이유: **카카오 계정에는 둘 다 없다.**
  - 비밀번호가 없다 — 카카오가 본인 확인을 대신한다.
  - 이메일을 **받지 않는다**(동의항목 검수 대상이기도 하지만 그것과 별개 결정이다). 받아서
    `email` 컬럼에 넣으면 같은 이메일의 기존 계정과 UNIQUE 충돌이 나고, 충돌을 "같은 사람"으로
    이어붙이면 카카오 이메일이 미인증일 때 계정 탈취 경로가 된다. 안 받으면 그 문제가 아예
    생기지 않는다 — 카카오 계정은 `kakao_id`로만 식별한다.

NULL을 허용해도 UNIQUE는 남긴다 — Postgres UNIQUE는 NULL 중복을 허용하므로 카카오 계정이
여러 개여도 충돌하지 않고, 이메일 계정의 중복 방지는 그대로 유효하다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0037"
down_revision: str | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("kakao_id", sa.BigInteger(), nullable=True))
    # 한 카카오 계정이 우리 계정 두 개가 되지 않게 DB가 막는다 — 동시 요청 두 개가
    # 애플리케이션 검사(있으면 재사용)를 함께 통과해도 여기서 걸린다.
    op.create_unique_constraint("uq_users_kakao_id", "users", ["kakao_id"])
    op.alter_column("users", "email", existing_type=sa.String(), nullable=True)
    op.alter_column("users", "password_hash", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    # 카카오 계정(email/password_hash가 NULL인 행)을 지운 뒤에야 NOT NULL을 되돌릴 수 있다.
    # 조용히 실패하지 않게 순서를 지킨다.
    op.execute("DELETE FROM users WHERE kakao_id IS NOT NULL")
    op.alter_column("users", "password_hash", existing_type=sa.String(), nullable=False)
    op.alter_column("users", "email", existing_type=sa.String(), nullable=False)
    op.drop_constraint("uq_users_kakao_id", "users", type_="unique")
    op.drop_column("users", "kakao_id")
