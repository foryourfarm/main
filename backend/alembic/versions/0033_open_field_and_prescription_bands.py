"""감자 노지 pH 행 신설 + 처방서 밴드 3건 정정 + 2차 인용 출처 명기 (2026-08-04).

FinalReport.md의 사용자 결정을 적재한다. `0032`가 만든 `cultivation_type`이 없으면 첫 항목이
불가능하므로 반드시 그 뒤에 온다.

## 1. 감자 pH — 노지·시설 두 행 (§1-1 + §2-4)

사용자 결정이 두 갈래로 나왔다가 재확인으로 합쳐졌다:
- §2-4 ⓐ = `5.5~6.2` — RDA 「작물별 비료사용처방」 5차(2022) p83. **시설재배토양** 진단기준.
- §1-1 = *"노지 데이터가 존재하는 감자의 pH와 온도는 노지 데이터를 이용"* → `5.5~7.0`.
  처방서 **2010 개정증보판 p.49 「감자(노지재배)」**.
- **재확인 결과: 두 행을 다 적재하고 노지 행으로 채점한다.** `0032`의 재배형 컬럼이 있어
  둘을 동시에 표현할 수 있고, `load_guides()`가 `open_field`를 우선 고른다.

⭐ **조사 중 확인된 것**: 2010판 p.49의 「감자(노지재배)」 행은 pH만이 아니라 **화학성 전
항목**을 준다 — pH 5.5~7.0 / OM 20~30 / P₂O₅ 250~350 / K 0.50~0.60 / Ca 4.5~5.5 /
Mg 1.5~2.0 / EC 2 이하. 이 중 **P·K·Ca·Mg·EC 5칸은 현행 시드와 완전히 같다**(0031·0028이
처방 5차에서 넣은 값과 일치). 즉 감자에서 노지와 시설이 실제로 갈리는 것은 **pH와 유기물
둘뿐**이고, 나머지는 두 판·두 재배형이 같은 값을 준다. 그래서 pH·유기물만 다룬다.

🔴 **상한 7.0이 더뎅이병 구간을 포함한다**는 우려는 유효하다(김점순 2012: pH 6.49에서
발병도 61.1%·상품률 37.0%, 무처리 86.3%). 노지 행을 채점에 쓰기로 한 것은 사용자 결정이며,
이 단서를 `source_ref`에 남긴다. 총수량은 처리 간 유의차가 없어 **수량 채점으로는 안 보인다**.

⭐ **오이·상추에는 이 문제가 없다는 것이 원문으로 확증됐다.** 같은 2010판 표의 제목이
**「오이(노지·시설재배)」·「상추(노지·시설재배)」**다 — 국가 표준 자신이 두 작물에는
재배형 공통 밴드를 쓴다. 값도 현행과 전부 일치한다. 종전에 "노지 값이 없어서 시설 값을
쓰고 있다"고 적었던 것은 **"국가 자료가 둘을 구분하지 않는다"**로 정정된다.

## 2. 감자 유기물 20~30 g/kg (§1-6 ⓐ)

종전 `30~47`은 문헌 밴드가 아니라 **실측범위(10~47)를 그대로 쓰고 하한을 관측 상위절반으로
잡은 편집 판단**이었다(정진철 2003은 단조 양의 상관만 제시하고 적정구간을 주지 않는다).
§1-6 ⓐ(작물별 처방기준을 1차로)에 따라 처방서 값으로 교체한다 — **처방 5차 p83 표와
2010판 노지 행이 둘 다 20~30으로 일치**해 판·재배형을 가로질러 확인된 값이다.

🔴 같은 p83 **각주**는 비화산회토 21~50 / 화산회토 101~150을 적어 표와 어긋난다. 표 값을
채택하되 각주를 `source_ref`에 남긴다. 제주(화산회토) 분기는 §2-8 보류 상태다.

## 3. 사과 치환성 K 0.30~0.60 (§1-2 ⓐ + §1-3 ⓐ)

교본 표5-21의 `0.6~0.9`가 **고립된 이상값**이라는 판정이 4건으로 굳었다: 처방 5차 p273 ·
2010판 사과(p.163) · 2010판 배(p.168) · 배 교본 표5-25. 특히 2010판은 OCR 텍스트 레이어와
내장 이미지 육안 판독이라는 **독립 경로 2개**에서 같은 값이 나와 오독 가능성이 배제됐다.

`allowed`는 §1-3 ⓐ대로 배와 같은 ±50% 규칙을 적용한다 — 그러지 않으면 종전 `allowed_min
0.45`가 새 `optimal_min 0.30`보다 커져 **허용구간이 최적구간을 감싸지 못하는 논리 파탄**이
된다. 성격은 `heuristic`이며 `0032`의 컬럼에 그대로 적힌다.

## 4. 2차 인용 출처 명기 (§1-15)

값은 건드리지 않고 `source_ref`만 고친다. **값이 아니라 출처가 틀렸던 것**이다.
- 감자 야간 28℃ — "Zhang 2024"로 적혀 있으나 실제로는 그 논문 Discussion의 **2차 인용[24]**.
  국내 1차 자료(농사로 「덩이줄기 비대 정지 27~30℃」)로 교체하되 🔴 **그 자료는 주야 구분이
  없다** — 시드는 「야간」이므로 성격이 같다고 단정할 수 없다는 단서를 반드시 병기한다(§1-15 ⓐ).
- 감자 잎 냉해 -3℃ — "Stegner 2019"의 **2차 인용[25]**이고 교체할 1차 자료가 없다. 게다가
  원문이 잎은 결빙 후 10~78분만 견디고 "2차 결빙은 확률적 사건"이라 밝혀 **단일 임계로는
  판정 자체가 불가능**하다. 2차 인용임을 명기만 한다(§1-15 ⓑ).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_HEURISTIC = (
    " allowed_min/max는 완충구간 문헌이 없어 optimal 폭 ±50% 휴리스틱(CLAUDE.md §8) "
    "[확인 필요] — allowed_*_kind='heuristic'."
)

# --- 감자 pH ---------------------------------------------------------------
_POTATO_PH_OPEN_FIELD = (5.5, 7.0, 4.75, 7.75)
_POTATO_PH_FACILITY = (5.5, 6.2, 5.15, 6.55)
_POTATO_PH_FACILITY_OLD = (5.0, 6.0, 4.5, 6.5)  # 0031이 넣은 교본값 — downgrade에서 복원

_POTATO_PH_OPEN_FIELD_SOURCE = (
    "RDA 「작물별 비료사용처방」 2010 개정증보판 p.49 「감자(노지재배)」 pH(1:5) 5.5~7.0. "
    "raw/papers/common/rda-fertilizer-prescription-revised-2010.md (A)표. "
    "우리 1차 목표가 노지이므로 이 행이 채점 기준이다(2026-08-04 사용자 결정) — "
    "load_guides()가 같은 지표에 두 재배형이 있으면 open_field를 우선한다. "
    "🔴 상한 7.0은 더뎅이병 구간을 포함한다: 김점순 2012에서 pH 6.49일 때 발병도 61.1%·"
    "상품률 37.0%(무처리 86.3%)로 무너진다. 총수량은 처리 간 유의차가 없어 수량 채점으로는 "
    "드러나지 않는다 — pH가 적정으로 판정돼도 상품률 경고가 별도로 필요하다. "
    "🔵 같은 2010판 행의 P₂O₅·K·Ca·Mg·EC 5칸은 현행 시설 기준값과 완전히 같다 — 감자에서 "
    "재배형이 실제로 가르는 것은 pH와 유기물 둘뿐이다."
    + _HEURISTIC
)
_POTATO_PH_FACILITY_SOURCE = (
    "RDA 「작물별 비료사용처방」 5차 개정본(2022) p83 시설재배토양 진단기준표 pH 5.5~6.2. "
    "knowledge-base/papers/common/rda-fertilizer-prescription-5th-2022.md. "
    "2026-08-04 갱신 — 종전 값 5.0~6.0은 RDA 농업기술길잡이 033 「감자」 교본 p71의 "
    "**재배 지침**이었다. 우리 채점은 실측 토양값을 기준과 대조하는 구조라 **토양검정 판정 "
    "기준**인 처방서 쪽이 용도에 맞다(FinalReport §2-4 ⓐ). "
    "이 행은 시설 기준이라 현재 채점에 쓰이지 않는다 — 향후 시설 재배 확장 시를 위한 것이다."
    + _HEURISTIC
)

# --- 감자 유기물 ------------------------------------------------------------
_POTATO_ORGANIC_NEW = (20.0, 30.0, 15.0, 35.0)
_POTATO_ORGANIC_OLD = (30.0, 47.0, 10.0, 55.5)  # 0019/0027이 넣은 실측범위 기반 편집값
_POTATO_ORGANIC_SOURCE = (
    "RDA 「작물별 비료사용처방」 5차(2022) p83 진단기준표 유기물 20~30 g/kg(Tyurin법). "
    "⭐ 2010 개정증보판 p.49 「감자(노지재배)」도 20~30으로 같다 — **판(2010/2022)과 "
    "재배형(노지/시설)을 가로질러 일치**해 이 지표는 재배형 분기가 필요 없다. "
    "2026-08-04 교체 — 종전 30~47은 문헌 밴드가 아니라 정진철 외 2003(한국환경농학회지 "
    "22(4):261-265)의 **실측범위(10~47)를 그대로 쓰고 하한을 관측 상위절반으로 잡은 편집 "
    "판단**이었다. 원 논문은 유기물과 건물율·칩색도의 단조 양의 상관만 제시하고 적정구간을 "
    "주지 않는다(FinalReport §1-6 ⓐ). "
    "🔴 같은 p83 **각주**는 '비화산회토양과 화산회토양의 유기물 적정함량은 각각 21~50, "
    "101~150 g/kg'이라 표와 어긋난다. 표 값을 채택했다. 제주(화산회토) 별도 분기는 보류 "
    "상태다(FinalReport §2-8) — 5작물 중 감자만 해당하고 달라지는 지표는 유기물뿐이다."
    + _HEURISTIC
)

# --- 사과 치환성 K ----------------------------------------------------------
_APPLE_K_NEW = (0.30, 0.60, 0.15, 0.75)
_APPLE_K_OLD = (0.6, 0.9, 0.45, 1.05)  # 0024가 넣은 교본 표5-21 값
_APPLE_K_SOURCE = (
    "RDA 「작물별 비료사용처방」 5차(2022) p273 사과 치환성 K 0.30~0.60 cmol/kg "
    "(1M NH4OAc 침출). 2026-08-04 교체 — 종전 0.6~0.9(RDA 사과 교본 표5-21/표5-20)는 "
    "**같은 성격의 표 안에서 사과 K 칸만 고립된 이상값**으로 판정됐다. 반증 4건: "
    "① 처방 5차 p273 ② 처방 2010 개정증보판 p.163(사과) ③ 같은 판 p.168(배) "
    "④ 배 교본 표5-25 — 모두 0.30~0.60이다. "
    "⭐ ②③은 OCR 텍스트 레이어와 내장 이미지 육안 판독이라는 **독립 경로 2개**에서 같은 "
    "값이 나와 추출 오류 가능성이 배제됐다(raw/papers/common/"
    "rda-fertilizer-prescription-revised-2010.md (C)표). "
    "⭐ 배 교본이 **같은 제목의 표(「과수원 토양개량 목표」)**에서 처방서와 일치한다는 점이 "
    "'개량목표라 높다'는 설명을 반증한다. 사과·배의 비대칭도 함께 해소된다. "
    "🔴 1차 원출처(농촌진흥청 2006)는 미확보이며 2006판의 존재 여부 자체가 미확인이다 — "
    "0.6~0.9가 오식인지 사과 한정 의도인지는 확정되지 않았다(FinalReport §1-2)."
    + " allowed 0.15~0.75는 pear.json k와 같은 ±50% 규칙이다(FinalReport §1-3 ⓐ). "
    "종전 allowed_min 0.45를 그대로 두면 새 optimal_min 0.30보다 커져 허용구간이 최적구간을 "
    "감싸지 못한다 — 값이 아니라 구조가 깨지므로 함께 옮긴다. allowed_*_kind='heuristic'."
)

# --- 2차 인용 출처 정정 (값 무변경) ------------------------------------------
_POTATO_NIGHT_TEMP_SOURCE = (
    "감자 괴경비대기 야간 고온 28℃. "
    "출처 교체(2026-08-04, FinalReport §1-15 ⓐ) — 종전 표기 'Zhang 2024'는 "
    "potato-heat-tolerance-zhang-2024의 **Discussion 2차 인용[24]**이었다. "
    "국내 1차 자료: RDA 농사로 주요작물 영농순기표 p.34 「덩이줄기 비대 정지 27~30℃」 "
    "(knowledge-base/papers/common/rda-major-crop-farming-calendar.md) — 28이 이 구간 안에 든다. "
    "🔴 **성격이 같다고 단정하지 않는다**: 이 시드는 「야간」 기준인데 농사로 자료는 "
    "주야 구분이 없다. 값이 우연히 겹치는 것일 수 있으므로 allowed_max_kind='unverified'로 둔다. "
    "야간 한정 국내 임계가 확보되면 교체 대상이다."
)
_POTATO_FROST_SOURCE = (
    "감자 잎 냉해 -3℃. "
    "출처 명기(2026-08-04, FinalReport §1-15 ⓑ) — 종전 표기 'Stegner 2019'는 "
    "potato-frost-damage-stegner-2019의 **2차 인용[25]**이며 교체할 국내 1차 자료가 없다. "
    "🔴 **단일 임계로는 판정이 불가능하다**: 원문에 따르면 잎은 결빙 후 10~78분만 견디고 "
    "'2차 결빙은 확률적 사건'이다 — 즉 -3℃라는 온도 하나가 아니라 **지속시간과 확률**이 "
    "피해를 가른다. 값은 하한 경보로 두되 allowed_min_kind='unverified'다. "
    "국내 감자 서리 정량 기준은 교본 312쪽 전수 확인 결과 **없음이 확정**됐다."
)


def upgrade() -> None:
    conn = op.get_bind()

    # 1) 감자 pH — 기존 행(0032가 facility로 표시)을 처방 5차 값으로 갱신.
    omin, omax, amin, amax = _POTATO_PH_FACILITY
    conn.execute(
        sa.text(
            "UPDATE crop_growth_guide "
            "   SET optimal_min = :omin, optimal_max = :omax, allowed_min = :amin, "
            "       allowed_max = :amax, source_ref = :src, "
            "       allowed_min_kind = 'heuristic', allowed_max_kind = 'heuristic' "
            " WHERE crop_id = 4 AND growth_stage IS NULL AND indicator = 'ph' "
            "   AND cultivation_type = 'facility'"
        ),
        {"omin": omin, "omax": omax, "amin": amin, "amax": amax,
         "src": _POTATO_PH_FACILITY_SOURCE},
    )

    # 2) 감자 pH — 노지 행 신설. 채점이 실제로 쓰는 행이다.
    #    risk_width·weight은 같은 지표의 시설 행에서 그대로 가져온다 — 두 재배형이 다른
    #    감쇠폭을 쓰면 같은 지표인데 곡선이 갈린다.
    omin, omax, amin, amax = _POTATO_PH_OPEN_FIELD
    conn.execute(
        sa.text(
            "INSERT INTO crop_growth_guide "
            "  (crop_id, growth_stage, indicator, cultivation_type, optimal_min, optimal_max, "
            "   allowed_min, allowed_max, weight, risk_width, risk_width_source, source_ref, "
            "   confidence, allowed_min_kind, allowed_max_kind, method) "
            "SELECT 4, NULL, 'ph', 'open_field', :omin, :omax, :amin, :amax, "
            "       weight, risk_width, risk_width_source, :src, 'domestic_measured', "
            "       'heuristic', 'heuristic', method "
            "  FROM crop_growth_guide "
            " WHERE crop_id = 4 AND growth_stage IS NULL AND indicator = 'ph' "
            "   AND cultivation_type = 'facility'"
        ),
        {"omin": omin, "omax": omax, "amin": amin, "amax": amax,
         "src": _POTATO_PH_OPEN_FIELD_SOURCE},
    )

    # 3) 감자 유기물 — 처방서 값으로 교체.
    omin, omax, amin, amax = _POTATO_ORGANIC_NEW
    conn.execute(
        sa.text(
            "UPDATE crop_growth_guide "
            "   SET optimal_min = :omin, optimal_max = :omax, allowed_min = :amin, "
            "       allowed_max = :amax, source_ref = :src, "
            "       allowed_min_kind = 'heuristic', allowed_max_kind = 'heuristic' "
            " WHERE crop_id = 4 AND growth_stage IS NULL AND indicator = 'organic'"
        ),
        {"omin": omin, "omax": omax, "amin": amin, "amax": amax,
         "src": _POTATO_ORGANIC_SOURCE},
    )

    # 4) 사과 치환성 K — optimal·allowed를 함께 옮긴다(따로 옮기면 allowed ⊅ optimal).
    omin, omax, amin, amax = _APPLE_K_NEW
    conn.execute(
        sa.text(
            "UPDATE crop_growth_guide "
            "   SET optimal_min = :omin, optimal_max = :omax, allowed_min = :amin, "
            "       allowed_max = :amax, source_ref = :src, "
            "       allowed_min_kind = 'heuristic', allowed_max_kind = 'heuristic' "
            " WHERE crop_id = 1 AND growth_stage IS NULL AND indicator = 'k'"
        ),
        {"omin": omin, "omax": omax, "amin": amin, "amax": amax, "src": _APPLE_K_SOURCE},
    )

    # 5) 2차 인용 출처 정정 — 값은 그대로 둔다.
    conn.execute(
        sa.text(
            "UPDATE crop_growth_guide SET source_ref = :src "
            " WHERE crop_id = 4 AND growth_stage = 'tuber' AND indicator = 'temp_night_min'"
        ),
        {"src": _POTATO_NIGHT_TEMP_SOURCE},
    )
    conn.execute(
        sa.text(
            "UPDATE crop_growth_guide SET source_ref = :src "
            " WHERE crop_id = 4 AND growth_stage = 'early' AND indicator = 'temp_day'"
        ),
        {"src": _POTATO_FROST_SOURCE},
    )


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            "DELETE FROM crop_growth_guide "
            " WHERE crop_id = 4 AND growth_stage IS NULL AND indicator = 'ph' "
            "   AND cultivation_type = 'open_field'"
        )
    )
    for crop_id, indicator, bands in (
        (4, "ph", _POTATO_PH_FACILITY_OLD),
        (4, "organic", _POTATO_ORGANIC_OLD),
        (1, "k", _APPLE_K_OLD),
    ):
        omin, omax, amin, amax = bands
        conn.execute(
            sa.text(
                "UPDATE crop_growth_guide "
                "   SET optimal_min = :omin, optimal_max = :omax, "
                "       allowed_min = :amin, allowed_max = :amax "
                " WHERE crop_id = :crop_id AND growth_stage IS NULL AND indicator = :indicator"
            ),
            {"crop_id": crop_id, "indicator": indicator,
             "omin": omin, "omax": omax, "amin": amin, "amax": amax},
        )
    # source_ref는 0031/0012가 다시 덮어쓰므로 여기서 되돌리지 않는다(그 마이그레이션들의
    # downgrade가 자기 값을 복원한다).
