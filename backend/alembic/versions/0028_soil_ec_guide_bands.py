"""토양 염류(EC) 채점 밴드 적재 — 오이·감자·상추 (2026-08-03).

**왜**: FarmML PR "update crop scoring contract"가 `outcomes/`에 EC 채점을 신설했는데
백엔드에는 지침 행이 없었다 — 같은 밭에 다른 점수가 나오는 구조적 불일치다
(`outcomes/README.md`의 "두 구현의 점수가 갈리면 안 되는 계약").
`test_guide_outcomes_contract.py`의 미반영 지표 게이트가 이것을 잡아 이 마이그레이션이 됐다.

**컬럼 추가가 없다.** `soil_state.ec`·`district_soil.ec`는 이미 있고
`suitability_service`도 `INDICATOR_SOURCE_FIELDS`·`INDICATOR_LABELS`에 `ec`를 이미 들고
있었다 — 룰 엔진이 `crop_growth_guide` 행 기반으로 도는 구조라, **빠져 있던 것은 지침 행뿐**
이다. 이 INSERT만으로 EC 채점이 켜진다.

    작물   optimal      allowed      근거
    오이   0.0~2.0      0.0~3.0      처방 5차 p103 시설재배 진단기준표 'EC 2 이하'
    감자   0.0~2.0      0.0~3.0      처방 5차 p83 (동일 표 계열)
    상추   0.0~2.0      0.0~2.9      처방 5차 p169 + allowed는 국내 실측

**상추 `allowed_max`만 휴리스틱이 아니다.** 노안성(2004) 시설채소 수량 20% 감소 EC가 상추
2.9 dS/m이다(organic-farmland-soil-management-2017.md). 5작물 중 EC 허용상한이 문헌값인
유일한 작물이라 오이·감자(3.0 = optimal 폭 ±50% 휴리스틱)와 값이 다르다 — 오타가 아니다.

**`optimal_min=0.0`은 "EC가 낮을수록 좋다"가 아니다.** 인용한 진단기준표들이 하한을 주지
않아 **하한 방향 감점을 두지 않는 것**이다. 저 EC를 문제로 다루는 문헌이 확보되면 갱신한다.

**[확인 필요] 남기는 위험 두 가지.**
1. **척도.** 문헌은 1:5 침출 dS/m인데 흙토람 `elcd` 반환값의 환산 여부가 미확인이다.
   EC는 지도자료용(1:5 ×5)과 연구자료용(비환산)이 정확히 5배 갈리는 것이 확인된 지표다
   (`_shared.json` method_note) — 유효인산 6배 건과 같은 종류의 위험이 남아 있다.
2. **재배형.** 셋 다 **시설재배** 토양 진단기준표다. 노지 밭에 그대로 적용하는 것이라
   보수적(엄격)일 수 있다. outcomes 쪽 `method`에도 같은 주의가 적혀 있다.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RDA_BASE = (
    "RDA 「작물별 비료사용처방」 5차(2022) 시설재배토양 진단기준표 'EC 2 이하'(1:5 침출, dS/m). "
    "outcomes/memory/crop_rules/{crop}.json soil_overrides.ec와 같은 값이어야 한다"
    "(두 구현의 점수가 갈리면 안 되는 계약). "
    "optimal_min=0.0은 문헌이 하한을 주지 않아 하한 감점을 두지 않는 것이다. "
    "[확인 필요] 흙토람 elcd 반환값의 1:5 환산 여부 미확인 — EC는 지도자료용(×5)과 "
    "연구자료용이 정확히 5배 갈리는 지표다. "
    "[확인 필요] 시설재배 기준표를 노지에 적용 중이라 보수적일 수 있다."
)
_HEURISTIC_MAX = " allowed_max=3.0은 붕괴점 문헌이 없어 optimal 폭(2.0) ±50% 휴리스틱(§8) [확인 필요]."
_LETTUCE_MAX = (
    " allowed_max=2.9는 휴리스틱이 아니라 국내 실측이다 — 노안성(2004) 시설채소 수량 20% "
    "감소 EC(organic-farmland-soil-management-2017.md). [확인 필요] 유기농기술지의 2차 "
    "인용이며 원 논문·측정법 미확인."
)

# (crop_id, optimal_min, optimal_max, allowed_min, allowed_max, source)
# crop_id는 0003 시드 기준(3 오이 / 4 감자 / 5 상추). 사과·배는 outcomes에도 EC 밴드가 없다.
# weight 1.0은 기존 토양 지표(0004 organic·p2o5, 0024 k·ca·mg)와 같다 — 임의값이 아니다.
_BANDS: list[tuple[int, float, float, float, float, str]] = [
    (3, 0.0, 2.0, 0.0, 3.0, _RDA_BASE + _HEURISTIC_MAX),
    (4, 0.0, 2.0, 0.0, 3.0, _RDA_BASE + _HEURISTIC_MAX),
    (5, 0.0, 2.0, 0.0, 2.9, _RDA_BASE + _LETTUCE_MAX),
]

_WEIGHT = 1.0
# 0020이 다른 지표와 함께 심어 둔 감쇠폭. 대상 행이 이제 생겨 유효해진다.
_RISK_WIDTH = 0.3855
_RISK_WIDTH_SOURCE = (
    "risk_width=2.0 x robust_sd(1.4826 x MAD), 전국 실측 산포도. "
    "출처 outcomes/memory/indicator_dispersion.json"
)

_CROP_SLUG = {3: "cucumber", 4: "potato", 5: "lettuce"}


def upgrade() -> None:
    conn = op.get_bind()
    for crop_id, omin, omax, amin, amax, source in _BANDS:
        conn.execute(
            sa.text(
                """
                INSERT INTO crop_growth_guide
                    (crop_id, growth_stage, indicator, optimal_min, optimal_max,
                     allowed_min, allowed_max, weight, source_ref, confidence,
                     risk_width, risk_width_source)
                VALUES (:crop, NULL, 'ec', :omin, :omax, :amin, :amax, :w, :src,
                        'domestic_measured', :rw, :rws)
                """
            ),
            {
                "crop": crop_id,
                "omin": omin,
                "omax": omax,
                "amin": amin,
                "amax": amax,
                "w": _WEIGHT,
                "src": source.replace("{crop}", _CROP_SLUG[crop_id]),
                "rw": _RISK_WIDTH,
                "rws": _RISK_WIDTH_SOURCE,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM crop_growth_guide "
            "WHERE growth_stage IS NULL AND indicator = 'ec'"
        )
    )
