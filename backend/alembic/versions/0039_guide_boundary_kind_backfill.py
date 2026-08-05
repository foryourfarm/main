"""crop_growth_guide 성격 메타 컬럼 백필 — 토양 33행 + 기온 9행 (finalplan.md P1).

**왜**: `0038`이 만든 5개 컬럼(`cultivation_type`/`allowed_min_kind`/`allowed_max_kind`/
`method`/`code_scores`)에 값을 채운다. 근거는 계약(`outcomes/memory/crop_rules/{작물}.json`)
이고, 백엔드 지침 행과 계약 밴드의 **지표명이 다르다** — 대응은
`tests/test_guide_outcomes_contract.py`의 `INDICATOR_ALIAS`를 그대로 쓴다(새로 만들지 않음):
ph→ph, organic_matter→organic, available_p→p2o5, k→k, ca→ca, mg→mg, ec→ec.

**토양 지표(soil_overrides, 33행)**: 5작물의 값이 이미 계약과 정확히 일치하는 상태다
(0023·0024·0028·0029·0030·0031·0035가 값을 맞춰 왔다) — 그래서 이 마이그레이션은 값을
바꾸지 않고 성격·재배형·측정법만 옮긴다. `code_scores`는 채우지 않는다 —
`subsoil_texture` 지침 행 자체가 아직 없다(P4 작업), 컬럼만 비어 있다.

**기온 지표(temperature_guides, 9행) — 🔴 "같은 방향 + 같은 값"일 때만 성격을 옮긴다.**
계약의 `temperature_guides`는 작물당 단일 밴드인데 백엔드는 생육단계별로 갈라져 있어
구조가 다르다(사과는 4~10월 단일 밴드 optimal 18~28/allowed 13.5~33.0인데 백엔드는
fruit_growth 18~24·maturity 20~25·coloring 12~13 3행이다). 값 대조 없이 성격을 그대로
옮기면 사과 기온 하한이 `literature_limit`으로 잘못 표기되고, 그 결과 사과 0점 지역이
93→121로 늘어난다(계약 문서 실측 기록). 그래서 각 백엔드 행의 `allowed_min`이 계약 밴드의
`allowed_min`과 **정확히 같을 때만** `allowed_min_kind`를 옮기고(`allowed_max`도 같은
방식, max는 max끼리만), 값이 다르거나 한쪽이 NULL이면 그 방향은 NULL로 둔다.
`cultivation_type`은 값 대조 없이 지표 대응만으로 옮긴다 — 재배형은 경계값과 무관한
출처 속성이다. 계약 기온 밴드가 5작물 전부 `open_field`라 기온 9행도 전부 `open_field`다.

**기온 행의 `method`는 전부 NULL이다.** 계약의 기온 `method`는 "지역 월평균 기온의 N~M월
산술평균" 같은 **생육기 집계 방식**을 서술하는데, 백엔드 기온 행이 실제로 받는 값은 그 달의
월평년(기상청 `weather_climatology`)이다. 그대로 옮기면 백엔드 행이 실제로 쓰지 않는 집계
방식을 쓴 것처럼 거짓 표기가 된다 — 그래서 기온 행엔 NULL을 둔다(토양 지표만 `method`를
옮긴다).

**대응 밴드가 없는 지표는 전부 NULL로 둔다(손대지 않는다)**: `rainfall_daily`(5작물,
계약이 다루지 않음), `temp_night_min`(감자 tuber — 계약 기온 밴드에 야간 구분이 없다).
`0013`이 이미 지운 사과 `rainfall_monthly` 계열도 대상 행 자체가 없다.

값 산출 근거(각 행 왜 이 kind인지)는 아래 상수 표와 `outcomes/memory/crop_rules/*.json`을
나란히 대조하면 된다 — `tests/test_guide_outcomes_contract.py`가 이 표를 계약과 자동 대조한다.
"""
from collections.abc import Sequence
from decimal import Decimal

import sqlalchemy as sa
from alembic import op

