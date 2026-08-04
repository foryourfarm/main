"""FarmML 2026-08-04 밴드 정합 — 사과 K·Ca, 감자 pH·유기물 (4건 UPDATE).

**왜**: `outcomes/`(FarmML 이관 계약)가 2026-08-04에 이 4개 밴드를 교체했는데 백엔드 시드는
그대로여서 계약 테스트 `test_guide_outcomes_contract.py`가 실패했다. 같은 밭에 두 구현이
다른 점수를 내는 상태다(`outcomes/README.md` "두 구현의 점수가 갈리면 안 되는 계약").

`outcomes` 쪽 주석은 이 변경을 "2026-08-04 교체(0033)"로 적었으나 **우리 `0033`은
`0033_long_term_recommendation`(무관한 테이블)이다.** 즉 그 번호는 FarmML 쪽 기대였을 뿐
백엔드엔 반영된 적이 없다. 이 파일이 실제 반영이다.

    작물·지표          종전(백엔드)              신규(outcomes)
    사과 k             0.6 / 0.9 / 0.45 / 1.05   0.3 / 0.6 / 0.15 / 0.75
    사과 ca            5.0 / NULL / 4.5 / NULL   5.0 / 6.0 / 4.5 / 6.5
    감자 ph            5.0 / 6.0 / 4.5 / 6.5     5.5 / 7.0 / 4.75 / 7.75
    감자 organic       30 / 47 / 10 / 55.5       20 / 30 / 15 / 35

네 건 모두 행이 이미 있어 INSERT가 아니라 UPDATE다(`0024`·`0027`·`0030`·`0031`이 심었다).

**⚠️ 점수가 내려간다. 회귀가 아니다.**
- 사과 `ca` 상한 복귀: 전국 토양 실측 중앙값 7.23 cmol/kg이 새 `allowed_max` 6.5 밖이라
  종전 100점이던 지역 다수가 감점된다. outcomes가 그 영향을 명시하고 채택한 값이다.
- 감자 `organic`: 상한이 47 → 30으로 내려가 유기물 많은 밭이 "과다"로 판정될 수 있다.

**⚠️ 물려받는 미해결 위험 2건 — outcomes가 스스로 🔴로 표시한 것을 그대로 옮긴다.**
1. 감자 `ph` 상한 7.0은 더뎅이병 구간을 포함한다(김점순 2012: pH 6.49에서 발병도 61.1%·
   상품률 37.0%). 총수량엔 유의차가 없어 **수량 기반 채점으로는 이 위험이 드러나지 않는다.**
   "노지 데이터가 있으면 노지를 쓴다"는 결정에 따라 채택했을 뿐 병해 위험이 사라진 게 아니다.
2. 사과 `ca` 상한 밖 감점 기울기에는 문헌 근거가 없다(FinalReport §3-1: 국내외 0건).
   outcomes는 상한 밖 점수를 "문헌 기반 점수"가 아니라 「기준 초과」·「참고」로만 노출하라고
   적었다 — 우리 UI 표기는 별도 과제다 `[확인 필요]`.

**⚠️ outcomes 주석의 재배형 서술은 우리 스키마에 해당하지 않는다 `[확인 필요]`.** 감자 `ph`
주석이 "백엔드는 같은 지표에 시설 행을 함께 두고 `load_guides()`가 open_field를 우선한다"고
적었지만, `crop_growth_guide`에는 재배형 컬럼이 없고 유니크 키가
`(crop_id, growth_stage, indicator)`라 한 지표에 두 행을 둘 수 없다. 노지/시설 분기는 우리
쪽에 **존재하지 않는 기능**이므로 노지 값 하나만 싣는다. FarmML에 알려야 한다.

`source_ref`도 함께 갱신한다 — 값만 바꾸고 근거 서술을 남겨두면 "이 숫자 어디서 왔나"에
답할 수 없다(§4).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0035"
down_revision: str | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONTRACT = (
    " outcomes/memory/crop_rules/{crop}.json soil_overrides와 같은 값이어야 한다"
    "(outcomes/README.md 계약, 2026-08-04 동기화)."
)

_APPLE_K_SOURCE = (
    "RDA 「작물별 비료사용처방」 5차(2022) p273 · 처방 2010 개정증보판 p.163(사과)·p.168(배) · "
    "배 교본 표5-25 — 치환성 K 0.30~0.60 cmol/kg. "
    "**2026-08-04 교체**: 종전 0.6~0.9(사과 교본 표5-21)는 같은 성격의 표 안에서 고립된 "
    "이상값이라는 판정이 반증 4건으로 굳었다. 2010판은 OCR 텍스트 레이어와 내장 이미지 육안 "
    "판독이라는 독립 경로 2개에서 같은 값이 나와 추출 오류가 배제됐다. allowed도 함께 옮긴다 "
    "— 0.45를 두면 allowed_min > optimal_min이 되어 허용구간이 최적구간을 못 감싼다. "
    "allowed는 완충구간 문헌이 없어 optimal 폭 ±50% 휴리스틱 [확인 필요]. "
    "[확인 필요] 1차 원출처(농촌진흥청 2006)는 미확보이며 2006판 존재 여부 자체가 미확인이다."
    + _CONTRACT.format(crop="apple")
)

_APPLE_CA_SOURCE = (
    "RDA 교본 개량목표 표5-21(원문 대조 검증됨) 치환성 Ca 5~6 cmol/kg. 양이온 목표비 "
    "Ca 65%:Mg 15%:K 5%. "
    "**2026-08-04 양측 밴드로 복귀(사용자 결정)**: `0030`이 원문 '5~6cmol/kg 이상' 표기를 근거로 "
    "상한을 NULL(단측)로 두었으나 다시 상한을 세운다 — 따라서 '기준 초과'라는 개념도 다시 "
    "성립한다. optimal_max 6.0은 표5-21 구간 상한 그대로다. "
    "🔵 allowed_max 6.5는 **문헌값이 아니라 역산치**다(outcomes allowed_max_kind=derived) — "
    "교본 p271 염기포화도 80% x kfia-inorganic-fertilizer-guide-2022 p102 CEC 10.0. "
    "🔴 상한 초과 구간의 감점 기울기에는 근거가 없다(국내외 문헌 0건) — 상한 밖 점수는 "
    "「문헌 기반 점수」가 아니라 「기준 초과·참고」로 노출해야 한다 [확인 필요]. "
    "전국 실측 중앙값 7.23 cmol/kg이 allowed_max 밖이라 다수 지역이 감점된다(밴드 변경 결과, "
    "버그 아님)."
    + _CONTRACT.format(crop="apple")
)

_POTATO_PH_SOURCE = (
    "RDA 「작물별 비료사용처방」 2010 개정증보판 p.49 「감자(노지재배)」 pH(1:5) 5.5~7.0. "
    "**2026-08-04 교체**: 종전 5.0~6.0(농업기술길잡이 033 교본 p71)에서 옮긴다 — "
    "'노지 데이터가 존재하는 감자의 pH와 온도는 노지 데이터를 이용한다'는 결정에 따라 노지 행을 "
    "1차 기준으로 쓴다. "
    "🔴 [확인 필요] 상한 7.0은 더뎅이병 구간을 포함한다 — 김점순 2012에서 pH 6.49일 때 "
    "발병도 61.1%·상품률 37.0%(무처리 86.3%)다. 총수량은 처리 간 유의차가 없어 수량 기반 "
    "채점으로는 이 위험이 드러나지 않는다. 노지 우선 원칙으로 채택한 값이고 병해 위험이 "
    "사라진 것은 아니다. "
    "[확인 필요] outcomes 주석은 백엔드가 시설 행을 함께 두고 open_field를 우선한다고 적었으나 "
    "crop_growth_guide에는 재배형 컬럼이 없다(유니크 키가 crop_id+growth_stage+indicator) — "
    "노지 값 하나만 싣는다. "
    "allowed는 붕괴점 문헌이 없어 optimal 폭 ±50% 휴리스틱 [확인 필요]."
    + _CONTRACT.format(crop="potato")
)

_POTATO_ORGANIC_SOURCE = (
    "RDA 「작물별 비료사용처방」 5차(2022) p83 표 · 2010 개정증보판 p.49 노지 행 — 유기물 "
    "20~30 g/kg. 두 판·두 재배형이 모두 같은 값이라 이 지표는 재배형 분기가 필요 없다. "
    "**2026-08-04 교체**: 종전 30~47은 문헌 밴드가 아니라 정진철 외 2003의 **실측범위**(10~47)를 "
    "그대로 쓰고 하한을 관측 상위절반으로 잡은 편집 판단이었다 — 원 논문은 단조 양의 상관만 "
    "제시하고 적정구간을 주지 않는다. "
    "🔴 [확인 필요] 같은 p83 각주는 비화산회토 21~50 / 화산회토 101~150으로 표와 어긋난다 — "
    "표 값을 채택했고 제주(화산회토) 분기는 보류 상태다."
    + _CONTRACT.format(crop="potato")
)

# (crop_id, indicator, optimal_min, optimal_max, allowed_min, allowed_max, source)
# 계약 테스트가 이 표를 읽어 outcomes와 대조한다 — 값을 SQL에 직접 박지 않는 이유다.
_BANDS: list[tuple[int, str, float, float, float, float, str]] = [
    (1, "k", 0.3, 0.6, 0.15, 0.75, _APPLE_K_SOURCE),
    (1, "ca", 5.0, 6.0, 4.5, 6.5, _APPLE_CA_SOURCE),
    (4, "ph", 5.5, 7.0, 4.75, 7.75, _POTATO_PH_SOURCE),
    (4, "organic", 20.0, 30.0, 15.0, 35.0, _POTATO_ORGANIC_SOURCE),
]

# downgrade에서 되돌릴 종전 값. (crop_id, indicator) → 4밴드.
# 사과 ca는 `0030`이 만든 단측 밴드(상한 NULL)로 돌아간다 — `0024`가 심은 5.0/6.0이 아니다.
_OLD_BANDS: dict[tuple[int, str], tuple[float, float | None, float, float | None]] = {
    (1, "k"): (0.6, 0.9, 0.45, 1.05),
    (1, "ca"): (5.0, None, 4.5, None),
    (4, "ph"): (5.0, 6.0, 4.5, 6.5),
    (4, "organic"): (30.0, 47.0, 10.0, 55.5),
}

_UPDATE = sa.text(
    """
    UPDATE crop_growth_guide
       SET optimal_min = CAST(:omin AS numeric), optimal_max = CAST(:omax AS numeric),
           allowed_min = CAST(:amin AS numeric), allowed_max = CAST(:amax AS numeric),
           source_ref = COALESCE(CAST(:src AS varchar), source_ref)
     WHERE crop_id = :crop AND growth_stage IS NULL AND indicator = CAST(:ind AS varchar)
    """
)


def upgrade() -> None:
    conn = op.get_bind()
    for crop_id, indicator, omin, omax, amin, amax, source in _BANDS:
        conn.execute(
            _UPDATE,
            {
                "crop": crop_id,
                "ind": indicator,
                "omin": omin,
                "omax": omax,
                "amin": amin,
                "amax": amax,
                "src": source,
            },
        )


def downgrade() -> None:
    # 값만 되돌린다. source_ref는 NULL을 넘겨 COALESCE로 건드리지 않는다 — 종전 서술을
    # 여기 다시 옮겨 적으면 원본(0024·0027·0030·0031)과 갈릴 위험만 생긴다.
    conn = op.get_bind()
    for (crop_id, indicator), (omin, omax, amin, amax) in _OLD_BANDS.items():
        conn.execute(
            _UPDATE,
            {
                "crop": crop_id,
                "ind": indicator,
                "omin": omin,
                "omax": omax,
                "amin": amin,
                "amax": amax,
                "src": None,
            },
        )
