// 장기 탭 도메인 타입. 계약: docs/long-term-tab-api.md (백엔드 스키마와 1:1).

/**
 * 적합도 산출 상태.
 * - dormant: 기상 판정 근거가 없는 달(토양 지침만 걸림). 점수·등급이 null로 온다 —
 *   토양만 보고 나온 100점을 "이 달이 최적"으로 오해하지 않게 하려는 처리(§18-4).
 * - out_of_season: 해당 단계 지침 자체가 없음(예: 배 겨울).
 */
export type SuitabilityStatus = "ok" | "dormant" | "out_of_season" | "insufficient_data";

/** S/A/B/C. 색만으로 구분하지 않고 항상 라벨을 병기한다(CLAUDE.md §8 접근성). */
export type Grade = "S" | "A" | "B" | "C";

export interface DashboardCard {
  farm_id: number;
  crop_id: number;
  crop_name: string | null;
  region_name: string | null;
  crop_type: "orchard" | "field";
  growth_stage: string | null;
  growth_stage_label: string | null;
  score: number | null;
  grade: Grade | null;
  status: SuitabilityStatus;
  label: string;
  limitations: string[];
}

export interface DashboardResponse {
  as_of: string;
  farms: DashboardCard[];
}

export interface MonthlyOutlookEntry {
  month: number; // 1~12
  growth_stage: string | null;
  status: SuitabilityStatus;
  score: number | null;
  grade: Grade | null;
  risk_flags: string[];
  /** 그 달 기온·강수에 3개월전망 보정이 반영됐는지. false면 평년치만 쓴 칸. */
  outlook_applied: boolean;
}

export interface FarmMonthlyOutlook {
  farm_id: number;
  crop_id: number;
  region_id: number;
  year: number;
  label: string;
  months: MonthlyOutlookEntry[];
  limitations: string[];
}

/** 생육단계 코드 → 한글 라벨. 백엔드 dashboard_service.STAGE_LABELS와 동일하게 유지. */
export const STAGE_LABELS: Record<string, string> = {
  fruit_growth: "결실비대기",
  coloring: "착색기",
  maturity: "성숙기",
  growing: "생육기",
  early: "초기 생육",
  tuber: "괴경비대기",
};

export function stageLabel(stage: string | null, status: SuitabilityStatus): string {
  if (stage !== null) return STAGE_LABELS[stage] ?? stage;
  if (status === "out_of_season") return "제철 아님";
  if (status === "dormant") return "휴면기";
  return "전기간";
}

/** 등급 없는 칸의 사유를 사용자 문구로. */
export function statusLabel(status: SuitabilityStatus): string {
  if (status === "out_of_season") return "제철 아님";
  if (status === "dormant") return "생육기 아님";
  if (status === "insufficient_data") return "데이터 부족";
  return "";
}

/** risk_flags("지표:사유") → 사람이 읽는 문구. 전문 용어를 눈높이로 바꾼다(§4.4 요구). */
const INDICATOR_NAMES: Record<string, string> = {
  temp_day: "낮 기온",
  temp_night_min: "야간 최저기온",
  rainfall: "강수량",
  sunlight: "일조",
  ph: "토양 산도(pH)",
  ec: "토양 염류(EC)",
  p2o5: "유효인산",
  organic: "유기물",
};

const REASON_NAMES: Record<string, string> = {
  outside_allowed: "권장 범위를 크게 벗어남",
  missing: "데이터 없음",
  invalid: "값이 이상함",
  invalid_guide: "기준 정보 미비",
};

export function describeRiskFlag(flag: string): string {
  const [indicator, reason] = flag.split(":");
  const name = INDICATOR_NAMES[indicator] ?? indicator;
  const why = REASON_NAMES[reason] ?? reason;
  return `${name} — ${why}`;
}
