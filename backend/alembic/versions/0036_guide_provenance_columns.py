"""생육지침에 출처 성격 컬럼 4개 신설 — 재배형·허용경계 성격·측정법 (2026-08-04).

**왜**: `crop_growth_guide`의 한 칸이 서로 다른 성격의 값을 구분 없이 담고 있었다.
FinalReport.md §2-1·§2-2·§2-3의 세 지적을 한 번에 푼다 — 셋 다 "값에 성격 표시를 붙이는
문제"라 따로 올리면 같은 설명을 세 번 하게 된다.

1. **`cultivation_type`(§2-1)** — 오이·감자·상추의 화학성 밴드는 RDA 「작물별 비료사용처방」
   5차(2022)의 **「시설재배토양」 진단기준표**인데 우리 채점 입력은 노지 실측이다. 지금까지는
   이 불일치가 `source_ref` 문자열에만 적혀 있어 코드가 읽을 수 없었다. 컬럼이 생기면 같은
   지표에 노지·시설 두 행을 두고 골라 쓸 수 있다(`0037`의 감자 pH가 첫 사례).

   🔴 **전 행을 `facility`로 채우지 않는다.** 실제로 시설 기준인 것은 **crop 3·4·5의 화학성
   7지표뿐**이다. 사과·배 토양 행은 처방서의 **과수원** 표에서 왔고, 기온·강수 행은 전부 노지
   기준 자료다. 일괄 `facility`로 칠하면 새 컬럼이 첫날부터 거짓말을 하게 된다.

2. **`allowed_min_kind` / `allowed_max_kind`(§2-2)** — `allowed` 경계는 지금 성격과 무관하게
   일괄 60점(B등급 하한)으로 읽힌다. 그런데 그 칸에는 ±50% 휴리스틱, 생리적 절대한계,
   재배 가능 범위, 우리 역산치가 섞여 있다. **생장이 완전히 멈추는 점이 60점을 받는 것**이
   가장 큰 문제다(상추 온도 2.5·36℃).

   🔴 **FinalReport는 `allowed_kind` 한 컬럼을 제안했으나 두 컬럼으로 쪼갠다.** 실제 데이터가
   방향별로 갈리기 때문이다 — 사과 착과기 기온은 `allowed_min 15.0`이 ±50% 휴리스틱이고
   `allowed_max 31`은 출처가 루프 라벨뿐이다. 한 컬럼이면 둘 중 하나를 반드시 거짓 표기하게 된다.

3. **`method`(§2-3)** — 추출법이 다르면 애초에 비교 대상이 아니다. EC는 보고 관행이 두 갈래라
   **정확히 5배** 갈리고(적정 2 이하 ↔ 염류토양 4 초과), pH는 H₂O법과 KCl법이 약 1.2 벌어진다.
   문헌측 프로토콜은 국가농업환경변동조사 최종보고서가 국내 표준을 명문화해 확정됐지만
   **흙토람 API 반환값(우리 실측 입력)의 추출법은 여전히 미확인**이라, EC는 `unknown`으로 둔다.

**채점은 딱 한 군데만 바뀐다** — `allowed_*_kind = 'literature_limit'`인 경계의 점수가
60 → 0이 된다(`suitability_service._indicator_score`). 나머지 값은 순수 출처 메타데이터로
코드 분기가 없다. 어떤 행이 바뀌는지는 아래 `_KIND_OVERRIDE` 참고 — 상추 기온 1행뿐이다.

**미분류 행은 `unverified`로 떨어진다.** 조용히 `heuristic`이나 문헌으로 승격시키지 않는다 —
"근거를 특정하지 못했다"와 "±50%로 만든 값이다"는 다른 말이고, 후자로 적으면 없는 정보를
지어내는 것이다(§18-4).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0036"
down_revision: str | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ---------------------------------------------------------------------------
# 값 도메인. 코드가 분기하는 것은 `literature_limit` 하나뿐이고 나머지는 표기용이다.
# CHECK 제약을 걸지 않는 이유: 성격 분류는 문헌 조사가 진행되면서 늘어난다(이미 FinalReport의
# 4종에서 여기 7종이 됐다). 제약을 걸면 값이 하나 늘 때마다 마이그레이션이 필요해진다.
# ---------------------------------------------------------------------------
ALLOWED_KINDS = (
    "heuristic",  # optimal 폭 ±50%로 기계 산출. 문헌 아님(CLAUDE.md §8)
    "literature_limit",  # 🔴 문헌이 준 생리적 절대한계 = 생장/수량이 0이 되는 점 → 경계 0점
    "literature_threshold",  # 문헌 실측이지만 붕괴점은 아님(예: 수량 20% 감소 EC)
    "cultivable_range",  # 「재배 가능 범위」 — 적정은 아니나 재배는 되는 구간
    "derived",  # 🔵 우리 역산치. 문헌값처럼 보이면 안 된다
    "unverified",  # 근거가 특정되지 않음(구 루프 라벨·2차 인용 등)
    "not_applicable",  # 그 방향에 경계 개념이 없음(EC 하한 — 저 EC는 문제로 다뤄지지 않는다)
)

CULTIVATION_TYPES = ("open_field", "facility")

# 지표 → 국내 표준 측정법. 국가농업환경변동조사 최종보고서가 명문화한
# 농촌진흥청 「토양 및 식물체 분석」(2007) 기준이다.
# 🔴 이것은 **문헌 밴드 쪽** 프로토콜이다. 실측 입력(흙토람 API)의 추출법은 명세서 3종에
# 단위만 있고 표기가 전혀 없어 미확인이며, 그래서 같은 프로토콜이라는 보장이 없다.
_METHOD_BY_INDICATOR = {
    "ph": "1to5_h2o",  # 토양:증류수 1:5
    "organic": "tyurin",  # Tyurin법, g/kg
    "p2o5": "lancaster",  # Lancaster법, mg/kg
    "k": "nh4oac",  # 1M NH4OAc 침출 후 AA·ICP, cmol/kg
    "ca": "nh4oac",
    "mg": "nh4oac",
    # 🔴 EC만 unknown이다. 문헌(처방 5차)은 1:5 침출이라 밝히지만 지도자료용(×5)과
    # 연구자료용이 정확히 5배 갈리고, 흙토람 `elcd`가 어느 쪽인지 확인되지 않았다.
    # 이 칸이 확정되기 전에는 EC 단독으로 판정하지 않는다(§2-3 ⓐ의 조건).
    "ec": "unknown",
    # 기온·강수는 추출법 개념이 없다 → NULL(아래 dict에 넣지 않는다).
}

# 시설재배토양 진단기준표에서 온 행 — 여기에 걸리는 것만 `facility`다.
_FACILITY_CROPS = (3, 4, 5)  # 오이·감자·상추
_SOIL_INDICATORS = ("ph", "organic", "p2o5", "k", "ca", "mg", "ec")

# ---------------------------------------------------------------------------
# 허용경계 성격 예외표. 여기 없으면 ±50% 판정 → 맞으면 heuristic, 아니면 unverified.
# 키: (crop_id, growth_stage, indicator). `ANY_STAGE`는 그 작물·지표의 모든 단계에 적용.
#     crop_id=None은 전 작물 공통.
# 값: (allowed_min_kind, allowed_max_kind). None은 "자동 판정에 맡긴다".
#
# 🔴 `ANY_STAGE`가 필요한 이유: 같은 지표가 작물마다 다른 단계 이름을 달고 있다 —
# 상추 `temp_day`는 `0025`가 작기를 세우면서 spring/fall 2행이 됐고 오이는 `growing`이다.
# 단계를 못 박으면 정작 성격을 붙여야 할 행을 놓친다(실제로 첫 시도에서 놓쳤다).
# ---------------------------------------------------------------------------
ANY_STAGE = "*"

_KIND_OVERRIDE: dict[tuple[int | None, str | None, str], tuple[str | None, str | None]] = {
    # 🔴 채점이 실제로 바뀌는 행들. 문헌이 **생육 중지/정지 온도**를 직접 준 두 작물이다.
    # 상추 2.5·36℃(발아 한계·복합장해), 오이 5·35℃('35℃ 이상/5℃ 이하 시 생육 중지').
    # 지금까지 이 네 점이 60점을 받고 있었다 — 생장이 멈추는 온도인데 B등급 하한이었다.
    (5, ANY_STAGE, "temp_day"): ("literature_limit", "literature_limit"),
    (3, ANY_STAGE, "temp_day"): ("literature_limit", "literature_limit"),
    # 배 생육기 기온 17·23℃는 arccas 「가능지」 문헌값이다(적지 18.5~21.5의 바깥 구간).
    # 값이 우연히 ±50%와 일치해 자동 판정이 heuristic으로 오인한다 — 문헌값을 휴리스틱이라
    # 적으면 근거를 지우는 것이라 명시한다.
    (2, "growing", "temp_day"): ("cultivable_range", "cultivable_range"),
    # 오이 pH 허용경계는 제주 농업기술원 지도요강의 **재배 가능 범위** 5.5~6.8이다
    # (0031이 종전 ±50% 휴리스틱 7.45를 이 문헌값으로 교체했다). 붕괴점이 아니라
    # "적정은 아니나 재배는 된다"는 구간이라 60점이 맞다.
    (3, None, "ph"): ("cultivable_range", "cultivable_range"),
    # 상추 EC 2.9는 휴리스틱이 아니라 국내 실측(노안성 2004, 시설채소 수량 20% 감소 EC)이다.
    # 다만 20% 감수는 붕괴점이 아니므로 `literature_limit`이 아니다 — 0점을 주면 과잉이다.
    (5, None, "ec"): ("not_applicable", "literature_threshold"),
    # EC 하한: optimal_min·allowed_min이 둘 다 0.0이다. 문헌이 하한을 주지 않아 하한 방향
    # 감점을 두지 않은 것이지 "0이 경계"라는 뜻이 아니다.
    (3, None, "ec"): ("not_applicable", None),
    (4, None, "ec"): ("not_applicable", None),
    # 사과 착과~비대기 고온 31℃ — 출처가 `LoopReport.md`라는 라벨뿐이고 원문이 특정되지
    # 않았다(FinalReport §3-5). 하한 15.0은 0021이 ±50%로 만든 휴리스틱이라 자동 판정에 맡긴다.
    (1, "fruit_growth", "temp_day"): (None, "unverified"),
    # 감자 초기 냉해 -3℃(Stegner 2019)·상한 27℃ — 둘 다 원문의 2차 인용이다. 게다가 잎은
    # 결빙 후 10~78분만 견디고 원문이 "2차 결빙은 확률적 사건"이라 밝혀 **단일 임계로는
    # 판정 자체가 불가능**하다. 값은 두되 문헌 한계로 승격시키지 않는다.
    (4, "early", "temp_day"): ("unverified", "unverified"),
    (4, "tuber", "temp_day"): (None, "unverified"),
    # 감자 야간 28℃ — Zhang 2024 **Discussion의 2차 인용[24]**이다(0037이 source_ref를
    # 국내 1차 자료로 교체하지만, 그 자료는 주야 구분이 없어 성격이 같다고 단정할 수 없다).
    (4, "tuber", "temp_night_min"): (None, "unverified"),
    # 사과 치환성 Ca. `0030`이 단측 밴드로 만들었다가(교본 원문 "5~6cmol/kg **이상**")
    # `0035`가 FarmML 동기화로 상한 6.0을 되살려 다시 양측이 됐다 — 자동 판정이 폭 1.0에서
    # ±50%를 계산해 양쪽 다 heuristic으로 맞게 떨어진다. 하한 명시는 `0030` 상태로 되돌아갈
    # 경우의 안전망으로 남긴다(그때는 폭을 못 구해 unverified로 떨어진다).
    (1, None, "ca"): ("heuristic", None),
    # 일 강수 30/50mm — 원문이 "배수 불량 토양에서(in poorly drained soils)"를 필수 전제로
    # 달고 1차 출처 작물이 대두다(FinalReport §1-12). 전제가 빠진 채 5작물에 일괄 적용 중이다.
    (None, ANY_STAGE, "rainfall_daily"): ("unverified", "unverified"),
}

_HEURISTIC_TOLERANCE = 1e-6


def _auto_kind(optimal_min, optimal_max, allowed_min, allowed_max, side: str) -> str | None:
    """±50% 휴리스틱인지 판정한다. `allowed = optimal 경계 ∓ (optimal 폭 x 0.5)`.

    0021이 사과 허용경계를 만들 때 쓴 식이고, 0019(오이 pH·감자 유기물·상추 유효인산)도
    같다. 폭을 계산할 수 없으면(단측 밴드 등) 판정을 포기하고 None을 돌려준다 —
    모르는 것을 heuristic으로 채우지 않는다.
    """
    bound = allowed_min if side == "min" else allowed_max
    if bound is None:
        return None
    if optimal_min is None or optimal_max is None:
        return "unverified"
    half = (float(optimal_max) - float(optimal_min)) * 0.5
    expected = float(optimal_min) - half if side == "min" else float(optimal_max) + half
    if abs(float(bound) - expected) <= _HEURISTIC_TOLERANCE:
        return "heuristic"
    return "unverified"


def _resolve_kinds(row) -> tuple[str | None, str | None]:
    # 구체적인 것부터: 그 단계 전용 → 그 작물의 모든 단계 → 전 작물 공통.
    override = (
        _KIND_OVERRIDE.get((row.crop_id, row.growth_stage, row.indicator))
        or _KIND_OVERRIDE.get((row.crop_id, ANY_STAGE, row.indicator))
        or _KIND_OVERRIDE.get((None, ANY_STAGE, row.indicator))
        or (None, None)
    )
    kinds = []
    for side, forced in zip(("min", "max"), override):
        auto = _auto_kind(
            row.optimal_min, row.optimal_max, row.allowed_min, row.allowed_max, side
        )
        bound = row.allowed_min if side == "min" else row.allowed_max
        # 경계가 없으면 성격도 없다. 다만 `not_applicable`은 "경계는 있으나 개념이 없다"를
        # 뜻하므로 경계가 있을 때만 붙인다.
        kinds.append(None if bound is None else (forced or auto))
    return kinds[0], kinds[1]


def upgrade() -> None:
    op.add_column("crop_growth_guide", sa.Column("cultivation_type", sa.String(), nullable=True))
    op.add_column("crop_growth_guide", sa.Column("allowed_min_kind", sa.String(), nullable=True))
    op.add_column("crop_growth_guide", sa.Column("allowed_max_kind", sa.String(), nullable=True))
    op.add_column("crop_growth_guide", sa.Column("method", sa.String(), nullable=True))

    # 같은 지표에 노지·시설 두 행을 두려면 유니크 키에 재배형이 들어가야 한다.
    # 0037의 감자 pH가 첫 사례다.
    op.drop_constraint("uq_guide", "crop_growth_guide", type_="unique")
    op.create_unique_constraint(
        "uq_guide",
        "crop_growth_guide",
        ["crop_id", "growth_stage", "indicator", "cultivation_type"],
    )

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, crop_id, growth_stage, indicator, optimal_min, optimal_max, "
            "       allowed_min, allowed_max "
            "  FROM crop_growth_guide"
        )
    ).fetchall()

    for row in rows:
        facility = row.crop_id in _FACILITY_CROPS and row.indicator in _SOIL_INDICATORS
        min_kind, max_kind = _resolve_kinds(row)
        bind.execute(
            sa.text(
                "UPDATE crop_growth_guide "
                "   SET cultivation_type = :ct, allowed_min_kind = :mink, "
                "       allowed_max_kind = :maxk, method = :method "
                " WHERE id = :id"
            ),
            {
                "id": row.id,
                "ct": "facility" if facility else "open_field",
                "mink": min_kind,
                "maxk": max_kind,
                "method": _METHOD_BY_INDICATOR.get(row.indicator),
            },
        )

    # 재배형은 유니크 키의 일부라 NULL이면 행 중복을 막지 못한다. 백필이 끝났으므로 잠근다.
    op.alter_column("crop_growth_guide", "cultivation_type", nullable=False)


def downgrade() -> None:
    op.alter_column("crop_growth_guide", "cultivation_type", nullable=True)
    op.drop_constraint("uq_guide", "crop_growth_guide", type_="unique")
    op.create_unique_constraint(
        "uq_guide", "crop_growth_guide", ["crop_id", "growth_stage", "indicator"]
    )
    for column in ("method", "allowed_max_kind", "allowed_min_kind", "cultivation_type"):
        op.drop_column("crop_growth_guide", column)
