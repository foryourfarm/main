"""사과·배 토양 밴드를 RDA 교본 개량목표로 교체 + temp_day 감쇠폭 갱신 (2026-08-01).

**왜**: 채점 근거를 `outcomes/`(FarmML 이관 계약)와 같은 값으로 유지해야 한다. 두 구현이
갈리면 같은 밭에 다른 점수가 나온다 — `outcomes/README.md`가 명시한 계약이다.
FarmML PR #3(채점 근거 정합성 감사 + RDA 교본 토양값 승격)이 사과·배에 `soil_overrides`를
신설했고, 그 값을 여기로 옮긴다.

**점수가 내려간다. 회귀가 아니다.** FarmML 산출 기준 사과 63.0 → 52.6, 배 92.0 → 77.2다.
원문 검증된 RDA 교본 개량목표를 적용하니 한국 과수원 토양의 인산·칼슘 과잉이 드러난 것이고,
교본 자신이 전국 실측(유효인산 사과 615·배 801.9 mg/kg)을 "과다 시비 상태"로 기술한다.
낮아진 점수가 실제 상태에 더 가깝다.

**바뀌는 값** (사과=1, 배=2):

    지표       종전                          신규(RDA 교본)
    ph         사과 opt 6.0~6.5/allow 5.5~7.0   opt 6.0~6.5 / allow 5.75~6.75
               배   opt 5.8~7.0/allow 5.5~7.5   opt 6.0~6.5 / allow 5.75~6.75
    organic    사과 opt 20~30/allow 15~35       opt 25~35 / allow 20~40
               배   없음                         신규 (같은 값)
    p2o5       사과 opt 300~550/allow 175~675   opt 200~300 / allow 150~350
               배   없음                         신규 (같은 값)

`temp_day` 감쇠폭도 2.2408 → 2.219로 갱신한다(`indicator_dispersion.json` 재산출 결과 —
표본이 150 → 136지역으로 바뀌었다. 문경 흥덕동 결함행 제외 등).

**⚠️ 측정 프로토콜 미확인 위험을 `source_ref`에 적어 남긴다(§18-4).** 유효인산은 RDA
비료사용처방(Bray-1) 30~50 mg/kg과 RDA 교본 개량목표 200~300 mg/kg이 약 6배 갈리는데
교본에 추출법 명시가 없다. 우리가 채점 입력으로 쓰는 흙토람 `VLDPHA`의 추출법도 미확인이라
"문헌 대비 편차"가 같은 척도 위에서 계산되는지 자체가 보장되지 않는다. 다만 흙토람 실측이
수백 mg/kg 범위(전국 중앙값 419.7)라 교본 척도와 정합적이므로 이 밴드를 채택한다 —
Bray-1 척도였다면 전국이 통째로 과다 판정되었을 것이다. FarmML은 이 위험을 밴드별 `method`
필드로 남겼는데, 우리는 컬럼을 새로 만들지 않고 기존 `source_ref`에 적는다(같은 목적의
자유서술 컬럼이 이미 있다).

**K·Ca·Mg는 이 마이그레이션에 없다.** FarmML은 사과·배에 그 세 밴드도 신설했지만
`soil_state`·`district_soil`에 컬럼이 없어 채점 입력 자체가 없다. 흙토람 클라이언트는 이미
`POSIFERT_K/CA/MG`를 파싱하므로 데이터는 오지만 저장하지 않는다. 스키마·ETL·채점 매핑이
함께 필요한 별도 작업이라 나누었다(`nexttodo.md`). `0020`이 그 세 지표의 `risk_width`를 이미
심어 둔 것은 지표 행이 생기면 바로 쓰이도록 한 것이고, 지금은 대상 행이 없어 무효다.

**가중치는 건드리지 않는다.** FarmML이 표기를 soil45/temp30/precip25 → 60/40/0으로 고쳤지만
그건 실효값을 명시값으로 올린 것(산출 점수 불변)이고, 우리 백엔드는 지표 행별 `weight`로
따로 계산한다. 배에 organic·p2o5가 생기면서 배의 토양:기온 비중이 42.9:57.1 → 63.6:36.4로
움직이는데, 이는 지표를 추가한 결과이지 가중치를 임의로 바꾼 것이 아니다.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_HANDBOOK = (
    "RDA 표준영농교본 개량목표(과수). FarmML PR #3에서 원문 검증 후 승격 — "
    "outcomes/memory/crop_rules/{apple,pear}.json soil_overrides와 같은 값이어야 한다"
    "(두 구현의 점수가 갈리면 안 되는 계약, outcomes/README.md). "
    "[확인 필요] 측정 프로토콜 미명시 — 교본에 추출법이 없고 흙토람 VLDPHA 추출법도 "
    "미확인이라 문헌 밴드와 실측이 같은 척도인지 보장되지 않는다. 유효인산은 Bray-1 "
    "30~50과 교본 200~300이 약 6배 갈린다. 흙토람 실측이 수백 mg/kg(전국 중앙값 419.7)라 "
    "교본 척도와 정합적이라고 보고 채택했다."
)

# (crop_id, indicator, optimal_min, optimal_max, allowed_min, allowed_max)
# 사과·배 공통 — 교본 개량목표는 과수 기준이라 두 작물이 같다(K만 다르고 그건 미적용).
_BANDS = [
    (1, "ph", 6.0, 6.5, 5.75, 6.75),
    (1, "organic", 25.0, 35.0, 20.0, 40.0),
    (1, "p2o5", 200.0, 300.0, 150.0, 350.0),
    (2, "ph", 6.0, 6.5, 5.75, 6.75),
    (2, "organic", 25.0, 35.0, 20.0, 40.0),
    (2, "p2o5", 200.0, 300.0, 150.0, 350.0),
]

# 종전 값 — downgrade에서 되돌린다. 배 organic·p2o5는 원래 없던 행이라 삭제한다.
_PREVIOUS = [
    (1, "ph", 6.0, 6.5, 5.5, 7.0),
    (1, "organic", 20.0, 30.0, 15.0, 35.0),
    (1, "p2o5", 300.0, 550.0, 175.0, 675.0),
    (2, "ph", 5.8, 7.0, 5.5, 7.5),
]
_ADDED_ROWS = [(2, "organic"), (2, "p2o5")]

_TEMP_DAY_RISK_WIDTH_NEW = 2.219
_TEMP_DAY_RISK_WIDTH_OLD = 2.2408
_RISK_WIDTH_SOURCE = (
    "risk_width=2.0 x robust_sd(1.4826 x MAD), 전국 실측 산포도. "
    "출처 outcomes/memory/indicator_dispersion.json (2026-08-01 재산출, 136지역)"
)


def _upsert(crop_id: int, indicator: str, bands: tuple[float, ...], source: str) -> None:
    """토양 지표는 생육단계 무관(growth_stage IS NULL)이라 그 행만 대상으로 한다."""
    conn = op.get_bind()
    updated = conn.execute(
        sa.text(
            """
            UPDATE crop_growth_guide
               SET optimal_min = :omin, optimal_max = :omax,
                   allowed_min = :amin, allowed_max = :amax,
                   source_ref = :src
             WHERE crop_id = :crop AND indicator = :ind AND growth_stage IS NULL
            """
        ),
        {
            "crop": crop_id,
            "ind": indicator,
            "omin": bands[0],
            "omax": bands[1],
            "amin": bands[2],
            "amax": bands[3],
            "src": source,
        },
    ).rowcount
    if updated:
        return
    # 없던 지표(배 organic·p2o5)는 새로 넣는다. weight는 사과의 같은 지표와 맞춘다(1.0) —
    # 임의값이 아니라 기존 시드의 토양 지표 가중치다(0004).
    conn.execute(
        sa.text(
            """
            INSERT INTO crop_growth_guide
                (crop_id, growth_stage, indicator, optimal_min, optimal_max,
                 allowed_min, allowed_max, weight, source_ref)
            VALUES (:crop, NULL, :ind, :omin, :omax, :amin, :amax, 1.0, :src)
            """
        ),
        {
            "crop": crop_id,
            "ind": indicator,
            "omin": bands[0],
            "omax": bands[1],
            "amin": bands[2],
            "amax": bands[3],
            "src": source,
        },
    )


def upgrade() -> None:
    for crop_id, indicator, *bands in _BANDS:
        _upsert(crop_id, indicator, tuple(bands), _HANDBOOK)

    # 감쇠폭은 지표 전체(작물 무관)에 같은 값을 쓴다 — 0020과 같은 방식이다.
    op.get_bind().execute(
        sa.text(
            "UPDATE crop_growth_guide SET risk_width = :w, risk_width_source = :s "
            "WHERE indicator = 'temp_day'"
        ),
        {"w": _TEMP_DAY_RISK_WIDTH_NEW, "s": _RISK_WIDTH_SOURCE},
    )


def downgrade() -> None:
    conn = op.get_bind()
    for crop_id, indicator in _ADDED_ROWS:
        conn.execute(
            sa.text(
                "DELETE FROM crop_growth_guide "
                "WHERE crop_id = :crop AND indicator = :ind AND growth_stage IS NULL"
            ),
            {"crop": crop_id, "ind": indicator},
        )
    for crop_id, indicator, omin, omax, amin, amax in _PREVIOUS:
        conn.execute(
            sa.text(
                """
                UPDATE crop_growth_guide
                   SET optimal_min = :omin, optimal_max = :omax,
                       allowed_min = :amin, allowed_max = :amax
                 WHERE crop_id = :crop AND indicator = :ind AND growth_stage IS NULL
                """
            ),
            {
                "crop": crop_id,
                "ind": indicator,
                "omin": omin,
                "omax": omax,
                "amin": amin,
                "amax": amax,
            },
        )
    conn.execute(
        sa.text(
            "UPDATE crop_growth_guide SET risk_width = :w WHERE indicator = 'temp_day'"
        ),
        {"w": _TEMP_DAY_RISK_WIDTH_OLD},
    )