revision: str = "0039"
# 🔴 0038이 아니라 0042다. 아래 `_assert_band`가 지침 행의 존재·허용경계를 검증하는데,
# 프로덕션에는 `0019` 부분 적용으로 6건이 결손돼 있어 이 마이그레이션이 RuntimeError로 죽었다
# (2026-08-05 실배포). `0042`가 그 결손을 먼저 메운다 — 자세한 경위는 0042 docstring 참고.
down_revision: str | None = "0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ---------------------------------------------------------------------------
# 토양 지표 method — 같은 문구를 여러 작물이 공유하는 경우가 실제로 있다(계약 원문이
# 글자 그대로 같다). 다른 문구는 각 작물·지표 전용으로 따로 적는다.
# ---------------------------------------------------------------------------
_UNKNOWN_PH_METHOD = "unknown [확인 필요] — 교본이 pH 추출비를 명시하지 않는다."
_UNKNOWN_ORGANIC_METHOD = "unknown [확인 필요] — 정량법 미명시. 단위 g/kg 확인."
_UNKNOWN_CATION_METHOD = (
    "unknown [확인 필요] — 교본이 치환성 양이온 침출액(1N NH4OAc 등)을 명시하지 않는다. "
    "단위 cmol/kg만 확인."
)
_NH4OAC_METHOD = "1M NH4OAc 침출 후 AA·ICP. 국내 표준. [확인 필요] 실측측 미확인."
_TYURIN_METHOD = (
    "Tyurin법, 그늘 풍건 후 20 mesh 체 통과 시료. 국내 표준"
    "(national-agri-environment-monitoring-2020.md). [확인 필요] 실측측 정량법 미확인."
)

