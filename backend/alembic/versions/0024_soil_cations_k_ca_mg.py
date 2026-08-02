"""치환성 양이온(K·Ca·Mg) 컬럼 추가 + 사과·배·상추 밴드 적재 (2026-08-01).

**왜**: `outcomes/`(FarmML 이관 계약)가 사과·배·상추를 K·Ca·Mg로도 채점하는데 백엔드에는
지표 자체가 없었다 — 같은 밭에 다른 점수가 나오는 구조적 불일치다
(`outcomes/README.md`의 "두 구현의 점수가 갈리면 안 되는 계약").
`0023`은 컬럼이 있는 지표(ph·organic·p2o5)만 맞췄고 이 마이그레이션이 나머지를 채운다.

**데이터는 이미 들어오고 있었다.** `soil_exam_client.py`가 흙토람 `POSIFERT_K/CA/MG`를
파싱해 놓고도 저장할 곳이 없어 버리고 있었다. `0020`이 이 세 지표의 `risk_width`
(k 0.5041 / ca 3.7777 / mg 1.2632)를 미리 심어둔 것도 지표 행이 생기면 바로 쓰이도록 한
것이고, 지금까지는 대상 행이 없어 무효였다.

**단위 정합성을 실호출로 확인했다(2026-08-01).** 문헌 밴드는 cmol/kg(치환성 양이온)이고,
흙토람 실측도 같은 척도다 — 고창 공음면 구암리 20건에서 K 0.314~2.469 / Ca 1.94~12.16 /
Mg 0.76~4.92였다. FarmML이 인용한 전국 실측(사과 K 0.94, Ca 중앙값 7.23, Mg 1.86)과도 맞는다.
유효인산이 Bray-1(30~50)과 교본(200~300)으로 6배 갈렸던 것과 달리 여기서는 척도 불일치가
없다 — 그래서 채점에 바로 쓸 수 있다.

    지표   사과            배             상추
    k      0.6~0.9        0.3~0.6        0.4~0.6
    ca     5.0~6.0        5.0~6.0        6.0~7.0
    mg     1.5~2.0        1.5~2.0        2.0~2.5
    (allowed는 전부 optimal 폭 ±50% 휴리스틱 — 완충구간 문헌 부재, §8)

**⚠️ 이 지표들은 대체로 "과다" 판정이 날 것이다.** 교본 자신이 전국 실측을 목표 초과로
기술한다(Ca 중앙값 7.23 > 상한 6.0, 배 K 실측 1.13 ≈ 상한의 2배). 점수가 내려가는 것은
회귀가 아니라 한국 과수원 토양의 양이온 과잉이 드러나는 것이다.

**[확인 필요] 두 가지를 미해결로 남긴다.**
1. **사과 K 0.6~0.9 vs 배 K 0.3~0.6 — 두 배 차이.** 작물 생리 차이인지 교본 표 계열
   차이인지 FarmML도 원문 대조 후에도 확정하지 못했다(표5-21 vs 표5-25). 값은 각 교본 표
   그대로 넣되 이 불확실성을 `source_ref`에 남긴다.
2. **침출액 미명시.** 교본이 1N NH4OAc 등 추출 프로토콜을 적지 않았고 흙토람 반환값의
   추출법도 미확인이다. 단위(cmol/kg)와 값의 범위는 일치하므로 채택하지만, 정밀 비교가
   필요해지면 이 지점을 먼저 볼 것.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CATIONS = ("k", "ca", "mg")

_HANDBOOK_BASE = (
    "RDA 표준영농교본 개량목표(치환성 양이온, cmol/kg). FarmML PR #3에서 원문 대조 검증. "
    "outcomes/memory/crop_rules/{crop}.json soil_overrides와 같은 값이어야 한다"
    "(두 구현의 점수가 갈리면 안 되는 계약). allowed_min/max는 완충구간 문헌이 없어 "
    "optimal 폭 ±50% 휴리스틱(§8) [확인 필요]. "
    "[확인 필요] 침출액(1N NH4OAc 등) 미명시 — 교본에도 흙토람 반환값에도 추출법이 없다. "
    "단위·값 범위는 실호출로 일치 확인(공음면 20건 K 0.314~2.469 / Ca 1.94~12.16 / Mg 0.76~4.92)."
)
_K_AMBIGUITY = (
    " [확인 필요] 사과 K 0.6~0.9 vs 배 K 0.3~0.6으로 두 배 차이 — 작물 차이인지 "
    "교본 표 계열(표5-21 vs 표5-25) 차이인지 미확인."
)
_LETTUCE_BASE = (
    "RDA 2022 노지 상추 토양 진단기준표(치환성 양이온, cmol/kg). "
    "outcomes/memory/crop_rules/lettuce.json soil_overrides와 같은 값이어야 한다. "
    "allowed_min/max는 optimal 폭 ±50% 휴리스틱(§8) [확인 필요]. "
    "[확인 필요] 침출액 미명시 — 0019에서 컬럼 부재로 보류했던 지표다."
)

# (crop_id, indicator, optimal_min, optimal_max, allowed_min, allowed_max, weight, source)
# weight 1.0은 기존 토양 지표(0004 organic·p2o5)와 같은 값이다 — 임의값이 아니다.
_BANDS: list[tuple[int, str, float, float, float, float, float, str]] = [
    (1, "k", 0.6, 0.9, 0.45, 1.05, 1.0, _HANDBOOK_BASE + _K_AMBIGUITY),
    (1, "ca", 5.0, 6.0, 4.5, 6.5, 1.0, _HANDBOOK_BASE),
    (1, "mg", 1.5, 2.0, 1.25, 2.25, 1.0, _HANDBOOK_BASE),
    (2, "k", 0.3, 0.6, 0.15, 0.75, 1.0, _HANDBOOK_BASE + _K_AMBIGUITY),
    (2, "ca", 5.0, 6.0, 4.5, 6.5, 1.0, _HANDBOOK_BASE),
    (2, "mg", 1.5, 2.0, 1.25, 2.25, 1.0, _HANDBOOK_BASE),
    (5, "k", 0.4, 0.6, 0.3, 0.7, 1.0, _LETTUCE_BASE),
    (5, "ca", 6.0, 7.0, 5.5, 7.5, 1.0, _LETTUCE_BASE),
    (5, "mg", 2.0, 2.5, 1.75, 2.75, 1.0, _LETTUCE_BASE),
]

# 0020이 이미 심어 둔 감쇠폭. 대상 행이 이제 생기므로 같이 채운다 — 지표별 전국 실측 산포도다.
_RISK_WIDTH = {"k": 0.5041, "ca": 3.7777, "mg": 1.2632}
_RISK_WIDTH_SOURCE = (
    "risk_width=2.0 x robust_sd(1.4826 x MAD), 전국 실측 산포도. "
    "출처 outcomes/memory/indicator_dispersion.json"
)


def upgrade() -> None:
    # 값은 cmol/kg 소수라 Numeric. nullable — 표본이 없는 법정동·경지구분이 실재한다(§12).
    for table in ("district_soil", "soil_state"):
        for column in _CATIONS:
            op.add_column(table, sa.Column(column, sa.Numeric(), nullable=True))

    conn = op.get_bind()
    for crop_id, indicator, omin, omax, amin, amax, weight, source in _BANDS:
        conn.execute(
            sa.text(
                """
                INSERT INTO crop_growth_guide
                    (crop_id, growth_stage, indicator, optimal_min, optimal_max,
                     allowed_min, allowed_max, weight, source_ref, confidence,
                     risk_width, risk_width_source)
                VALUES (:crop, NULL, :ind, :omin, :omax, :amin, :amax, :w, :src,
                        'domestic_measured', :rw, :rws)
                """
            ),
            {
                "crop": crop_id,
                "ind": indicator,
                "omin": omin,
                "omax": omax,
                "amin": amin,
                "amax": amax,
                "w": weight,
                "src": source.replace(
                    "{crop}", {1: "apple", 2: "pear", 5: "lettuce"}[crop_id]
                ),
                "rw": _RISK_WIDTH[indicator],
                "rws": _RISK_WIDTH_SOURCE,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM crop_growth_guide "
            "WHERE growth_stage IS NULL AND indicator IN ('k', 'ca', 'mg')"
        )
    )
    for table in ("soil_state", "district_soil"):
        for column in _CATIONS:
            op.drop_column(table, column)
