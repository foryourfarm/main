"""장기 커리큘럼 서술 — 3개월 적합도를 "그래서 지금 뭘 준비하나"로 옮긴다 (PRD §10-2).

**구조는 단기(`advice_service`)와 동형이다.** 규칙 문구가 먼저, LLM은 다듬기:

    summarize_window()  월별 위험 → 값·기준을 담은 정형 요약 (순수)
    rule_advice()       정형 요약 → 규칙 문구                (순수, 품질 하한선)
    polish()            규칙 문구 → LLM이 다듬은 문구         (실패하면 규칙 문구 그대로)

LLM이 죽어도 화면이 빈약해지지 않는다. 프로덕션 LLM은 별도 GPU VM이라 콜드 로드가 67초까지
걸린 실측이 있다(config.llm_timeout_s=90).

**단기와 결정적으로 다른 두 가지**:

1. **어미가 추정형이다.** 단기는 예보를 보고 "벗어납니다", 장기는 최근 5년 관측 평균 +
   3개월전망이라 "벗어날 것으로 보입니다". 이걸 프롬프트 규칙으로만 맡기지 않고 **규칙
   문구 단계에서 못박는다** — 프롬프트 지시만으로는 새는 것이 챗봇 마크다운 건에서 6회
   실측으로 확인됐다(nexttodo.md "프롬프트로 고치려 들지 말 것").
2. **캐시가 밭당 1행이다.** 단기의 `target_date` 같은 자연 키가 없다 — 창이 항상 오늘
   기준이라 지난 창을 다시 보여줄 일이 없다. 낡음 판정은 단기와 **같은 지문**을 쓴다
   (`advice_cache.prompt_fingerprint`).

**기상 위험만 다룬다.** 토양은 월별로 변하지 않아 3개월 어느 칸에서도 같은 말이 나오고,
단기 탭이 이미 같은 내용을 보여준다(`advice_service.soil_advice`).
"""

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.infra.llm_client import LlmClient
from app.models import LongTermRecommendation
from app.prompts.long_term_advice import PROMPT_VERSION, build_prompt
from app.services.advice_cache import prompt_fingerprint
from app.services.advice_text import RISK_SUFFIX, UNITS, bound_phrase, num, subject_josa
from app.services.suitability_service import INDICATOR_NAMES, WEATHER_INDICATORS

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class MonthRisk:
    """한 달의 위험 하나. 단기의 `RiskLine`과 같은 역할이고 축만 날짜 → (연,월)이다."""

    indicator: str
    year: int
    month: int
    value: float
    allowed_min: float | None
    allowed_max: float | None


def summarize_window(months: list[dict[str, Any]]) -> list[MonthRisk]:
    """기상 위험만 골라 값·허용구간과 함께 정형화한다. 순수 함수.

    같은 지표가 여러 달 걸리면 **가장 이른 달 하나만** 남긴다(단기의 `summarize_risks`와
    같은 규칙). 3개월을 다 나열하면 문구만 길어지고, 유저가 알아야 할 것은 "언제부터"다.

    입력은 `compute_monthly_outlook()`이 돌려준 dict의 `months`다 — pydantic 스키마가 아니라
    **dict여야 한다.** `MonthlyOutlookEntry`에는 없는 내부용 `breakdown`이 여기 살아 있고,
    그게 있어야 값과 허용 경계를 문구에 담을 수 있다. 없으면 "9월 위험"까지밖에 못 쓰고
    수치를 LLM이 지어낼 여지가 생긴다.
    """
    first_seen: dict[str, MonthRisk] = {}
    for entry in sorted(months, key=lambda m: (m["year"], m["month"])):
        breakdown = entry.get("breakdown") or {}
        for flag in entry.get("risk_flags", []):
            if not str(flag).endswith(RISK_SUFFIX):
                continue
            indicator = str(flag).split(":")[0]
            if indicator not in WEATHER_INDICATORS or indicator in first_seen:
                continue
            cell = breakdown.get(indicator)
            if cell is None or cell.get("value") is None:
                continue  # 값이 없으면 서술할 근거가 없다 — 지어내지 않는다
            first_seen[indicator] = MonthRisk(
                indicator=indicator,
                year=int(entry["year"]),
                month=int(entry["month"]),
                value=float(cell["value"]),
                allowed_min=cell.get("allowed_min"),
                allowed_max=cell.get("allowed_max"),
            )
    return sorted(first_seen.values(), key=lambda r: (r.year, r.month, r.indicator))