_APPLE_P2O5_METHOD = (
    "Lancaster법(국내 표준). 2026-08-03 갱신 — 농촌진흥청 「토양 및 식물체 분석」(2007) "
    "국내 표준이 Lancaster로 확정됐고(national-agri-environment-monitoring-2020.md), "
    "종전에 6배 갈림의 근거로 삼던 'RDA 비료사용처방 Bray-1 30~50 mg/kg'은 원문에 존재하지 "
    "않는 창작 수치로 확인됐다(kfia-inorganic-fertilizer-guide-2022.md, 322쪽 중 Bray 0건). "
    "6배 프로토콜 갈림 우려는 해소. [확인 필요] 교본 자체에는 추출법 표기가 없고 실측측"
    "(흙토람) 추출법도 미확인."
)
_PEAR_P2O5_METHOD = (
    "Lancaster법(국내 표준). 2026-08-05 갱신 — 종전에 '약 6배 갈림'의 근거로 적어둔 'RDA "
    "비료사용처방 Bray-1 30~50 mg/kg'은 원문에 존재하지 않는 창작 수치로 확인됐다"
    "(kfia-inorganic-fertilizer-guide-2022.md, 322쪽 중 Bray 0건 — 사과 파일·_shared.json에 "
    "같은 정정이 이미 반영돼 있었고 배 파일만 폐기된 주장을 들고 있었다). 국내 표준은 "
    "농촌진흥청 「토양 및 식물체 분석」(2007) 기준 Lancaster법이다"
    "(national-agri-environment-monitoring-2020.md). 6배 프로토콜 갈림 우려는 해소. "
    "⚠️ 이 노트를 근거로 배 P 밴드를 Bray 척도(약 10배 차)에 맞춰 재척도하면 안 된다 — "
    "존재하지 않는 밴드에 맞추는 것이다. [확인 필요] 교본 자체에는 추출법 표기가 없고 "
    "실측측(흙토람) 추출법도 미확인."
)
_CUCUMBER_PH_METHOD = (
    "1:5 물(H2O) 침출, pH meter. 처방 5차 화학성 표 헤더가 pH(1:5)로 명시하고 농촌진흥청 "
    "「토양 및 식물체 분석」(2007) 국내 표준과 일치한다"
    "(knowledge-base/papers/common/national-agri-environment-monitoring-2020.md 측정법 표). "
    "[확인 필요] 실측측(흙토람 API -> data/01_soil_chemistry_modified.csv pH)의 추출비·용매는 "
    "여전히 미확인 — 같은 시료가 pH(H2O) 5.8 / pH(KCl) 4.6으로 1.2 갈리는 사례 확인됨"
    "(korean-soil-drainage-idonghyun-2023)."
)
_CUCUMBER_P2O5_METHOD = (
    "Lancaster법. 국내 표준(national-agri-environment-monitoring-2020.md). 종전 "
    "_shared.json이 경고하던 'Bray-1 30~50 mg/kg과 약 6배 갈림'은 그 Bray 수치 자체가 "
    "원문에 없는 창작값으로 확인돼 해소됐다(kfia-inorganic-fertilizer-guide-2022.md, 322쪽 "
    "중 Bray 0건). [확인 필요] 실측측 추출법 미확인."
)
_CUCUMBER_EC_METHOD = (
    "토양:증류수 1:5 침출, EC meter(국내 표준, national-agri-environment-monitoring-2020.md). "
    "입력은 data/ml/soil_ec_by_region.csv의 `ec_median`(시군구 필지 실측 중앙값) — 평균이 "
    "아니라 중앙값을 쓰는 이유는 분포가 오른쪽으로 심하게 치우쳐(중앙값 0.61 vs 평균 2.11, "
    "최대 30.0) 시설 염류집적 필지 몇 곳이 노지 위주 지역을 통째로 감점시키기 때문이다. "
    "[확인 필요] 흙토람 elcd가 1:5 비환산인지 지도자료용 ×5 환산인지 미확인 — 국가보고서 "
    "실측(밭 1.03)과 우리 분포(중앙값 0.49)가 같은 자릿수라 비환산 1:5로 보이나 확정은 "
    "아니다. 척도가 ×5라면 이 밴드는 통째로 어긋난다."
)
_POTATO_PH_METHOD = (
    "1:5 물(H2O) 침출 가정. 교본이 측정법을 명시하지 않으나 국내 표준이 1:5 물 침출이다"
    "(national-agri-environment-monitoring-2020.md). [확인 필요] 교본 자체에는 표기 없음, "
    "실측측(흙토람) 추출비도 미확인."
)
_POTATO_ORGANIC_METHOD = (
    "unknown [확인 필요] — P10(정진철 외 2003)이 유기물 정량법을 명시하지 않는다. "
    "단위 g/kg만 확인됨."
)
_POTATO_P2O5_METHOD = (
    "Lancaster법. 국내 표준(national-agri-environment-monitoring-2020.md). [확인 필요] "
    "실측측 추출법 미확인."
)
_POTATO_EC_METHOD = (
    "토양:증류수 1:5 침출, EC meter(국내 표준). 입력은 data/ml/soil_ec_by_region.csv의 "
    "`ec_median`(시군구 필지 실측 중앙값) — 분포 왜곡 대응 근거는 cucumber.json ec 참조. "
    "[확인 필요] 흙토람 elcd의 환산 여부(1:5 비환산 vs 지도자료용 ×5) 미확인."
)
_LETTUCE_PH_METHOD = (
    "1:5 물(H2O) 침출, pH meter. 2026-08-03 확정 — 이 표의 정체가 RDA 「작물별 비료사용처방」 "
    "5차 개정본(2022) p169임이 확인됐고 그 화학성 표 헤더가 pH(1:5)이며 국내 표준"
    "(농촌진흥청 「토양 및 식물체 분석」 2007)과 일치한다. [확인 필요] 실측측(흙토람) 추출비 "
    "미확인."
)
_LETTUCE_P2O5_METHOD = (
    "Lancaster법. 2026-08-03 확정 — 국내 표준(national-agri-environment-monitoring-2020.md). "
    "종전 '추출법 미명시, 최대 6배 프로토콜 이슈 노출' 경고는 그 대조군이던 Bray-1 30~50 "
    "mg/kg 자체가 원문에 없는 창작값으로 확인돼(kfia-inorganic-fertilizer-guide-2022.md) "
    "해소됐다. [확인 필요] 실측측 추출법 미확인."
)
_LETTUCE_EC_METHOD = (
    "토양:증류수 1:5 침출, EC meter(국내 표준). 입력은 data/ml/soil_ec_by_region.csv의 "
    "`ec_median`(시군구 필지 실측 중앙값) — 분포 왜곡 대응 근거는 cucumber.json ec 참조. "
    "[확인 필요] 흙토람 elcd의 환산 여부 미확인. 또한 상추 교본이 EC 기준을 셋(포장 2 dS/m "
    "이하 / 연작관리 1.5 mS/cm 이하 / 육묘 상토 1.0~2.0 포화점토법) 제시하고 스스로 '분석 "
    "방법에 따라 적정 기준이 달라진다'고 인정한다 — 여기서는 포장 기준만 쓴다."
)

