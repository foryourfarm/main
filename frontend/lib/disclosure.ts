import type { IndicatorBreakdown } from "@/types/farm";

/**
 * 지표 근거 표기 판정(P6, outcomes/README.md 적용 체크리스트 12번). 컴포넌트에 인라인하지
 * 않고 여기 순수 함수로 뽑는다(CLAUDE.md §8) — DayDetailModal의 ScoreRows가 그대로 쓴다.
 */

/** 이 지표 밴드가 시설재배 기준표인지. `true`면 "시설 기준" 꼬리표를 붙인다 — 노지 밭이라도
 * 시설 기준으로 채점되는 지표가 있어(오이·상추 토양 전부, 감자 6개) 표기 없이는 오해한다. */
export function isFacilityIndicator(breakdown: IndicatorBreakdown): boolean {
  return breakdown.cultivation_type === "facility";
}

/** 이 점수가 문헌 근거 없는 참고 점수인지. `true`면 "기준 초과·참고" 강등 표기를 붙이고,
 * 문헌 기반 점수와 같은 자리에 두지 않는다(역산 경계 `derived` 밖 점수라 근거가 없다). */
export function isReferenceTierScore(breakdown: IndicatorBreakdown): boolean {
  return breakdown.score_tier === "reference";
}
