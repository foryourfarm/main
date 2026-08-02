"""단기 행동추천 — 위험신호를 "오늘 뭘 하면 되는지"로 옮긴다 (PRD §10-1, 필수·메인).

**구조: 규칙 문구가 먼저, LLM은 다듬기.**

    summarize_risks()  위험신호 → 값·기준을 담은 정형 요약 (순수)
    rule_advice()      정형 요약 → 규칙 문구                  (순수, 품질 하한선)
    polish()           규칙 문구 → LLM이 다듬은 문구           (실패하면 규칙 문구 그대로)

LLM이 죽어도 화면 내용이 빈약해지지 않는다. 프로덕션 LLM은 별도 GPU VM이라 콜드 로드가
67초까지 걸린 실측이 있어(config.llm_timeout_s=90) 이 방어가 이론이 아니다.

**기상 위험만 다룬다.** 토양은 며칠 안에 변하지 않아 매일 같은 말이 반복되고, "오늘 이렇게
하라"와 성격이 다르다. `persistent_risks`가 같은 이유로 이미 기상만 거른다.

**캐시**: `daily_recommendation`의 `uq_daily(user_farm_id, target_date)` 멱등 upsert.
생성 시점은 DB.md §3.14의 온디맨드 경로만 쓴다 — 사전생성 스케줄러는 아직 없다.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.infra.llm_client import LlmClient
from app.models import DailyRecommendation
from app.prompts.daily_advice import build_prompt
from app.services.suitability_service import INDICATOR_NAMES, WEATHER_INDICATORS

# 지표 단위. 표기용이라 농업 기준값이 아니다(기준값은 crop_growth_guide, §18-2).
UNITS: dict[str, str] = {
    "temp_day": "℃",
    "temp_night_min": "℃",
    "rainfall_daily": "mm",
    "rainfall_monthly": "mm",
    "sunlight": "시간",
}

RISK_SUFFIX = ":outside_allowed"


@dataclass(frozen=True)
class RiskLine:
    """위험 하나를 사람 말로 옮기는 데 필요한 최소 정보. 판정은 이미 끝났고 서술만 남았다."""

    indicator: str
    target_date: date
    value: float
    allowed_min: float | None
    allowed_max: float | None
    streak_days: int  # 1이면 그날 하루, 2 이상이면 연속


def summarize_risks(
    days: list[dict[str, Any]], persistent: list[dict[str, Any]]
) -> list[RiskLine]:
    """기상 위험만 골라 값·허용구간과 함께 정형화한다. 순수 함수 — 규칙을 테스트로 고정한다.

    같은 지표가 여러 날 걸리면 **가장 이른 날 하나만** 남긴다. 사흘치를 모두 나열하면
    문구가 길어지기만 하고, 유저가 알아야 할 것은 "언제부터 며칠간"이다.
    """
    streak_by_flag = {str(p["flag"]): int(p["days"]) for p in persistent}

    first_seen: dict[str, RiskLine] = {}
    for day in sorted(days, key=lambda d: d["target_date"]):
        breakdown = day.get("breakdown") or {}
        for flag in day.get("risk_flags", []):
            if not str(flag).endswith(RISK_SUFFIX):
                continue
            indicator = str(flag).split(":")[0]
            if indicator not in WEATHER_INDICATORS or indicator in first_seen:
                continue
            entry = breakdown.get(indicator)
            if entry is None or entry.get("value") is None:
                continue  # 값이 없으면 서술할 근거가 없다 — 지어내지 않는다
            first_seen[indicator] = RiskLine(
                indicator=indicator,
                target_date=day["target_date"],
                value=float(entry["value"]),
                allowed_min=entry.get("allowed_min"),
                allowed_max=entry.get("allowed_max"),
                streak_days=streak_by_flag.get(str(flag), 1),
            )
    return sorted(first_seen.values(), key=lambda r: (r.target_date, r.indicator))


def _num(value: float) -> str:
    """소수점 꼬리 정리. 3.0 -> "3", 3.20 -> "3.2"."""
    text = f"{value:.1f}"
    return text[:-2] if text.endswith(".0") else text


def _subject_josa(word: str) -> str:
    """주격 조사 — 받침 있으면 "이", 없으면 "가".

    "이(가)"로 뭉개지 않는 이유: 규칙 문구는 LLM 실패 시 **그대로 유저에게 나가는** 최종
    문구다. 지표 한글명이 시드가 아니라 코드 상수(INDICATOR_NAMES)라 받침이 고정이므로
    한글 음절 계산으로 정확히 고를 수 있다.
    """
    last = word[-1]
    if "가" <= last <= "힣":
        return "이" if (ord(last) - 0xAC00) % 28 else "가"
    return "이"  # 숫자·영문으로 끝나면 판정 불가 — 덜 어색한 쪽으로 고정


def _bound_phrase(line: RiskLine, unit: str) -> str | None:
    """어느 쪽 경계를 벗어났는지. 지침에 그 경계가 없으면 None(범위를 지어내지 않는다)."""
    if line.allowed_min is not None and line.value < line.allowed_min:
        return f"허용 범위({_num(line.allowed_min)}{unit} 이상)"
    if line.allowed_max is not None and line.value > line.allowed_max:
        return f"허용 범위({_num(line.allowed_max)}{unit} 이하)"
    return None


def rule_advice(risks: list[RiskLine], stage_label: str | None, horizon_days: int) -> str:
    """규칙 기반 문구. **LLM 없이도 이것만으로 완결되어야 한다** — 품질 하한선이다.

    순수 함수. 위험 유형이 늘었는데 문구가 없으면 조용히 빈 안내가 나가므로 테스트로 막는다.
    """
    if horizon_days == 0:
        # 예보를 못 받은 상태. 위험이 없는 것과 구분해야 한다 — "위험 없음"이라고 하면
        # 확보하지 못한 정보를 안전하다고 말하는 셈이다(§18-4).
        return "예보를 아직 확보하지 못해 오늘의 행동 안내를 만들 수 없습니다."
    if not risks:
        tail = f" 현재 생육 단계는 {stage_label}입니다." if stage_label else ""
        return f"앞으로 {horizon_days}일간 기상 위험 신호가 없습니다.{tail}"

    parts: list[str] = []
    for line in risks:
        unit = UNITS.get(line.indicator, "")
        name = INDICATOR_NAMES.get(line.indicator, line.indicator)
        when = f"{line.target_date.month}월 {line.target_date.day}일"
        bound = _bound_phrase(line, unit)
        josa = _subject_josa(name)
        if bound is None:
            # 허용 경계가 지침에 없는데 위험 판정이 났다 — 값만 알리고 기준은 말하지 않는다.
            parts.append(f"{when} {name}{josa} {_num(line.value)}{unit}로 주의가 필요합니다.")
        else:
            parts.append(
                f"{when} {name}{josa} {_num(line.value)}{unit}로 {bound}를 벗어납니다."
            )
        if line.streak_days >= 2:
            parts.append(f"{line.streak_days}일 연속입니다.")
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
        return None
    return out or None


def _upsert(
    db: Session,
    farm_id: int,
    target_date: date,
    text: str,
    is_llm: bool,
    risk_flags: list[str],
) -> None:
    """uq_daily 기준 멱등 upsert. 같은 날 몇 번 불려도 행이 하나다(DB.md §3.14).

    `risk_flags`를 함께 남긴다 — "이 문구가 왜 나왔나"를 나중에 되짚을 수 있어야 한다.
    """
    stmt = insert(DailyRecommendation).values(
        user_farm_id=farm_id,
        target_date=target_date,
        advice_text=text,
        is_llm=is_llm,
        risk_flags=risk_flags,
    )
    db.execute(
        stmt.on_conflict_do_update(
            constraint="uq_daily",
            set_={
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
    crop_name: str,
    days: list[dict[str, Any]],
    persistent: list[dict[str, Any]],
    stage_label: str | None,
    today: date,
    llm: LlmClient | None,
) -> tuple[str, bool, bool]:
    """(문구, is_llm, 백그라운드 다듬기 필요 여부).

    세 갈래다:

    1. 다듬어진 캐시가 있으면 그대로 — LLM을 다시 부르지 않는다.
    2. 규칙 문구만 저장된 캐시가 있으면 **짧은 타임아웃으로 동기 재시도**. Cloud Run은 응답
       후 CPU를 스로틀링해 백그라운드 작업이 끝나지 않을 수 있어(기본 설정), 그 경우
       `is_llm=false` 행이 영구히 남는다. 다음 조회가 그걸 메운다.
    3. 캐시가 없으면 규칙 문구를 **즉시** 저장·반환하고 다듬기는 호출부가 백그라운드로 돌린다.
       그날 첫 조회가 LLM 콜드 로드(최악 67초)를 기다리지 않게 한다.
    """
    cached = (
        db.query(DailyRecommendation)
        .filter(
            DailyRecommendation.user_farm_id == farm_id,
            DailyRecommendation.target_date == today,
        )
        .first()
    )
    if cached is not None and cached.is_llm and cached.advice_text:
        return cached.advice_text, True, False

    risks = summarize_risks(days, persistent)
    base = rule_advice(risks, stage_label, len(days))
    flags = [f"{r.indicator}{RISK_SUFFIX}" for r in risks]

    if cached is not None:
        # ② 규칙 문구만 있던 행 — 지금 짧게 한 번 더 시도한다.
        polished = polish(base, crop_name, llm) if llm is not None else None
        text = polished or base
        _upsert(db, farm_id, today, text, polished is not None, flags)
        return text, polished is not None, False

    # ③ 첫 조회 — 규칙 문구로 즉시 응답하고 다듬기는 뒤로 넘긴다.
    _upsert(db, farm_id, today, base, False, flags)
    return base, False, True


def polish_in_background(
    farm_id: int, crop_name: str, target_date: date, base_text: str, llm: LlmClient
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
            db.query(DailyRecommendation)
            .filter(
                DailyRecommendation.user_farm_id == farm_id,
                DailyRecommendation.target_date == target_date,
            )
            .first()
        )
        # 그 사이 다른 요청이 이미 다듬었으면 덮지 않는다.
        if row is not None and not row.is_llm:
            row.advice_text = polished
            row.is_llm = True
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