def window_label(months: list[dict[str, Any]]) -> str:
    """"2026년 8~10월" / "2026년 11월 ~ 2027년 1월". 창이 해를 넘기면 양쪽 연도를 적는다.

    프론트 `LongTermPanel`이 화면 상단에 같은 규칙으로 범위를 적는다 — 카드 문구와 헤더가
    다른 표기를 쓰면 같은 창을 두 가지로 부르는 셈이 된다.
    """
    if not months:
        return ""
    first, last = months[0], months[-1]
    if first["year"] == last["year"]:
        return f"{first['year']}년 {first['month']}~{last['month']}월"
    return f"{first['year']}년 {first['month']}월 ~ {last['year']}년 {last['month']}월"


def rule_advice(
    risks: list[MonthRisk],
    months: list[dict[str, Any]],
    stage_label: str | None,
    next_season: tuple[int, int] | None,
) -> str:
    """규칙 기반 문구. **LLM 없이도 이것만으로 완결되어야 한다** — 품질 하한선이다.

    순수 함수. 분기 4개를 전부 테스트로 고정한다 — 위험 유형이 늘었는데 문구가 없으면
    조용히 빈 안내가 나간다.

    **어미가 전부 추정형이다.** "벗어납니다"가 아니라 "벗어날 것으로 보입니다" — 이 값은
    예보가 아니라 이론 추정치라 확정 어미로 쓰면 §18-4를 어긴다(모듈 docstring 참고).
    """
    if not months:
        # 창 자체가 없다. 실제로는 `outlook_window`가 항상 3칸을 주므로 도달하지 않지만,
        # 도달하면 "위험 없음"으로 뭉개지 않는다 — 확보 못 한 정보를 안전하다고 말하는 셈이다.
        return "3개월 전망을 아직 계산하지 못해 안내를 만들 수 없습니다."

    if all(m["growth_stage"] is None for m in months):
        # 창이 통째로 비었다. 여기서는 LLM을 부르지 않는다(호출부에서 처리) — 데이터
        # 근거가 0이라 다듬게 하면 없는 관리 조언을 지어낸다.
        if next_season is None:
            # 파종후경과일(`days_after_planting`) 기준 작물 — 5종 중 **감자뿐**이다
            # (오이·배는 day_of_year라 달력으로 다음 작기가 잡힌다). 파종일에서 경과일을
            # 세는 축이라 미래 달에는 어떤 단계도 걸리지 않아 `next_season_month`가 None을
            # 준다 — 결함이 아니라 다시 심어야 시작한다는 사실 그대로다.
            return (
                "지금은 이 밭의 생육기가 아닙니다. "
                "다시 파종하시면 그때부터 3개월 안내를 시작해 드릴게요."
            )
        return (
            "지금은 이 밭의 생육기가 아닙니다. "
            f"{next_season[0]}년 {next_season[1]}월부터 다시 안내해 드릴게요."
        )

    if not risks:
        tail = f" 현재 생육 단계는 {stage_label}입니다." if stage_label else ""
        return f"{window_label(months)}에는 큰 기상 위험이 예상되지 않습니다.{tail}"

    parts: list[str] = []
    for line in risks:
        unit = UNITS.get(line.indicator, "")
        name = INDICATOR_NAMES.get(line.indicator, line.indicator)
        bound = bound_phrase(line, unit)
        josa = subject_josa(name)
        when = f"{line.month}월"
        if bound is None:
            # 허용 경계가 지침에 없는데 위험 판정이 났다 — 값만 알리고 기준은 말하지 않는다.
            parts.append(
                f"{when} {name}{josa} {num(line.value)}{unit}로 주의가 필요할 것으로 보입니다."
            )
        elif "이상" in bound:
            # 하한을 못 넘긴 경우. "벗어난다"보다 "못 미친다"가 방향을 바로 알려준다.
            parts.append(
                f"{when} {name}{josa} {num(line.value)}{unit}로 {bound}에 "
                "못 미칠 것으로 보입니다."
            )
        else:
            parts.append(
                f"{when} {name}{josa} {num(line.value)}{unit}로 {bound}를 "
                "벗어날 것으로 보입니다."
            )
    return " ".join(parts)