# ---------------------------------------------------------------------------
# 토양 지표 33행. (crop_id, indicator, cultivation_type, allowed_min_kind,
# allowed_max_kind, method) — growth_stage는 토양 지표 전부 NULL(전기간)이라 표에 없다.
# 값(optimal/allowed)은 이미 계약과 일치해 이 마이그레이션에서 건드리지 않는다.
# ---------------------------------------------------------------------------
SOIL_ROWS: list[tuple[int, str, str, str, str, str]] = [
    # 사과(1) — RDA 교본 개량목표, 전부 open_field. ca만 allowed_max_kind=derived —
    # 원문 '5~6cmol/kg 이상'의 상한을 우리가 역산했다(0035 소스 참고).
    (1, "ph", "open_field", "heuristic", "heuristic", _UNKNOWN_PH_METHOD),
    (1, "organic", "open_field", "heuristic", "heuristic", _UNKNOWN_ORGANIC_METHOD),
    (1, "p2o5", "open_field", "heuristic", "heuristic", _APPLE_P2O5_METHOD),
    (1, "k", "open_field", "heuristic", "heuristic", _UNKNOWN_CATION_METHOD),
    (1, "ca", "open_field", "heuristic", "derived", _UNKNOWN_CATION_METHOD),
    (1, "mg", "open_field", "heuristic", "heuristic", _UNKNOWN_CATION_METHOD),
    # 배(2) — 같은 교본 계열, 전부 open_field·heuristic/heuristic(ca도 양측 heuristic —
    # 배 교본 표5-25는 사과와 달리 상한이 있다).
    (2, "ph", "open_field", "heuristic", "heuristic", _UNKNOWN_PH_METHOD),
    (2, "organic", "open_field", "heuristic", "heuristic", _UNKNOWN_ORGANIC_METHOD),
    (2, "p2o5", "open_field", "heuristic", "heuristic", _PEAR_P2O5_METHOD),
    (2, "k", "open_field", "heuristic", "heuristic", _UNKNOWN_CATION_METHOD),
    (2, "ca", "open_field", "heuristic", "heuristic", _UNKNOWN_CATION_METHOD),
    (2, "mg", "open_field", "heuristic", "heuristic", _UNKNOWN_CATION_METHOD),
    # 오이(3) — RDA 처방 5차 시설재배토양 진단기준표, 전부 facility. ph만
    # cultivable_range/cultivable_range(제주 재배기술서 재배 가능 범위 5.5~6.8).
    (3, "ph", "facility", "cultivable_range", "cultivable_range", _CUCUMBER_PH_METHOD),
    (3, "organic", "facility", "heuristic", "heuristic", _TYURIN_METHOD),
    (3, "p2o5", "facility", "heuristic", "heuristic", _CUCUMBER_P2O5_METHOD),
    (3, "k", "facility", "heuristic", "heuristic", _NH4OAC_METHOD),
    (3, "ca", "facility", "heuristic", "heuristic", _NH4OAC_METHOD),
    (3, "mg", "facility", "heuristic", "heuristic", _NH4OAC_METHOD),
    (3, "ec", "facility", "not_applicable", "heuristic", _CUCUMBER_EC_METHOD),
    # 감자(4) — ph만 open_field(2010 개정증보판 「감자(노지재배)」 p.49), 나머지 6개는
    # 처방 5차 시설재배토양 진단기준표라 facility.
    (4, "ph", "open_field", "heuristic", "heuristic", _POTATO_PH_METHOD),
    (4, "organic", "facility", "heuristic", "heuristic", _POTATO_ORGANIC_METHOD),
    (4, "p2o5", "facility", "heuristic", "heuristic", _POTATO_P2O5_METHOD),
    (4, "k", "facility", "heuristic", "heuristic", _NH4OAC_METHOD),
    (4, "ca", "facility", "heuristic", "heuristic", _NH4OAC_METHOD),
    (4, "mg", "facility", "heuristic", "heuristic", _NH4OAC_METHOD),
    (4, "ec", "facility", "not_applicable", "heuristic", _POTATO_EC_METHOD),
    # 상추(5) — RDA 처방 5차 p169, 전부 facility. ec만 allowed_max_kind=literature_threshold
    # (노안성 2004 시설채소 수량 20% 감소 EC 2.9 — 5작물 중 EC 상한이 문헌값인 유일한 작물).
    (5, "ph", "facility", "heuristic", "heuristic", _LETTUCE_PH_METHOD),
    (5, "organic", "facility", "heuristic", "heuristic", _TYURIN_METHOD),
    (5, "p2o5", "facility", "heuristic", "heuristic", _LETTUCE_P2O5_METHOD),
    (5, "k", "facility", "heuristic", "heuristic", _NH4OAC_METHOD),
    (5, "ca", "facility", "heuristic", "heuristic", _NH4OAC_METHOD),
    (5, "mg", "facility", "heuristic", "heuristic", _NH4OAC_METHOD),
    (5, "ec", "facility", "not_applicable", "literature_threshold", _LETTUCE_EC_METHOD),
]

