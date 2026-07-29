"""사과 지침의 누락된 허용경계(allowed_min/max) 보완 + 채점 불가 행 제거 (2026-07-29).

**왜**: 0020이 `risk_width`(전국 실측 산포도)를 넣어 위험구간 절벽을 없앴지만, 사과 5행은
그 개선을 못 받았다. `_indicator_score`가 `allowed_min`/`allowed_max`가 NULL이면
`risk_width`를 읽기 **전에** 0점을 반환하기 때문이다(suitability_service.py:124-132).
즉 마이그레이션 0020이 값을 넣어둔 컬럼에 채점 경로가 도달하지 못한다.

원인은 코드가 아니라 시드다. 0004 시드(농사로 안내책자)는 optimal만 주는 출처였고, 다른
작물은 이후 0012/0015/0019에서 허용경계가 채워졌는데 사과의 0004 행들만 한 번도 손을 안 탔다.
그래서 채점 곡선(정책)은 그대로 두고 데이터만 보완한다.

**허용경계 산출**: `allowed = optimal 경계 ± (optimal_max - optimal_min) x 0.5`.
새 방법이 아니라 0019가 문헌이 침묵하는 경계에 이미 쓴 휴리스틱이다 — 실제 값으로 역산 확인:
오이 pH 7.45 = 6.8 + 1.3x0.5, 감자 유기물 55.5 = 47 + 17x0.5,
상추 유효인산 175/475 = 250-75 / 400+75. 세 사례 모두 일치한다.
문헌에서 온 경계(사과 착과~비대기 상한 31도, LoopReport)는 건드리지 않는다.

**[확인 필요] 이 값들은 문헌이 아니라 휴리스틱이다.** 0019 선례대로 `confidence`는
optimal의 근거(domestic_measured)를 유지하고, 허용경계가 추정임을 `source_ref`에 명시한다.
사과 내성 한계 문헌(고온·저온 붕괴점, 유기물·유효인산 결핍/과다 임계)을 확보하면 교체 대상.

**삭제하는 행**: 사과 착색기 `temp_night_min` (optimal 8~8).
폭이 0인 점 값이라 채점이 구조적으로 불가능하다 — 야간최저기온이 정확히 8.00도일 때만
100점, 그 외 전부 0점이다. 평년치가 소수점까지 8.00으로 떨어질 일이 없어 사실상 상시 0점이며,
착색기 가중치의 약 18%(장기 탭 기준 1.0/5.5)를 근거 없이 깎아왔다. 폭이 0이라 위 휴리스틱도
적용할 수 없고, `risk_width`도 산포도를 낼 수 없어 NULL이다.
0004가 인용한 `crop-domain-knowledge.md`는 현재 리포에 없고 `outcomes/memory/crop_rules/
apple.json`에도 야간기온 항목이 없어 원 문헌을 확인할 수 없다. 값을 추측으로 고치는 대신
채점에서 제외한다 — 집계는 값이 없는 지표를 `weight_sum`에서 빼므로(suitability_service.py:175)
나머지 지표로 정상 채점된다. 문헌 확보 시 구간으로 되살린다. [확인 필요]

**주의**: source_ref 문구에 `%`가 들어가 바인드 파라미터로 넘긴다. `op.execute(f"...")`로
문자열 보간하면 psycopg가 `%`를 파라미터 자리표시자로 오인해 깨진다(0019에서 실측 확인).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 허용경계가 문헌이 아니라 휴리스틱임을 행마다 남긴다(§18-4 — 추정치를 실측처럼 표기 금지).
HEURISTIC_NOTE = (
    " | 허용경계는 문헌값이 아니라 추정: allowed = optimal 경계 ±(optimal 폭 x 50%), "
    "0019(오이 pH·감자 유기물·상추 유효인산)와 동일한 휴리스틱. [확인 필요] 사과 내성 한계 "
    "문헌 확보 시 교체."
)

# (growth_stage, indicator, allowed_min, allowed_max). None은 "그대로 둔다"(문헌값 보존).
# 값 근거는 모듈 docstring의 산출식. optimal은 건드리지 않는다.
APPLE_ALLOWED: tuple[tuple[str | None, str, float | None, float | None], ...] = (
    # 착과~비대기: 상한 31은 문헌값(LoopReport)이라 유지하고 하한만 채운다. 18 - 6x0.5
    ("fruit_growth", "temp_day", 15.0, None),
    ("maturity", "temp_day", 17.5, 27.5),  # 20 ∓ 2.5 / 25 ± 2.5
    ("coloring", "temp_day", 11.5, 13.5),  # 12 ∓ 0.5 / 13 ± 0.5
    (None, "organic", 15.0, 35.0),  # 20 ∓ 5 / 30 ± 5
    (None, "p2o5", 175.0, 675.0),  # 300 ∓ 125 / 550 ± 125
)

# 삭제 대상 행의 원본 — downgrade에서 그대로 복원한다.
COLORING_NIGHT_TEMP = {
    "optimal_min": 8,
    "optimal_max": 8,
    "weight": 1.0,
    "source_ref": "농촌진흥청 농사로 작물별 안내책자(0004 시드)",
    "confidence": "domestic_measured",
}

_STAGE_CLAUSE = {
    True: "growth_stage IS NULL",
    False: "growth_stage = :stage",
}


def _where(stage: str | None) -> tuple[str, dict[str, object]]:
    """growth_stage가 NULL인 행은 `= NULL`로 못 잡는다 — 절을 나눈다."""
    clause = _STAGE_CLAUSE[stage is None]
    params: dict[str, object] = {} if stage is None else {"stage": stage}
    return clause, params


def upgrade() -> None:
    bind = op.get_bind()
    for stage, indicator, allowed_min, allowed_max in APPLE_ALLOWED:
        clause, params = _where(stage)
        # coalesce 없이 `|| :note`는 source_ref가 NULL이면 결과도 NULL — 근거를 조용히 지운다.
        sets = ["source_ref = coalesce(source_ref, '') || :note"]
        params |= {"note": HEURISTIC_NOTE, "indicator": indicator}
        if allowed_min is not None:
            sets.append("allowed_min = :amin")
            params["amin"] = allowed_min
        if allowed_max is not None:
            sets.append("allowed_max = :amax")
            params["amax"] = allowed_max
        bind.execute(
            sa.text(
                f"UPDATE crop_growth_guide SET {', '.join(sets)} "  # noqa: S608 — 값은 전부 바인드
                f"WHERE crop_id = 1 AND indicator = :indicator AND {clause}"
            ),
            params,
        )

    bind.execute(
        sa.text(
            "DELETE FROM crop_growth_guide "
            "WHERE crop_id = 1 AND growth_stage = 'coloring' AND indicator = 'temp_night_min'"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    for stage, indicator, allowed_min, allowed_max in APPLE_ALLOWED:
        clause, params = _where(stage)
        sets = ["source_ref = replace(source_ref, :note, '')"]
        params |= {"note": HEURISTIC_NOTE, "indicator": indicator}
        if allowed_min is not None:
            sets.append("allowed_min = NULL")
        if allowed_max is not None:
            sets.append("allowed_max = NULL")
        bind.execute(
            sa.text(
                f"UPDATE crop_growth_guide SET {', '.join(sets)} "  # noqa: S608 — 값은 전부 바인드
                f"WHERE crop_id = 1 AND indicator = :indicator AND {clause}"
            ),
            params,
        )

    bind.execute(
        sa.text(
            "INSERT INTO crop_growth_guide "
            "(crop_id, growth_stage, indicator, optimal_min, optimal_max, "
            " allowed_min, allowed_max, weight, source_ref, confidence) "
            "VALUES (1, 'coloring', 'temp_night_min', :optimal_min, :optimal_max, "
            " NULL, NULL, :weight, :source_ref, :confidence)"
        ),
        COLORING_NIGHT_TEMP,
    )
