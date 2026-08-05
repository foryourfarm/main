from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class IndicatorBreakdown(BaseModel):
    """지표 하나의 채점 내역. 결측/이상은 status로만 표기(value/score 없음)."""

    value: float | None = None
    score: float | None = None
    weight: float | None = None
    status: str  # optimal | allowed | risk | missing | invalid | invalid_guide
    # 장기예보 보정이 적용된 지표만 채워진다(value = baseline + correction). 근거 제시용.
    baseline: float | None = None
    correction: float | None = None
    # 기준값의 근거와 신뢰도. domestic_measured면 국내 실측, foreign_literature/provisional은
    # 잠정치라 UI가 표현을 약하게 해야 한다(§18-4).
    confidence: str | None = None
    source_ref: str | None = None
    cultivation_type: str | None = None
    """그 지표 밴드 기준표의 출처 — `open_field`(노지) | `facility`(시설), `guide.cultivation_type`
    그대로. 오이·상추는 토양 7개 전부, 감자는 6개가 **시설재배 기준표로 노지 실측을 채점**한다
    (outcomes/README.md 적용 체크리스트 4-1) — 사용자가 노지 밭 점수를 보면서 그 기준이 시설
    기준인지 모르면 안 된다. 채점되지 않은 지표(missing/invalid/invalid_guide/unscored_code)는
    다른 근거 필드(`confidence`/`source_ref`)와 마찬가지로 싣지 않아 `None`이다."""
    boundary_kind: str | None = None
    """점수를 정한 **방향**의 허용경계 성격 — `value < optimal_min`으로 이탈했으면
    `guide.allowed_min_kind`, `value > optimal_max`로 이탈했으면 `guide.allowed_max_kind`.
    한 밴드 안에서 하한·상한의 성격이 다를 수 있어(사과 기온: 하한 `cultivable_range`, 상한
    `heuristic`) 두 컬럼을 합쳐 내면 반드시 한쪽이 거짓 표기가 된다 — **결속한 쪽만** 낸다.
    `status`가 `optimal`(최적구간 안, 방향 없음)·`category`(등급코드 조회, 밴드 자체가 없음)·
    `missing`/`invalid`/`invalid_guide`/`unscored_code`(채점 자체가 없음)면 결속한 방향이
    없으므로 `None`이다."""
    score_tier: Literal["literature", "reference"] | None = None
    """이 점수가 문헌 기반(`literature`)인지 참고용(`reference`)인지. `reference`는
    `status == "risk"`이면서 결속한 방향의 kind가 `"derived"`인 경우뿐이다 — 문헌값이 아니라
    우리가 역산한 경계를 넘어선 구간의 점수라는 뜻이다(outcomes/README.md 적용 체크리스트
    12번). 현재 유일한 대상은 사과 `ca.allowed_max = 6.5`다: 문헌값이 아니라 역산치(염기포화도
    80% × CEC 10.0)이고, **그 상한 밖 감점 기울기는 국내외 근거 0건**인데 전국 치환성 Ca
    중앙값(7.23)이 그 상한 밖이라 다수 밭이 이 근거 없는 기울기로 감점된다. 판정은 `derived`
    kind 여부만 보므로 다른 지표가 향후 `derived`가 되어도 자동으로 이 판정을 따라간다 —
    "사과 ca"를 코드로 특별취급하지 않는다. 그 외 채점된 지표(`optimal`/`allowed`/`risk`
    non-derived/`category`)는 `literature`. 채점되지 않은 항목은 `None`."""