# ---------------------------------------------------------------------------
# 기온 지표 9행. (crop_id, growth_stage, cultivation_type, allowed_min_kind,
# allowed_max_kind) — indicator는 전부 temp_day, method는 전부 NULL(위 사유).
#
# kind는 "같은 방향 + 같은 값"일 때만 부여했다 — 계약 밴드의 allowed_min/allowed_max와
# 백엔드 이 행의 allowed_min/allowed_max를 방향별로 대조한 결과다:
#   사과(1) 계약 allowed 13.5~33.0 — 3행 전부 값이 다르다 -> 전부 NULL/NULL.
#   배(2)   계약 allowed 17~23   — growing 17/23와 정확히 일치 -> cultivable_range/cultivable_range.
#   오이(3) 계약 allowed 5~35   — growing 5/35와 정확히 일치 -> literature_limit/literature_limit.
#   감자(4) 계약 allowed 10.0~27.0 — early는 allowed_min=-3(불일치, NULL)·allowed_max=27(일치),
#           tuber는 allowed_min=NULL(자동 불일치)·allowed_max=27(일치).
#   상추(5) 계약 allowed 2.5~36 — spring·fall 둘 다 2.5/36와 정확히 일치.
# ---------------------------------------------------------------------------
TEMP_ROWS: list[tuple[int, str, str, str | None, str | None]] = [
    (1, "fruit_growth", "open_field", None, None),
    (1, "maturity", "open_field", None, None),
    (1, "coloring", "open_field", None, None),
    (2, "growing", "open_field", "cultivable_range", "cultivable_range"),
    (3, "growing", "open_field", "literature_limit", "literature_limit"),
    (4, "early", "open_field", None, "literature_limit"),
    (4, "tuber", "open_field", None, "literature_limit"),
    (5, "spring", "open_field", "literature_limit", "literature_limit"),
    (5, "fall", "open_field", "literature_limit", "literature_limit"),
]

