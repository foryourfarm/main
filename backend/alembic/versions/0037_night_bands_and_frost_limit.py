"""야간 최저기온 밴드 전량 적용 + 사과 서리 극값 + 감자 pH 노지/시설 2행 (2026-08-05).

세 갈래를 한 마이그레이션에 담는다 — 전부 `0036`이 만든 성격 컬럼을 처음으로 실제로 쓰는
행이라 따로 올리면 "왜 이 컬럼이 필요했나"가 흩어진다.

────────────────────────────────────────────────────────────────────────────
1. 야간 최저기온 밴드 — 오이·상추 신설 (문헌 확보분 전량)
────────────────────────────────────────────────────────────────────────────
`temp_night_min`은 소스가 이미 배선돼 있다(`weather_climatology.temp_night_min_normal`,
AWS 관측망 534지점으로 PR #68·#69에서 채워짐 / 단기 탭은 `aws_daily_client.ta_min`·
`forecast_client.TMN`). 그런데 **지침 행이 사과 착색기·감자 비대기 2건뿐**이라 나머지
작물은 값이 있어도 채점되지 않았다 — 문제정의서가 지목한 실패 원인(봄 야간 저온)이
정작 대부분의 작물에서 총점에 나타나지 않는 상태였다.

문헌이 야간 밴드를 주는 작물을 전수 확인해 **오이·상추 2건을 신설한다.**

| 작물 | 값 | 출처 |
|---|---|---|
| 오이 | 15~18℃ | RDA 농업기술길잡이 107 「오이」 표5+본문 (주간 22~28 / 야간 15~18 / 주야차 7~10) |
| 상추 | 10~15℃ | RDA 농업기술길잡이 023 「상추」 — "잎의 분화는 주간보다 **야간 온도의 영향을
             많이 받는다**. 10~15℃에서 가장 활발" (10℃↓·15℃↑ 모두 분화 정지) |

🔴 **배는 만들지 않는다.** 배 교본이 주는 야간 수치는 「겨울철 최저기온 -20℃ 전후에서 언
피해 위험 상존」뿐이다 — 휴면기 동해 경고이지 생육 최적 밴드가 아니다. 없는 밴드를
±50%로 지어내지 않는다.

⚠️ **`risk_width`는 전부 NULL로 둔다**(룰 엔진이 완충폭 1배로 폴백). `0020`이 심은 실측
산포도는 `temp_day`까지이고, 야간 산포도를 낼 원천이 지금 없다 —
`data/03_weather_monthly_modified.csv`는 `avg_temp`·`precipitation` 2컬럼뿐이고
`temp_night_min_normal`은 DB에만 있다. 척도를 지어내지 않는다.
(상추 야간산포도 보류는 2026-08-05 사용자 지시이기도 하다. 상세 논의는 MergeReport.md)

⚠️ **weight는 휴리스틱이다** — 문헌이 가중치를 주지 않는다. 상추는 문헌이 "야간이 주간보다
영향이 크다"고 명시하므로 `temp_day`와 같은 2.0을, 오이는 그런 서술이 없어 한 단계 낮은
1.5를 준다. 근거가 생기면 교체할 값이다.

────────────────────────────────────────────────────────────────────────────
2. 사과 서리 극값 — 문헌 2점으로 3밴드를 세운다
────────────────────────────────────────────────────────────────────────────
`생육 최적 구간`과 `서리 임계`는 성격이 다르다 — 전자는 "잘 자라는 온도", 후자는 "죽는
온도"다. 지금까지 우리 지침에는 후자가 없었다.

사과만 **한 생육단계에 대해 2점이 다 있다**:
- 만개 동해 한계 **−1.7℃** (교본 표8-1, 늦서리 화기 피해 한계온도와도 일치)
- 만개기 90% 동사 **−3.9℃** (교본 표1-4, 10%는 −2.2℃)

→ `optimal_min = −1.7`(이 위로는 서리 피해 없음 = 100점) / `allowed_min = −3.9`
(`literature_limit` → **경계 0점**) / 그 사이는 기존 로그 곡선. `optimal_max`는 NULL —
야간이 따뜻한 것 자체는 서리 관점에서 감점 사유가 아니다(단측 밴드, `0030`과 같은 계약).

🔴 **배·감자는 만들지 않는다.**
- 배: 교본이 화총 −3.5 / 만개·유과 −1.7을 주는데 **서로 다른 생육단계**다. 한 단계의
  최적경계·허용경계 2점이 되지 않아 밴드를 세울 수 없다.
- 감자: 2026-08-05 사용자 지시로 제외. (근거상으로도 괴경 −1.4~−1.9는 지상부 −3와
  별개 지표이고, Boydston 2006이 **온도×시간 조합**으로 주어 단일 임계로 환원되지 않는다.)

🔴 **생육단계를 새로 만들지 않는다.** `crop_growth_stage`에 개화기가 없고(사과는
`fruit_growth` 111–263 / `coloring` 233–293 / `maturity` 294–314),
`growth_stage_service.pick_stage`는 단계를 **하나만** 고른다. `flowering`을 끼우면 그
창에서 사과 `temp_day` 행이 사라져 통째로 미채점이 된다. `fruit_growth`(4/21~9/20)가
만개 직후 서리 위험기를 포함하므로 그 단계에 얹는다 — 야간 −1.7℃ 미만은 실제로 4~5월에만
발생하므로 창이 넓은 것이 오작동을 만들지 않는다.

⚠️ **실효 범위**: 장기 탭이 보는 것은 **월 평년 최저기온**이라 −1.7℃가 거의 걸리지 않는다.
이 행이 실제로 작동하는 곳은 **단기 탭**(일 최저 실측·예보)이다. 장기에서 안 걸리는 것은
결함이 아니라 평년값의 해상도 문제다.

────────────────────────────────────────────────────────────────────────────
3. 감자 pH — 노지/시설 2행 공존
────────────────────────────────────────────────────────────────────────────
`0035`(FarmML 동기화)가 감자 pH를 **5.5~7.0**으로 갱신했다. 이 값은 RDA 처방 2010
개정증보판 p.49 「감자(**노지**재배)」에서 온 것인데, `0036`의 백필 규칙(crop 3·4·5의
화학성 = 시설)이 그 행을 `facility`로 칠했다 — **규칙은 맞지만 이 행에는 틀렸다.**

→ 기존 행을 `open_field`로 되돌리고, 처방 5차(2022) p83 **시설재배토양** 진단기준
5.5~6.2로 `facility` 행을 새로 넣는다. 우리 1차 목표가 노지이므로 채점은 노지 행이 쓴다
(`load_guides`가 `open_field`를 우선한다).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0037"
down_revision: str | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_HEURISTIC = (
    " 허용경계는 문헌값이 아니라 optimal 폭 ±50%로 만든 휴리스틱이다"
    "(allowed_min_kind/allowed_max_kind='heuristic')."
)

# ---------------------------------------------------------------------------
# 1) 야간 최저기온 신설
#    (crop_id, growth_stage, optimal_min, optimal_max, allowed_min, allowed_max, weight, source)
# ---------------------------------------------------------------------------
_CUCUMBER_NIGHT_SOURCE = (
    "RDA 농업기술길잡이 107 「오이」 표5 + 본문 — 생육적온 주간 22~28℃ / **야간 15~18℃**, "
    "주야간 온도차 7~10℃가 적당. wiki/research/papers/cucumber/rda-cucumber-handbook-107.md. "
    "⚠️ 교본의 온도 기준은 시설 재배를 전제로 서술되나 값 자체에 재배형 표기가 없어 "
    "cultivation_type은 open_field로 둔다(기온 행은 전부 노지 기준으로 다뤄 왔다). "
    "⚠️ weight 1.5는 휴리스틱이다 — 문헌이 가중치를 주지 않는다."
    + _HEURISTIC
)
_LETTUCE_NIGHT_SOURCE = (
    "RDA 농업기술길잡이 023 「상추」 — 잎 분화 최적 **야간 10~15℃**. 원문: \"잎의 분화는 "
    "주간 온도보다는 야간 온도의 영향을 많이 받는다. 10~15℃에서 잎의 분화가 가장 활발\"이며 "
    "10℃ 이하·15℃ 이상 **모두** 분화가 정지한다(양측 밴드가 맞는 근거). "
    "wiki/research/papers/lettuce/rda-lettuce-handbook-023.md. "
    "⚠️ weight 2.0은 휴리스틱이나 문헌이 야간 우위를 명시하므로 temp_day와 같은 값을 준다. "
    "⚠️ risk_width는 NULL이다 — 야간 산포도 적용 보류(2026-08-05 사용자 지시). "
    "완충폭 1배 폴백으로 채점된다."
    + _HEURISTIC
)

_NIGHT_ROWS: list[tuple[int, str, float, float, float, float, float, str]] = [
    (3, "growing", 15.0, 18.0, 13.5, 19.5, 1.5, _CUCUMBER_NIGHT_SOURCE),
    # 상추는 0025가 작기를 세워 spring/fall 2행 구조다 — 한쪽만 넣으면 나머지 작기가
    # 야간을 채점하지 못한다.
    (5, "spring", 10.0, 15.0, 7.5, 17.5, 2.0, _LETTUCE_NIGHT_SOURCE),
    (5, "fall", 10.0, 15.0, 7.5, 17.5, 2.0, _LETTUCE_NIGHT_SOURCE),
]

# ---------------------------------------------------------------------------
# 2) 사과 서리 극값
# ---------------------------------------------------------------------------
_APPLE_FROST = (-1.7, None, -3.9, None)
_APPLE_FROST_SOURCE = (
    "RDA 농업기술길잡이 05(개정8판, 2025) 「사과」 — 표8-1 만개(4월상~5월상) 동해 한계온도 "
    "**−1.7℃**(제8장 02 늦서리 화기 피해 한계온도와 같은 값) / 표1-4 만개기 **90% 동사 "
    "−3.9℃**(10%는 −2.2℃). wiki/research/papers/apple/rda-apple-handbook-2025.md. "
    "🔴 이 행은 생육 최적 구간이 아니라 **서리 임계**다 — optimal_min은 '가장 잘 자라는 "
    "온도'가 아니라 '이 위로는 서리 피해가 없는 온도'이고, allowed_min은 생리적 절대한계라 "
    "allowed_min_kind='literature_limit'(경계 0점)이다. "
    "optimal_max가 NULL인 것은 의도다 — 야간이 따뜻한 것은 서리 관점에서 감점 사유가 아니다. "
    "⚠️ 표1-4는 원문이 미국 자료임을 밝히고 있고 '30분 견디는 한계온도' 기준이다. "
    "⚠️ 단계를 fruit_growth(111~263일)에 얹은 것은 crop_growth_stage에 개화기가 없고 "
    "pick_stage가 단계를 하나만 고르기 때문이다 — flowering을 신설하면 그 창에서 사과 "
    "temp_day가 통째로 미채점이 된다. "
    "⚠️ 장기 탭은 월 평년 최저기온을 보므로 이 임계가 거의 걸리지 않는다. 실효는 단기 탭."
)

# ---------------------------------------------------------------------------
# 3) 감자 pH 노지/시설
# ---------------------------------------------------------------------------
_POTATO_PH_FACILITY = (5.5, 6.2, 5.15, 6.55)
_POTATO_PH_FACILITY_SOURCE = (
    "RDA 「작물별 비료사용처방」 5차 개정본(2022) p83 시설재배토양 진단기준표 pH 5.5~6.2. "
    "wiki/research/papers/common/rda-fertilizer-prescription-5th-2022.md. "
    "이 행은 시설 기준이라 현재 채점에 쓰이지 않는다 — load_guides가 open_field를 우선한다. "
    "향후 시설 재배 확장 시를 위한 것이다."
    + _HEURISTIC
)
_POTATO_PH_OPEN_FIELD_NOTE = (
    " 🔵 2026-08-05(0037): 이 행은 RDA 처방 2010 개정증보판 p.49 「감자(**노지**재배)」 "
    "pH(1:5) 5.5~7.0이므로 cultivation_type을 open_field로 정정했다 — 0036의 백필 규칙"
    "(crop 3·4·5 화학성=시설)이 일반 규칙으로는 맞지만 이 행에는 틀렸다. "
    "🔴 상한 7.0은 더뎅이병 구간을 포함한다: 김점순 2012에서 pH 6.49일 때 발병도 61.1%·"
    "상품률 37.0%(무처리 86.3%)로 무너지나 총수량은 유의차가 없어 수량 채점으로는 드러나지 "
    "않는다 — pH가 적정으로 판정돼도 상품률 경고가 별도로 필요하다."
)


def _insert(bind, crop_id, stage, indicator, omin, omax, amin, amax, weight, source, **kw):
    bind.execute(
        sa.text(
            "INSERT INTO crop_growth_guide "
            "  (crop_id, growth_stage, indicator, optimal_min, optimal_max, "
            "   allowed_min, allowed_max, weight, source_ref, confidence, "
            "   cultivation_type, allowed_min_kind, allowed_max_kind) "
            "VALUES (:crop, :stage, :ind, :omin, :omax, :amin, :amax, :w, :src, :conf, "
            "        :ct, :mink, :maxk)"
        ),
        {
            "crop": crop_id, "stage": stage, "ind": indicator,
            "omin": omin, "omax": omax, "amin": amin, "amax": amax,
            "w": weight, "src": source,
            "conf": kw.get("confidence", "domestic_measured"),
            "ct": kw.get("cultivation_type", "open_field"),
            "mink": kw.get("min_kind", "heuristic"),
            "maxk": kw.get("max_kind", "heuristic"),
        },
    )


def upgrade() -> None:
    bind = op.get_bind()

    # 1) 야간 밴드 — 오이·상추
    for crop_id, stage, omin, omax, amin, amax, weight, source in _NIGHT_ROWS:
        _insert(bind, crop_id, stage, "temp_night_min", omin, omax, amin, amax, weight, source)

    # 2) 사과 서리 극값. allowed_max가 NULL이므로 max_kind도 NULL이다 —
    #    경계가 없는 방향에 성격을 붙이지 않는다(0036과 같은 계약).
    omin, omax, amin, amax = _APPLE_FROST
    _insert(
        bind, 1, "fruit_growth", "temp_night_min", omin, omax, amin, amax, 1.0,
        _APPLE_FROST_SOURCE,
        confidence="foreign_literature",  # 표1-4가 미국 자료라고 원문이 밝힌다
        min_kind="literature_limit",
        max_kind=None,
    )

    # 3) 감자 pH — 기존 행을 노지로 정정하고 시설 행을 새로 넣는다.
    bind.execute(
        sa.text(
            "UPDATE crop_growth_guide "
            "   SET cultivation_type = 'open_field', "
            "       source_ref = source_ref || :note "
            " WHERE crop_id = 4 AND indicator = 'ph' AND growth_stage IS NULL "
            "   AND cultivation_type = 'facility'"
        ),
        {"note": _POTATO_PH_OPEN_FIELD_NOTE},
    )
    omin, omax, amin, amax = _POTATO_PH_FACILITY
    _insert(
        bind, 4, None, "ph", omin, omax, amin, amax, 1.5, _POTATO_PH_FACILITY_SOURCE,
        cultivation_type="facility",
    )
    bind.execute(
        sa.text(
            "UPDATE crop_growth_guide SET method = '1to5_h2o' "
            " WHERE crop_id = 4 AND indicator = 'ph' AND cultivation_type = 'facility'"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM crop_growth_guide "
            " WHERE crop_id = 4 AND indicator = 'ph' AND cultivation_type = 'facility'"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE crop_growth_guide "
            "   SET cultivation_type = 'facility', "
            "       source_ref = replace(source_ref, :note, '') "
            " WHERE crop_id = 4 AND indicator = 'ph' AND growth_stage IS NULL"
        ),
        {"note": _POTATO_PH_OPEN_FIELD_NOTE},
    )
    bind.execute(
        sa.text(
            "DELETE FROM crop_growth_guide "
            " WHERE indicator = 'temp_night_min' "
            "   AND ((crop_id = 3 AND growth_stage = 'growing') "
            "     OR (crop_id = 5 AND growth_stage IN ('spring', 'fall')) "
            "     OR (crop_id = 1 AND growth_stage = 'fruit_growth'))"
        )
    )
