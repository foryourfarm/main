"""감자 tuber 상한을 120 → 112일로 좁혀 8월 오채점을 없앤다 (2026-08-02)

Revision ID: 0026
Revises: 0025
Create Date: 2026-08-02

**왜**: 감자 온도 문헌은 달력월(춘작 3~6월) 기준인데 `crop_growth_stage`는 파종후경과일
기준이라 두 축이 어긋난다는 지적이 있었다([확인 필요], 0019가 미룬 건). 축을 바꾸는 대신
어긋남 크기를 먼저 쟀더니(2026-08-02) **원인이 축이 아니라 상한값이었다.**

측정: 현실적 춘작 파종창(3/20~4/10)에서 문헌 3~6월 밖으로 새는 달

    tuber 46~120일(종전)  [7] [7] [7,8] [7,8]
    tuber 46~112일(이번)  [7] [7] [7]   [7]

**120일에 문헌 근거가 없다.** 리포 안에서 감자 전체 생육기간을 숫자로 말한 곳은 한 곳뿐이고
그 값이 90~100일이다 — `data/potato/[서류][감자][일반] 감자의 생장과 발육.txt:122`
"감자의 전체 생육기간을 90-100일로 보았을 때". 시드 0007 주석도 "전체 생육 90~100일
**+ 버퍼**"라고 스스로 패딩임을 적어놨다. 120일은 3/20 파종 시 7/18까지 밭에 있다는 뜻인데,
같은 교본이 "봄감자 재배는 장마 이전에 모두 수확을 완료하는 것이 좋다"(:155)고 한다.

**112일을 고른 근거**: 농사로 농작업일정이 춘작 수확을 `[6월하]`로 적으면서 `[7월상]`도
병기한다. 늦은 수확까지 인정하는 값이 3/20 파종 기준 7월 상순 종료 = **112일**이다
(2026-08-02 팀 결정). 문헌 상한 100일보다 12일 여유가 있지만 그 12일은 농작업일정이
명시한 `[7월상]`에서 나온 것이고, 종전 120일처럼 근거 없는 패딩이 아니다.

**증상이 뭐였나**: 7~8월은 이미 수확한 시점인데 `tuber` 밴드(낮기온 optimal 23~24 /
allowed ~27)로 계속 채점됐다. 7월 평년 25~26℃가 허용구간으로 밀려 81~90점이 나온다 —
**이미 캔 밭이 여름 더위로 감점당한다.** 112일로 8월은 사라지고, 남는 7월은 농작업일정이
수확기로 인정하는 달이라 채점 대상으로 두는 것이 맞다.

`early`(0~45일)는 건드리지 않는다 — 같은 교본이 "싹의 출현기간이 일반적으로 30-45일"(:122)
이라고 해서 근거가 있다.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD, _NEW = 120, 112


def upgrade() -> None:
    op.execute(
        f"UPDATE crop_growth_stage SET range_end = {_NEW} "
        f"WHERE crop_id = 4 AND growth_stage = 'tuber'"
    )


def downgrade() -> None:
    op.execute(
        f"UPDATE crop_growth_stage SET range_end = {_OLD} "
        f"WHERE crop_id = 4 AND growth_stage = 'tuber'"
    )
