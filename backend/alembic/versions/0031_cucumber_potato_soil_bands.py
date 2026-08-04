"""오이·감자 토양 밴드 정합 — 신규 10건 + 오이 pH 갱신 (2026-08-04).

**왜**: `outcomes/`(FarmML 이관 계약)가 2026-08-03에 오이·감자 토양 밴드를 **7지표로 보강**
했는데 백엔드는 각 2지표만 갖고 있었다. 같은 밭에 다른 점수가 나오는 구조적 불일치다
(`outcomes/README.md`의 "두 구현의 점수가 갈리면 안 되는 계약").

**계약 테스트가 못 잡았다 — 그게 이 결함이 오래 남은 이유다.** `test_guide_outcomes_contract.py`
의 `CROP_ID`가 `{apple, pear, lettuce}` 3작물만 담고 있어 오이·감자는 검증 대상 밖이었다.
`nexttodo.md`가 "outcomes soil_overrides 전 지표가 백엔드와 같은 값"이라고 적은 것은 실제로는
그 3작물에만 해당하는 말이었다. 같은 PR에서 `CROP_ID`에 5작물 전부를 넣어 사각지대를 없앤다.

**의도적 배제는 하나도 없었다(이력 확인).** `0019`가 오이·상추·감자를 다룰 때 K·Ca·Mg를 뺀
이유는 "`soil_state` 테이블에 해당 컬럼이 없어 넣어도 채점에 안 쓰인다"였고 그 제약은
`0024`(컬럼 추가)로 해소됐다. 감자 `ph`·오이 `p2o5` 등은 그 시점 outcomes에 **아직 없던**
값이다(전부 출처에 "2026-08-03 신설"로 적혀 있다).

    지표      오이(crop 3)          감자(crop 4)
    ph        6.0~6.5 (갱신)        5.0~6.0 (신규)
    organic   20~30   (신규)        (이미 있음, 값 일치)
    p2o5      400~500 (신규)        250~350 (신규)
    k         0.7~0.8 (신규)        0.5~0.6 (신규)
    ca        5.0~6.0 (신규)        4.5~5.5 (신규)
    mg        1.5~2.0 (신규)        1.5~2.0 (신규)
    ec        (이미 있음, 값 일치)   (이미 있음, 값 일치)

**오이 pH 갱신은 휴리스틱 하나를 없앤다.** 종전 `allowed 4.3~7.45`의 상한 7.45는 ±50%
휴리스틱이었다(`0019`의 `CUCUMBER_PH_SOURCE`가 그렇게 자인한다). outcomes가 제주 농업기술원
문헌의 재배 가능 범위(pH 5.5~6.8)로 교체해 **allowed 양쪽이 모두 문헌값이 됐다.** optimal은
RDA 처방 5차 진단기준표(6.0~6.5)로 좁아진다 — 두 값은 모순이 아니라 역할이 다르다(처방기준은
토양검정 판정 최적구간, 제주 자료는 재배 가능 범위).

**⚠️ 점수가 내려갈 수 있다. 회귀가 아니다.** `0023`·`0024`와 같은 이유다 — 교본 자신이 전국
실측을 "과다 시비 상태"로 기술하고, 지표가 2개에서 7개로 늘면 그동안 안 보이던 과부족이
드러난다. 특히 오이는 `optimal` 폭이 좁아진다(pH 1.3 → 0.5).

**⚠️ 재배형 불일치를 그대로 물려받는다 [확인 필요].** outcomes가 명시하듯 RDA 처방 5차의
오이·감자 화학성 기준표는 **「시설재배토양」** 표인데 우리 실측은 노지 시군구/리 평균이다
(감자는 `exam_field_type=2` 밭, 오이는 `3` 시설). outcomes 쪽 판단("출처 없는 공유 밴드보다
낫다")을 따라 채택하되 이 불일치를 `source_ref`에 남긴다 — 계약상 두 구현이 같은 값을 써야
하므로 여기서 임의로 다르게 정하지 않는다(§3-2).

**감자 온도는 손대지 않는다.** `0019`가 보류한 이유(문헌은 달력월 3~6월인데 감자는
파종후경과일 모드라 파종일을 임의 가정해야 한다 — §3-4 추측 금지)가 그대로 유효하다.
이 마이그레이션은 토양 지표만 다룬다.

`allowed`가 문헌값인지 휴리스틱인지는 지표마다 갈린다 — 아래 각 `source`에 개별로 적는다.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 두 작물이 공유하는 출처 서술. 표 페이지가 달라(오이 p103 / 감자 p83) 페이지는 각 행에 붙인다.
_RDA5_BASE = (
    "RDA 「작물별 비료사용처방」 5차 개정본(2022) {page} 진단기준표. "
    "outcomes/memory/crop_rules/{crop}.json soil_overrides와 같은 값이어야 한다 "
    "(outcomes/README.md 계약). "
    "[확인 필요] 재배형 불일치 — 원문이 「시설재배토양」 기준표인데 우리 실측은 노지 "
    "시군구/리 평균이다. outcomes 판단(출처 없는 공유 밴드보다 낫다)을 따라 채택했다."
)
_HEURISTIC = " allowed는 처방표가 완충구간을 주지 않아 optimal 폭 ±50% 휴리스틱 [확인 필요]."

# 오이 pH만 allowed가 문헌값이다 — 다른 문헌(제주)에서 왔다.
_CUCUMBER_PH_SOURCE = (
    "optimal 6.0~6.5는 RDA 「작물별 비료사용처방」 5차 개정본(2022) p103 시설재배토양 "
    "진단기준표, allowed 5.5~6.8은 제주특별자치도 농업기술원 과채류(오이) 재배기술서의 "
    "'약산성에서 중성으로 pH 5.5~6.8이 적당'(재배 가능 범위). "
    "두 값은 모순이 아니라 역할이 다르다 — 처방기준은 토양검정 판정 최적구간, 제주 자료는 "
    "재배 가능 범위. **이 재배치로 allowed 양쪽이 모두 문헌값이 되어 0019의 "
    "allowed_max=7.45(±50% 휴리스틱)가 소멸한다.** 종전 allowed_min=4.3(고사한계)은 제주 "
    "원문 발췌 범위에서 재확인되지 않아 채택하지 않는다(outcomes 2026-08-03 개정과 동일)."
)

# 감자 pH는 처방표가 아니라 교본에서 왔다.
_POTATO_PH_SOURCE = (
    "RDA 농업기술길잡이 033 「감자」 교본 pH 5.0~6.0 "
    "(knowledge-base/papers/potato/rda-potato-handbook-033). "
    "outcomes/memory/crop_rules/potato.json과 같은 값이어야 한다(2026-08-03 신설)."
    + _HEURISTIC
)

_POTATO_CA_NOTE = (
    " 5작물 중 감자만 낮다(다른 작물 5.0~6.0, 상추 6.0~7.0) — 석회 시용 기준 차이로 "
    "outcomes가 원문 그대로 반영한 값이다."
)

# (crop_id, indicator, optimal_min, optimal_max, allowed_min, allowed_max, weight, source)
# weight 1.0은 기존 토양 지표(0004 organic·p2o5, 0024 k·ca·mg)와 같다 — 임의값이 아니다.
_BANDS: list[tuple[int, str, float, float, float, float, float, str]] = [
    # 오이(crop 3) — p103
    (3, "organic", 20.0, 30.0, 15.0, 35.0, 1.0,
     _RDA5_BASE.format(page="p103", crop="cucumber") + " 유기물 20~30 g/kg." + _HEURISTIC),
    (3, "p2o5", 400.0, 500.0, 350.0, 550.0, 1.0,
     _RDA5_BASE.format(page="p103", crop="cucumber") + " 유효인산 400~500 mg/kg." + _HEURISTIC),
    (3, "k", 0.7, 0.8, 0.65, 0.85, 1.0,
     _RDA5_BASE.format(page="p103", crop="cucumber") + " 치환성 K 0.70~0.80 cmol/kg." + _HEURISTIC),
    (3, "ca", 5.0, 6.0, 4.5, 6.5, 1.0,
     _RDA5_BASE.format(page="p103", crop="cucumber") + " 치환성 Ca 5.0~6.0 cmol/kg." + _HEURISTIC),
    (3, "mg", 1.5, 2.0, 1.25, 2.25, 1.0,
     _RDA5_BASE.format(page="p103", crop="cucumber") + " 치환성 Mg 1.5~2.0 cmol/kg." + _HEURISTIC),
    # 감자(crop 4) — p83
    (4, "ph", 5.0, 6.0, 4.5, 6.5, 1.5, _POTATO_PH_SOURCE),
    (4, "p2o5", 250.0, 350.0, 200.0, 400.0, 1.0,
     _RDA5_BASE.format(page="p83", crop="potato") + " 유효인산 250~350 mg/kg." + _HEURISTIC),
    (4, "k", 0.5, 0.6, 0.45, 0.65, 1.0,
     _RDA5_BASE.format(page="p83", crop="potato") + " 치환성 K 0.50~0.60 cmol/kg." + _HEURISTIC),
    (4, "ca", 4.5, 5.5, 4.0, 6.0, 1.0,
     _RDA5_BASE.format(page="p83", crop="potato") + " 치환성 Ca 4.5~5.5 cmol/kg."
     + _POTATO_CA_NOTE + _HEURISTIC),
    (4, "mg", 1.5, 2.0, 1.25, 2.25, 1.0,
     _RDA5_BASE.format(page="p83", crop="potato") + " 치환성 Mg 1.5~2.0 cmol/kg." + _HEURISTIC),
]

# 오이 pH는 이미 행이 있어 INSERT가 아니라 UPDATE다. (optimal_min, optimal_max, allowed_min, allowed_max)
_CUCUMBER_PH_NEW = (6.0, 6.5, 5.5, 6.8)
_CUCUMBER_PH_OLD = (5.5, 6.8, 4.3, 7.45)  # 0019가 넣은 값 — downgrade에서 되돌린다

# `0020`이 심어 둔 지표별 감쇠폭(전국 실측 산포도). 새 행도 같은 값을 써야 곡선이 갈리지 않는다.
# 출처: outcomes/memory/indicator_dispersion.json
_RISK_WIDTH = {"ph": 0.4641, "organic": 9.2069, "p2o5": 275.3322, "k": 0.5041, "ca": 3.7777, "mg": 1.2632}
_RISK_WIDTH_SOURCE = (
    "risk_width=2.0 x robust_sd(1.4826 x MAD), 전국 실측 산포도. "
    "출처 outcomes/memory/indicator_dispersion.json"
)


def upgrade() -> None:
    conn = op.get_bind()

    # 신규 10건. 멱등하게 — 같은 (crop, 전기간, indicator)가 이미 있으면 넣지 않는다.
    # `0027`이 감자 organic 누락을 backfill할 때 같은 이유로 WHERE NOT EXISTS를 썼다
    # (프로덕션에서 마이그레이션이 적용 완료로 표시됐는데 행은 없던 사고 이력).
    for crop_id, indicator, omin, omax, amin, amax, weight, source in _BANDS:
        conn.execute(
            sa.text(
                """
                INSERT INTO crop_growth_guide
                    (crop_id, growth_stage, indicator, optimal_min, optimal_max,
                     allowed_min, allowed_max, weight, source_ref, confidence,
                     risk_width, risk_width_source)
                -- 파라미터를 명시적으로 캐스팅한다. `INSERT ... SELECT`에서는 Postgres가
                -- 대상 컬럼 타입으로 추론해 주지 않아 `AmbiguousParameter: inconsistent
                -- types deduced (text versus character varying)`로 죽는다(실측). 같은 이유로
                -- `0027`은 값을 SQL에 직접 박아 피했지만, 여기선 행이 10개라 표로 두고 캐스팅한다.
                SELECT CAST(:crop AS integer), NULL, CAST(:ind AS varchar),
                       CAST(:omin AS numeric), CAST(:omax AS numeric),
                       CAST(:amin AS numeric), CAST(:amax AS numeric),
                       CAST(:w AS numeric), CAST(:src AS varchar),
                       'domestic_measured', CAST(:rw AS numeric), CAST(:rws AS varchar)
                WHERE NOT EXISTS (
                    SELECT 1 FROM crop_growth_guide
                    WHERE crop_id = :crop AND growth_stage IS NULL AND indicator = :ind
                )
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
                "src": source,
                "rw": _RISK_WIDTH[indicator],
                "rws": _RISK_WIDTH_SOURCE,
            },
        )

    # 오이 pH 갱신 1건.
    omin, omax, amin, amax = _CUCUMBER_PH_NEW
    conn.execute(
        sa.text(
            """
            UPDATE crop_growth_guide
               SET optimal_min = :omin, optimal_max = :omax,
                   allowed_min = :amin, allowed_max = :amax,
                   source_ref = :src
             WHERE crop_id = 3 AND growth_stage IS NULL AND indicator = 'ph'
            """
        ),
        {"omin": omin, "omax": omax, "amin": amin, "amax": amax, "src": _CUCUMBER_PH_SOURCE},
    )


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            "DELETE FROM crop_growth_guide "
            "WHERE growth_stage IS NULL AND (crop_id, indicator) IN "
            "((3,'organic'),(3,'p2o5'),(3,'k'),(3,'ca'),(3,'mg'),"
            " (4,'ph'),(4,'p2o5'),(4,'k'),(4,'ca'),(4,'mg'))"
        )
    )

    omin, omax, amin, amax = _CUCUMBER_PH_OLD
    conn.execute(
        sa.text(
            """
            UPDATE crop_growth_guide
               SET optimal_min = :omin, optimal_max = :omax,
                   allowed_min = :amin, allowed_max = :amax
             WHERE crop_id = 3 AND growth_stage IS NULL AND indicator = 'ph'
            """
        ),
        {"omin": omin, "omax": omax, "amin": amin, "amax": amax},
    )