class FarmSuitability(BaseModel):
    """밭 단위 '문헌 기반 예상 적합도'(장기 탭). ML 정확도 검증 완료 아님 — 명칭 고정(§13, 핸드오프 §5).

    status: ok(정상) | dormant(기상 판정 근거 없는 달 — 토양 지침만 걸림, 점수 미노출)
    | out_of_season(해당 단계 지침 없음 — 예: 배 겨울) | insufficient_data(지표 전부 결측/이상).

    P3(2026-08-05): `score`는 국가 적지평가 3단 구조 `min(토양 축, 기후 축)`이다(심교문
    2016, outcomes/README.md §2026-08-04 §2) — 종전 가중평균이 아니다. 토양/기온 각 축의
    실제 값(soil_total/temp_score)은 응답에 내지 않는다 — G11(기후 축 무동작 감시)은
    로그(`app/core/log_config.py`) 쪽에서 집계하고, 프론트가 그 값을 쓰지 않으므로 breakdown과
    중복되는 필드를 새로 늘리지 않는다(YAGNI).
    """

    farm_id: int
    crop_id: int
    region_id: int
    growth_stage: str | None
    as_of: date
    status: Literal["ok", "dormant", "out_of_season", "insufficient_data"]
    score: float | None
    grade: str | None  # S | A | B | C | null
    score_weighted: float | None = None
    """종전 토양60/기온40 가중평균 총점. P3 도입 후 주 총점(`score`)이 min 구조로 바뀌면서
    부차 지표로만 병기한다 — min에는 가중 개념이 없어 주 판정에는 쓰지 않는다."""
    limiting_factor: str | None = None
    """총점을 결속한 축 **안에서** 가장 낮은 지표. 토양 축이 결속했으면 그 지표의 한글명
    (`INDICATOR_NAMES`), 기후 축이 결속했으면 `"기온"`(계약이 그렇게 규정,
    outcomes/README.md §2026-08-04 §2). 두 축 다 비었거나 dormant/미채점이면 `None`."""
    limiting_layer: str | None = None
    """총점을 결속한 축 — `"토양"` | `"기온"`. `limiting_factor`가 어느 층 얘기인지 먼저
    가리켜야 한다 — 그래야 대시보드와 히트맵이 같은 밭·같은 달에 "무엇이 원인인지"를
    같게 말한다."""
    label: str
    breakdown: dict[str, IndicatorBreakdown]
    risk_flags: list[str]
    limitations: list[str]


class MonthlyOutlookEntry(BaseModel):
    """한 달의 전망 한 칸(히트맵 셀). 지표별 breakdown은 응답 비대를 피해 생략 — 상세는 일자 조회로.

    P3(2026-08-05): `score`는 국가 적지평가 3단 구조 `min(토양 축, 기후 축)`이다(심교문
    2016, outcomes/README.md §2026-08-04 §2) — `compute_farm_suitability`와 같은 총점
    축이라 같은 밭·같은 달이면 대시보드와 히트맵이 같은 점수를 보여준다.
    """

    year: int
    """창이 해를 넘기므로(11월 조회 → 11·12·1월) 칸마다 연도를 갖는다. 응답 최상위에 하나로
    두면 걸친 창에서 반드시 한쪽이 틀린다."""
    month: int  # 1~12
    growth_stage: str | None
    status: Literal["ok", "dormant", "out_of_season", "insufficient_data"]
    score: float | None
    grade: str | None
    score_weighted: float | None = None
    """종전 토양60/기온40 가중평균 총점(부차 지표). min 구조인 `score`가 주 총점이다."""
    limiting_factor: str | None = None
    """총점을 결속한 축 안에서 가장 낮은 지표명(토양) 또는 `"기온"`(기후). 결측이면 `None`."""
    limiting_layer: str | None = None
    """총점을 결속한 축 — `"토양"` | `"기온"`."""
    risk_flags: list[str]
    # 그 달 기온·강수에 3개월전망 보정이 반영됐는지. false면 평년치만 쓴 칸이다.
    outlook_applied: bool = False
    outlook_published_at: datetime | None = None
    """이 칸에 쓰인 전망의 발표일. 보정이 없으면 None.

    칸마다 다른 발표분에서 올 수 있어(8/25 기준: 8월은 7/23 발표, 9·10월은 8/23 발표)
    연도와 마찬가지로 칸이 갖는다."""


class FarmMonthlyOutlook(BaseModel):
    """밭의 **다가오는 3개월** 전망(장기 탭 히트맵, `PRD.md` §4.4).

    평년치 기반 이론 추정이며 예보가 아니다 — 한계는 limitations로 함께 내려 UI에 병기한다.

    창 범위는 `months[0]`·`months[-1]`에서 나오므로 별도 필드를 두지 않는다 — 중복 필드는
    실제 값과 어긋날 여지만 만든다.
    """

    farm_id: int
    crop_id: int
    region_id: int
    label: str
    months: list[MonthlyOutlookEntry]
    limitations: list[str]


class LongTermAdvice(BaseModel):
    """장기 탭 추천 문구(PRD §10-2). 히트맵과 **별도 요청**이라 탭 렌더를 막지 않는다.

    위험 판정·수치는 백엔드 룰 엔진이 끝냈고 LLM은 문장만 다듬는다 — 히트맵 점수와 같은
    근거에서 나오므로 둘이 어긋나지 않는다.
    """

    text: str
    """항상 채워진다. LLM이 죽어도 규칙 문구가 나가고, 생육기가 아닌 창에서도 그 사실을
    문장으로 알린다 — 프론트가 "없음" 상태를 따로 처리할 필요가 없다."""

    is_llm: bool
    """false면 규칙 기반 문구 — LLM 실패·미도달이거나, 생육기가 아니라 다듬지 않은 경우다.
    다듬어진 것처럼 보이게 하지 않는다(§18-4)."""
