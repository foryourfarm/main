"""상추 작기(봄·가을)를 생육단계로 세워 작기 밖 월을 dormant 처리 (2026-08-02)

Revision ID: 0025
Revises: 0024
Create Date: 2026-08-02

**왜**: 상추는 `crop_growth_stage` 행이 0개라 기상 지침(temp_day)이 전기간(NULL)에 붙어
1~12월 12칸이 전부 채점됐다. 노지 상추를 1월에 심지 않는데 1월 칸에 낮은 점수가 뜨면
"이 달엔 상추가 안 좋다"로 읽힌다 — 심지 않는 달이라는 사실이 점수로 둔갑한다.
사과는 이미 겨울이 `dormant`(점수 숨김)로 나오므로 두 작물의 동작이 갈려 있었다.

0019가 "단계 행을 새로 만들면 윤년 경계버그 위험만 생기고 실익이 없다(YAGNI)"고 판단해
미뤘던 건인데, FarmML이 2026-08-01에 상추 채점월을 작기로 좁히면서(총점 45.7 → 72.2)
실익이 생겼다. 윤년 우려는 여기선 무해하다 — 경계가 3/1·6/30·8/1·11/30이라 윤년에
±1일 밀려도 작기 한가운데가 아니라 이미 여유가 있는 끝단이다.

**축을 달력월로 잡은 이유**(파종후경과일 아님, 2026-08-02 팀 결정):
- 상추는 작기 30~60일로 짧고 봄·가을 연 2회 재배한다. `user_farm.planting_date` 하나로는
  그 반복을 표현할 수 없다(감자가 파종후경과일로 되는 건 춘작 1회라서다).
- 장기 탭을 "앞으로 3개월"로 좁히는 안이 논의 중인데, 그 창은 달력 기준으로 슬라이드한다.
  파종후경과일 축이면 유저가 파종일을 갱신하지 않은 순간 창 3칸이 통째로 비어버린다.
- 사과·배가 이미 `day_of_year`라 축이 하나로 모인다.

**구간 폭**: 3~6월 / 8~11월. FarmML은 4·5·9·10월을 썼지만 그건 작기 한가운데만 짚은
휴리스틱이고 FarmML 자신이 문헌 근거 없음을 명시했다(상추 교본 264p 미처리). 실제 노지
상추는 3월 정식·6월 수확, 8월 정식·11월 수확까지 가므로 넉넉히 잡고, 진짜 못 심는
한여름·한겨울(7·12·1·2월)만 작기 밖으로 둔다. **이 범위 자체가 문헌 근거 없는 휴리스틱**
이라는 사실은 `suitability_service.LETTUCE_SEASON_LIMITATION`으로 화면에 표기한다(§18-4).

토양 지침(ph·p2o5·k·ca·mg)은 전기간(NULL)에 그대로 둔다 — 작기 밖에도 토양은 존재하고,
기상 지표가 0개인 달을 `dormant`로 접는 것은 `derive_status`가 이미 하는 일이다.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 비윤년 DOY. 3/1=60, 6/30=181, 8/1=213, 11/30=334 (0007과 같은 기준).
_SPRING = (60, 181)
_FALL = (213, 334)


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO crop_growth_stage
            (crop_id, growth_stage, mode, range_start, range_end, priority)
        VALUES
            (5, 'spring', 'day_of_year', {_SPRING[0]}, {_SPRING[1]}, 1),
            (5, 'fall',   'day_of_year', {_FALL[0]},   {_FALL[1]},   2);

        -- 전기간 temp_day 1행을 두 작기로 복제한다. 값·근거·감쇠폭을 손으로 옮겨 적으면
        -- 0019/0020/0021이 갱신한 내용과 어긋나므로 그 행에서 그대로 SELECT 한다.
        INSERT INTO crop_growth_guide
            (crop_id, growth_stage, indicator, optimal_min, optimal_max,
             allowed_min, allowed_max, weight, risk_width, risk_width_source,
             source_ref, confidence)
        SELECT crop_id, 'fall', indicator, optimal_min, optimal_max,
               allowed_min, allowed_max, weight, risk_width, risk_width_source,
               source_ref, confidence
        FROM crop_growth_guide
        WHERE crop_id = 5 AND indicator = 'temp_day' AND growth_stage IS NULL;

        UPDATE crop_growth_guide SET growth_stage = 'spring'
        WHERE crop_id = 5 AND indicator = 'temp_day' AND growth_stage IS NULL;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM crop_growth_guide
        WHERE crop_id = 5 AND indicator = 'temp_day' AND growth_stage = 'fall';

        UPDATE crop_growth_guide SET growth_stage = NULL
        WHERE crop_id = 5 AND indicator = 'temp_day' AND growth_stage = 'spring';

        DELETE FROM crop_growth_stage WHERE crop_id = 5;
        """
    )
