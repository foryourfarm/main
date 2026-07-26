"""오이·상추·감자 생육 기준을 문헌 기반으로 갱신 (outcomes/memory/crop_rules, 2026-07-25 확인)

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-26

`outcomes/`(5작물 채점 이관 계약 — 별도 ML 프로젝트 산출물)에 오이·상추·감자 문헌 기준이
새로 생겨 반영한다. 사과·배(0015)와 달리 이 셋은 겨울 갭 논의 대상이 아니다 — 오이·상추는
원래 하위 단계 자체가 없었고(전기간 공통 지침), 감자는 파종후경과일 기준이라 "몇 월이 빈다"는
문제가 애초에 없다.

**오이(crop_id=3)**: 지금까지 생육단계 행이 없어 전기간 공통 temp_day(20~22℃)를 썼다. 제주
농업기술원 과채류(오이) 재배기술서 실측(노지 생육적온 25~28℃, 5℃ 이하/35℃ 이상 생육중지)으로
갱신하면서, 생육기(문헌이 명시한 노지 재배기간 4~9월)를 새로 만든다 — 그 결과 겨울철은
"전기간"에서 "단계 없음"으로 바뀐다(사과·배와 같은 맥락: 노지 오이는 4~9월 밖에 실제로 없다).
토양 pH(5.5~6.8, 고사한계 4.3) 기준도 새로 추가 — 기존엔 오이 전용 pH 기준이 없었다.

**상추(crop_id=5)**: 생육단계는 그대로 둔다(문헌이 1~12월 전체를 다뤄 실질적으로 "전기간"과
동일 — 단계 행을 새로 만들면 윤년 12/31이 범위 밖으로 빠지는 경계버그 위험만 생기고 실익이
없다, YAGNI). temp_day만 문헌값(수경재배·항온챔버 실측 22~24℃, 생육정지 2.5~36℃)으로 갱신하고,
토양 pH(6.5~7.0)·유효인산(250~400mg/kg) 기준을 새로 추가한다.

**감자(crop_id=4)**: 토양 유기물 기준(30~47g/kg, 전국 실측)만 추가한다. 문헌의 온도 기준은
달력월(3~6월) 단위인데 감자는 지금 파종후경과일(days_after_planting) 모드라 단순 대응이 안 된다
— 파종일 가정을 임의로 넣어야 하는데 그건 추측이라(§3-4 추측 금지), 이번엔 반영하지 않는다
([확인 필요], nexttodo.md).

**반영하지 않은 것**: 상추 K/Ca/Mg 토양 기준 — `soil_state` 테이블에 해당 컬럼이 없고
suitability_service의 INDICATOR_SOURCE_FIELDS에도 안 걸려 있어 지금 넣어도 채점에 안 쓰인다.
흙토람 API 클라이언트(soil_exam_client.py)는 이미 k/ca/mg를 파싱하고 있어 값 자체는 받아오는
중이니, 스키마+매핑 작업은 별도 PR로.

문구에 %가 섞여 있어(예: "±50%") 값을 바인드 파라미터로 넘긴다 — op.execute(f"...")로
직접 문자열 보간하면 psycopg가 %를 파라미터 자리표시자로 오인해 깨진다(실측 확인됨).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CUCUMBER_TEMP_SOURCE = (
    "제주특별자치도 농업기술원 과채류(오이) 재배기술서 — 노지 생육적온(주간) 25~28도, "
    "35도 이상/5도 이하 시 생육 중지. crop_code 04009가 노지재배 코드인데 기존값(20~22)은 "
    "시설재배 외기 근사였던 것을 실측 노지 문헌으로 교체(outcomes/memory/crop_rules/cucumber.json)."
)
CUCUMBER_PH_SOURCE = (
    "제주특별자치도 농업기술원 과채류(오이) 재배기술서 — 토양 적정 pH 5.5~6.8, 고사한계 pH 4.3 "
    "이하(실측 임계치). allowed_max=7.45는 상한 붕괴점이 문헌에 없어 optimal 폭 절반 폭만큼의 휴리스틱."
)
LETTUCE_TEMP_SOURCE = (
    "문보흠·조일환 — 실측 생육적온 피크 24도, 추정 최적 22.5도(구간 22~24로 반영), "
    "생육정지 2.5~36도(문헌값 그대로, 휴리스틱 아님). [확인 필요] 수경재배·항온챔버 조건이라 "
    "노지 일교차는 미반영."
)
LETTUCE_PH_SOURCE = "농촌진흥청(RDA 2022) 노지 상추 재배 토양 화학성 표준 적정범위(진단기준표)."
LETTUCE_P2O5_SOURCE = "농촌진흥청(RDA 2022) 노지 상추 토양 진단기준표 — 유효인산."
POTATO_ORGANIC_SOURCE = (
    "정진철 외 2003(한국환경농학회지 22권 4호, 261-265쪽), 전국 7개 지역 2개년 실측 — 토양 "
    "유기물이 건물율·칩색도와 강한 상관, 실측범위 10~47g/kg. [확인 필요] 원 논문은 '높을수록 "
    "좋다'는 단조 상관만 제시하고 명시적 적정구간을 안 줘 — optimal_min=30은 관측범위 상위절반을 "
    "'양호' 구간으로 잡은 편집 판단. allowed_max=55.5는 optimal 폭 절반 폭만큼의 휴리스틱."
)

_OLD_CUCUMBER_TEMP = dict(optimal_min=20, optimal_max=22, allowed_min=15, allowed_max=30)
_OLD_LETTUCE_TEMP = dict(optimal_min=15, optimal_max=20, allowed_min=4, allowed_max=30)


def upgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            "INSERT INTO crop_growth_stage (crop_id, growth_stage, mode, range_start, range_end, priority) "
            "VALUES (3, 'growing', 'day_of_year', 91, 273, 1)"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE crop_growth_guide "
            "SET growth_stage = 'growing', optimal_min = 25, optimal_max = 28, "
            "    allowed_min = 5, allowed_max = 35, source_ref = :src, confidence = 'domestic_measured' "
            "WHERE crop_id = 3 AND indicator = 'temp_day' AND growth_stage IS NULL"
        ),
        {"src": CUCUMBER_TEMP_SOURCE},
    )
    bind.execute(
        sa.text(
            "INSERT INTO crop_growth_guide "
            "(crop_id, growth_stage, indicator, optimal_min, optimal_max, allowed_min, allowed_max, "
            " weight, source_ref, confidence) "
            "VALUES (3, NULL, 'ph', 5.5, 6.8, 4.3, 7.45, 1.5, :src, 'domestic_measured')"
        ),
        {"src": CUCUMBER_PH_SOURCE},
    )

    bind.execute(
        sa.text(
            "UPDATE crop_growth_guide "
            "SET optimal_min = 22, optimal_max = 24, allowed_min = 2.5, allowed_max = 36, "
            "    source_ref = :src, confidence = 'domestic_measured' "
            "WHERE crop_id = 5 AND indicator = 'temp_day' AND growth_stage IS NULL"
        ),
        {"src": LETTUCE_TEMP_SOURCE},
    )
    bind.execute(
        sa.text(
            "INSERT INTO crop_growth_guide "
            "(crop_id, growth_stage, indicator, optimal_min, optimal_max, allowed_min, allowed_max, "
            " weight, source_ref, confidence) "
            "VALUES (5, NULL, 'ph', 6.5, 7.0, 6.25, 7.25, 1.5, :src, 'domestic_measured')"
        ),
        {"src": LETTUCE_PH_SOURCE},
    )
    bind.execute(
        sa.text(
            "INSERT INTO crop_growth_guide "
            "(crop_id, growth_stage, indicator, optimal_min, optimal_max, allowed_min, allowed_max, "
            " weight, source_ref, confidence) "
            "VALUES (5, NULL, 'p2o5', 250, 400, 175, 475, 1.0, :src, 'domestic_measured')"
        ),
        {"src": LETTUCE_P2O5_SOURCE},
    )

    bind.execute(
        sa.text(
            "INSERT INTO crop_growth_guide "
            "(crop_id, growth_stage, indicator, optimal_min, optimal_max, allowed_min, allowed_max, "
            " weight, source_ref, confidence) "
            "VALUES (4, NULL, 'organic', 30, 47, 10, 55.5, 1.0, :src, 'domestic_measured')"
        ),
        {"src": POTATO_ORGANIC_SOURCE},
    )


def downgrade() -> None:
    bind = op.get_bind()

    bind.execute(sa.text("DELETE FROM crop_growth_guide WHERE crop_id = 4 AND indicator = 'organic'"))

    bind.execute(
        sa.text("DELETE FROM crop_growth_guide WHERE crop_id = 5 AND indicator IN ('ph', 'p2o5')")
    )
    bind.execute(
        sa.text(
            "UPDATE crop_growth_guide "
            "SET optimal_min = :optimal_min, optimal_max = :optimal_max, "
            "    allowed_min = :allowed_min, allowed_max = :allowed_max, "
            "    source_ref = NULL, confidence = 'foreign_literature' "
            "WHERE crop_id = 5 AND indicator = 'temp_day' AND growth_stage IS NULL"
        ),
        _OLD_LETTUCE_TEMP,
    )

    bind.execute(sa.text("DELETE FROM crop_growth_guide WHERE crop_id = 3 AND indicator = 'ph'"))
    bind.execute(
        sa.text(
            "UPDATE crop_growth_guide "
            "SET growth_stage = NULL, optimal_min = :optimal_min, optimal_max = :optimal_max, "
            "    allowed_min = :allowed_min, allowed_max = :allowed_max, "
            "    source_ref = NULL, confidence = 'foreign_literature' "
            "WHERE crop_id = 3 AND indicator = 'temp_day' AND growth_stage = 'growing'"
        ),
        _OLD_CUCUMBER_TEMP,
    )
    bind.execute(
        sa.text("DELETE FROM crop_growth_stage WHERE crop_id = 3 AND growth_stage = 'growing'")
    )