def polish(base_text: str, crop_name: str, llm: LlmClient) -> str | None:
    """LLM이 규칙 문구를 다듬는다. 실패·빈 응답이면 None — 호출부가 규칙 문구를 쓴다(§18-5).

    성공/실패를 반환값으로 구분한다(실패 시 base_text를 돌려주면 호출부가 `is_llm`을
    판정할 수 없다). 사실 검증은 하지 않는다 — 프롬프트가 [기본 문구]를 통째로 주고 표현만
    바꾸게 하는 구조라 수치를 새로 만들 여지를 좁혔다.
    """
    try:
        out = llm.generate(build_prompt(crop_name, base_text)).strip()
    except Exception:
        # 폴백은 유지하되 원인은 남긴다 — 조용히 삼키면 "왜 규칙 문구만 나오는지"를 로그로
        # 알 수 없다(단기에서 같은 이유로 로깅을 넣었다).
        _log.warning("장기 추천 다듬기 실패 — 규칙 문구로 폴백한다", exc_info=True)
        return None
    if not out:
        _log.warning("장기 추천 LLM이 빈 응답을 줬다 — 규칙 문구로 폴백한다")
    return out or None


def _upsert(
    db: Session,
    farm_id: int,
    input_hash: str,
    window_start: tuple[int, int],
    text: str,
    is_llm: bool,
    risk_flags: list[str],
) -> None:
    """uq_long_term(user_farm_id) 기준 멱등 upsert. 밭당 행이 하나다(DB.md §3.16).

    `input_hash`도 함께 갱신한다 — 창이 넘어가면 같은 행을 새 창 내용으로 덮어쓰는 것이
    이 테이블의 설계다(지난 창은 다시 보여줄 일이 없다).
    """
    stmt = insert(LongTermRecommendation).values(
        user_farm_id=farm_id,
        input_hash=input_hash,
        window_start_year=window_start[0],
        window_start_month=window_start[1],
        advice_text=text,
        is_llm=is_llm,
        risk_flags=risk_flags,
    )
    db.execute(
        stmt.on_conflict_do_update(
            constraint="uq_long_term",
            set_={
                "input_hash": stmt.excluded.input_hash,
                "window_start_year": stmt.excluded.window_start_year,
                "window_start_month": stmt.excluded.window_start_month,
                "advice_text": stmt.excluded.advice_text,
                "is_llm": stmt.excluded.is_llm,
                "risk_flags": stmt.excluded.risk_flags,
            },
        )
    )
    db.commit()