# ---------------------------------------------------------------------------
# 각 행의 kind 판정 근거가 된 허용경계 값. `upgrade()`가 **실행 시점에 실제 DB 행과
# 대조**하고 다르면 즉시 실패한다.
#
# 왜 필요한가: 위 두 표의 kind는 계약 밴드와 백엔드 밴드를 **작성 시점에** 대조해 정했다.
# 그런데 마이그레이션은 (crop_id, growth_stage, indicator)로 행을 찾아 UPDATE하므로,
# 밴드 값이 그 사이 달라진 DB에서는 **계약과 다른 밴드에 계약 성격을 붙인다.** 실제로
# 그런 DB가 있었다 — 로컬 dev DB는 `alembic_version=0037`인데 0012·0021·0023·0024·0031·
# 0035의 데이터 효과가 빠져 사과 pH가 5.5~7.0(계약은 5.75~6.75)이었다. 그 상태에
# `heuristic`을 붙이면 "이 경계는 ±50% 휴리스틱"이라는 거짓 표기가 되고, 더 나쁘게는
# 기온 쪽에서 `literature_limit`이 계약과 다른 지점에 붙어 **0점 경계가 문헌이 말하지 않은
# 곳으로 옮겨간다**(P2가 이 kind로 0점을 준다).
#
# NULL로 남기고 넘어가지 않고 **실패**시키는 이유: 밴드가 계약과 다른 DB는 이미 잘못된
# 점수를 서빙하고 있다. 조용히 성격만 비워두면 그 사실이 아무 데도 드러나지 않는다.
# 계약 테스트(`test_guide_outcomes_contract.py`)는 DB 없이 상수 표만 대조하므로 이 드리프트를
# 잡을 수 없다 — 실행 시점 대조가 유일한 감지 지점이다.
# ---------------------------------------------------------------------------
EXPECTED_SOIL_BOUNDS: dict[tuple[int, str], tuple[str | None, str | None]] = {
    (1, "ph"): ("5.75", "6.75"),
    (1, "organic"): ("20", "40"),
    (1, "p2o5"): ("150", "350"),
    (1, "k"): ("0.15", "0.75"),
    (1, "ca"): ("4.5", "6.5"),
    (1, "mg"): ("1.25", "2.25"),
    (2, "ph"): ("5.75", "6.75"),
    (2, "organic"): ("20", "40"),
    (2, "p2o5"): ("150", "350"),
    (2, "k"): ("0.15", "0.75"),
    (2, "ca"): ("4.5", "6.5"),
    (2, "mg"): ("1.25", "2.25"),
    (3, "ph"): ("5.5", "6.8"),
    (3, "organic"): ("15", "35"),
    (3, "p2o5"): ("350", "550"),
    (3, "k"): ("0.65", "0.85"),
    (3, "ca"): ("4.5", "6.5"),
    (3, "mg"): ("1.25", "2.25"),
    (3, "ec"): ("0", "3"),
    (4, "ph"): ("4.75", "7.75"),
    (4, "organic"): ("15", "35"),
    (4, "p2o5"): ("200", "400"),
    (4, "k"): ("0.45", "0.65"),
    (4, "ca"): ("4", "6"),
    (4, "mg"): ("1.25", "2.25"),
    (4, "ec"): ("0", "3"),
    (5, "ph"): ("6.25", "7.25"),
    (5, "organic"): ("15", "35"),
    (5, "p2o5"): ("175", "475"),
    (5, "k"): ("0.3", "0.7"),
    (5, "ca"): ("5.5", "7.5"),
    (5, "mg"): ("1.75", "2.75"),
    (5, "ec"): ("0", "2.9"),
}

# 기온 9행. 이 값이 곧 TEMP_ROWS kind 판정의 좌변이다 — 계약 밴드(사과 13.5~33.0,
# 배 17~23, 오이 5~35, 감자 10~27, 상추 2.5~36)와 방향별로 같은 값일 때만 kind가 붙었다.
EXPECTED_TEMP_BOUNDS: dict[tuple[int, str], tuple[str | None, str | None]] = {
    (1, "fruit_growth"): ("15", "31"),
    (1, "maturity"): ("17.5", "27.5"),
    (1, "coloring"): ("11.5", "13.5"),
    (2, "growing"): ("17", "23"),
    (3, "growing"): ("5", "35"),
    (4, "early"): ("-3", "27"),
    (4, "tuber"): (None, "27"),
    (5, "spring"): ("2.5", "36"),
    (5, "fall"): ("2.5", "36"),
}

_SOIL_SELECT = sa.text(
    """
    SELECT allowed_min, allowed_max FROM crop_growth_guide
     WHERE crop_id = :crop AND growth_stage IS NULL AND indicator = :ind
    """
)
_TEMP_SELECT = sa.text(
    """
    SELECT allowed_min, allowed_max FROM crop_growth_guide
     WHERE crop_id = :crop AND growth_stage = :stage AND indicator = 'temp_day'
    """
)


