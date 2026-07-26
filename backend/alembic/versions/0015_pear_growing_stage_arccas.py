"""배 생육기 범위를 ARCCAS 공식 기준(4~10월)으로 확장 (outcomes/ ML 이관 반영)

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-26

`outcomes/memory/crop_rules/pear.json`(별도 ML 프로젝트 산출물, PR 논의로 반입 여부 확정)이
농업·농촌 기후정보시스템(ARCCAS) 재배적지 지표를 근거로 배 생육기를 4~10월로 명시한다.
온도 기준값(적지 18.5~21.5℃·가능지 17~23℃)은 기존 시드(0004, 농사로 안내책자)와
**이미 정확히 일치** — 값은 그대로 두고, 두 출처가 교차 확인됐다는 사실만 source_ref에 남긴다.

생육기 범위(day_of_year)만 5/1~10/20(121~293) → 4/1~10/31(91~304)로 넓힌다.
0007 시드가 "세포분열기~과실비대기 5월상~10월중"으로 잡은 것보다 ARCCAS 공식 자료가
한 달 가까이 더 이르게(4월초) 시작을 잡고 있어 — 4월 적합도가 지금은 '제철 아님'으로
잘못 판정되고 있었다.

사과(crop_id=1)는 이번에 반영하지 않는다 — ARCCAS 단일 생육기 기준(14.5~18.5℃)이 기존
농사로 단계별 세분값(결실비대기/착색기/성숙기, 서로 다른 목표온도)과 성격이 달라 교체·병행
여부가 미결정([확인 필요], nexttodo.md).
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_SOURCE = "농촌진흥청 농사로 작물별 안내책자(0004 시드)"
NEW_SOURCE = (
    "농촌진흥청 농사로 작물별 안내책자(0004 시드) — 농업·농촌 기후정보시스템(ARCCAS) "
    "재배적지 지표(생육기기온 적지 18.5~21.5℃, 가능지 17~23℃)와 교차 확인됨"
)


def upgrade() -> None:
    op.execute(
        """
        UPDATE crop_growth_stage
           SET range_start = 91, range_end = 304
         WHERE crop_id = 2 AND growth_stage = 'growing';

        UPDATE crop_growth_guide
           SET source_ref = %(new)s
         WHERE crop_id = 2 AND growth_stage = 'growing' AND indicator = 'temp_day';
        """
        % {"new": f"'{NEW_SOURCE}'"}
    )


def downgrade() -> None:
    op.execute(
        f"""
        UPDATE crop_growth_stage
           SET range_start = 121, range_end = 293
         WHERE crop_id = 2 AND growth_stage = 'growing';

        UPDATE crop_growth_guide
           SET source_ref = '{OLD_SOURCE}'
         WHERE crop_id = 2 AND growth_stage = 'growing' AND indicator = 'temp_day';
        """
    )