def get_or_create(
    db: Session,
    *,
    farm_id: int,
    crop_id: int,
    crop_name: str,
    outlook: dict[str, Any],
    stage_label: str | None,
    llm: LlmClient | None,
) -> tuple[str, bool, bool, str]:
    """(문구, is_llm, 백그라운드 다듬기 필요 여부, 입력 지문).

    지문을 함께 돌려주는 이유: 백그라운드 다듬기가 저장 직전에 **그 사이 창이 넘어가지
    않았는지** 확인해야 한다. 호출부가 다시 계산하게 두면 같은 값을 두 번 만드는 셈이다.

    단기 `advice_service.get_or_create`와 같은 세 갈래이고, 지문도 같은 함수로 만든다.

    1. 지문이 같고 이미 다듬어진 행이 있으면 그대로 — LLM을 다시 부르지 않는다.
    2. 지문은 같은데 규칙 문구만 저장돼 있으면 **짧은 타임아웃으로 동기 재시도**. Cloud Run은
       응답 후 CPU를 스로틀링해 백그라운드가 끝나지 않을 수 있어, 그 경우 `is_llm=false`
       행이 영구히 남는다. 다음 조회가 그걸 메운다.
    3. 지문이 다르거나 행이 없으면 규칙 문구를 **즉시** 저장·반환하고 다듬기는 호출부가
       백그라운드로 돌린다. 첫 조회가 LLM 콜드 로드(최악 67초)를 기다리지 않게 한다.

    `crop_id`는 지문에 쓰지 않는다 — 프롬프트에 들어가는 것은 작물 **이름**이라 그쪽이
    지문 재료다. 시그니처에 남겨둔 것은 호출부가 이미 갖고 있어서가 아니라, 지문 재료가
    무엇인지 헷갈리지 않게 **쓰지 않음을 여기 적어두기 위해서**다.
    """
    months: list[dict[str, Any]] = outlook["months"]

    risks = summarize_window(months)
    base = rule_advice(risks, months, stage_label, outlook.get("next_season"))
    flags = [f"{r.indicator}{RISK_SUFFIX}" for r in risks]
    window_start = (
        (int(months[0]["year"]), int(months[0]["month"])) if months else (0, 0)
    )
    input_hash = prompt_fingerprint(PROMPT_VERSION, crop_name, base)

    cached = (
        db.query(LongTermRecommendation)
        .filter(LongTermRecommendation.user_farm_id == farm_id)
        .first()
    )
    fresh = cached is not None and cached.input_hash == input_hash

    if fresh and cached.is_llm and cached.advice_text:
        return cached.advice_text, True, False, input_hash

    # 창이 통째로 비었으면 다듬지 않는다 — 서술할 데이터가 0이라 LLM이 지어낸다.
    # 문구가 이미 완결돼 있으므로 규칙 문구 그대로 저장하고 끝낸다.
    if all(m["growth_stage"] is None for m in months):
        _upsert(db, farm_id, input_hash, window_start, base, False, flags)
        return base, False, False, input_hash

    if fresh:
        # ② 같은 창인데 규칙 문구만 있던 행 — 지금 짧게 한 번 더 시도한다.
        polished = polish(base, crop_name, llm) if llm is not None else None
        text = polished or base
        _upsert(db, farm_id, input_hash, window_start, text, polished is not None, flags)
        return text, polished is not None, False, input_hash

    # ③ 새 창(또는 첫 조회) — 규칙 문구로 즉시 응답하고 다듬기는 뒤로 넘긴다.
    _upsert(db, farm_id, input_hash, window_start, base, False, flags)
    return base, False, True, input_hash


def polish_in_background(
    farm_id: int, crop_name: str, input_hash: str, base_text: str, llm: LlmClient
) -> None:
    """응답을 보낸 뒤 도는 다듬기. **자체 세션을 연다** — 요청 스코프 세션은 이미 닫혔다.

    실패해도 조용히 끝낸다. 규칙 문구가 이미 저장돼 있어 화면은 정상이고, 다음 조회의
    동기 재시도(get_or_create ②)가 다시 기회를 갖는다.
    """
    from app.db.session import SessionLocal

    polished = polish(base_text, crop_name, llm)
    if polished is None:
        return
    db = SessionLocal()
    try:
        row = (
            db.query(LongTermRecommendation)
            .filter(LongTermRecommendation.user_farm_id == farm_id)
            .first()
        )
        # 그 사이 다른 요청이 이미 다듬었으면 덮지 않는다. **해시도 확인한다** — 백그라운드가
        # 도는 동안 창이 넘어가거나 전망이 갱신되면 이 문구는 이미 다른 창의 것이다.
        if row is not None and not row.is_llm and row.input_hash == input_hash:
            row.advice_text = polished
            row.is_llm = True
            db.commit()
    except Exception:
        # 백그라운드 경로라 유저에게 드러날 길이 없다 — 로그가 유일한 단서다.
        _log.warning("장기 추천 백그라운드 저장 실패", exc_info=True)
        db.rollback()
    finally:
        db.close()