def _decimal(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _assert_band(conn, select, params, expected, label: str) -> None:
    """대상 행이 존재하고 그 허용경계가 kind 판정 근거와 같은지 확인. 다르면 실패."""
    row = conn.execute(select, params).first()
    if row is None:
        raise RuntimeError(
            f"0039: {label} 지침 행이 없다 — 백필 대상이 사라졌다. 이 마이그레이션이 "
            "가정하는 지침 행 집합(0004~0035)이 바뀌었는지 확인할 것."
        )
    actual = (_decimal(row.allowed_min), _decimal(row.allowed_max))
    want = (_decimal(expected[0]), _decimal(expected[1]))
    if actual != want:
        raise RuntimeError(
            f"0039: {label} 허용경계가 성격 판정 근거와 다르다 — DB {actual} vs 기대 {want}. "
            "이 DB의 밴드는 계약(outcomes/memory/crop_rules)과 어긋나 있어 계약 성격을 붙이면 "
            "거짓 표기가 된다. 밴드를 먼저 계약과 맞춘 뒤(0023·0024·0028~0031·0035가 그 일을 "
            "한다) 다시 실행할 것."
        )


def _assert_rowcount(result, expected: int, label: str) -> None:
    if result.rowcount != expected:
        raise RuntimeError(
            f"0039: {label} UPDATE가 {result.rowcount}행을 갱신했다(기대 {expected}행) — "
            "지침 행 식별 키가 어긋났다."
        )


_SOIL_UPDATE = sa.text(
    """
    UPDATE crop_growth_guide
       SET cultivation_type = :ct, allowed_min_kind = :amink,
           allowed_max_kind = :amaxk, method = :method
     WHERE crop_id = :crop AND growth_stage IS NULL AND indicator = :ind
    """
)
_TEMP_UPDATE = sa.text(
    """
    UPDATE crop_growth_guide
       SET cultivation_type = :ct, allowed_min_kind = :amink, allowed_max_kind = :amaxk
     WHERE crop_id = :crop AND growth_stage = :stage AND indicator = 'temp_day'
    """
)
_SOIL_CLEAR = sa.text(
    """
    UPDATE crop_growth_guide
       SET cultivation_type = NULL, allowed_min_kind = NULL,
           allowed_max_kind = NULL, method = NULL
     WHERE crop_id = :crop AND growth_stage IS NULL AND indicator = :ind
    """
)
_TEMP_CLEAR = sa.text(
    """
    UPDATE crop_growth_guide
       SET cultivation_type = NULL, allowed_min_kind = NULL, allowed_max_kind = NULL
     WHERE crop_id = :crop AND growth_stage = :stage AND indicator = 'temp_day'
    """
)


def upgrade() -> None:
    conn = op.get_bind()
    for crop_id, indicator, cultivation_type, amink, amaxk, method in SOIL_ROWS:
        params = {"crop": crop_id, "ind": indicator}
        label = f"crop={crop_id} {indicator}"
        _assert_band(conn, _SOIL_SELECT, params, EXPECTED_SOIL_BOUNDS[(crop_id, indicator)], label)
        result = conn.execute(
            _SOIL_UPDATE,
            params | {"ct": cultivation_type, "amink": amink, "amaxk": amaxk, "method": method},
        )
        _assert_rowcount(result, 1, label)
    for crop_id, stage, cultivation_type, amink, amaxk in TEMP_ROWS:
        params = {"crop": crop_id, "stage": stage}
        label = f"crop={crop_id} {stage} temp_day"
        _assert_band(conn, _TEMP_SELECT, params, EXPECTED_TEMP_BOUNDS[(crop_id, stage)], label)
        result = conn.execute(
            _TEMP_UPDATE, params | {"ct": cultivation_type, "amink": amink, "amaxk": amaxk}
        )
        _assert_rowcount(result, 1, label)


def downgrade() -> None:
    """5개 컬럼을 다시 NULL로 되돌린다.

    사람이 upgrade 후 이 컬럼을 수동으로 채웠다면 그 값은 사라진다. 허용 가능한 설계인
    이유: `CLAUDE.md` §10이 마스터 데이터(`crop_growth_guide`)의 런타임 수정을 금지하고
    변경은 마이그레이션으로만 하게 규정한다 — 수동 편집분이 존재하는 상황 자체가 규칙
    위반이라 보존 대상이 아니다.
    """
    conn = op.get_bind()
    for crop_id, indicator, *_rest in SOIL_ROWS:
        conn.execute(_SOIL_CLEAR, {"crop": crop_id, "ind": indicator})
    for crop_id, stage, *_rest in TEMP_ROWS:
        conn.execute(_TEMP_CLEAR, {"crop": crop_id, "stage": stage})
