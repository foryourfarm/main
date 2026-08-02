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

/** 온보딩 선택지. 계약: docs/long-term-tab-api.md */
export interface Region {
  id: number;
  name: string;
  sido: string;
}

/** bjd_code가 흙토람 토양 조회 키다. 시/군은 기상 단위, 읍면동은 토양 단위(PRD §5). */
export interface District {
  bjd_code: string;
  name: string;
}

export interface Crop {
  id: number;
  name: string;
}

export interface FarmCreateInput {
  region_id: number;
  bjd_code: string;
  crop_id: number;
  planting_date: string; // YYYY-MM-DD
  label?: string;
}

/** 등록된 밭 1건(GET/POST/PATCH /farms 공통 응답). 이름은 설정 화면 표시용. */
export interface Farm {
  id: number;
  region_id: number;
  region_name: string | null;
  /** 읍면동. 0014 이전 등록 밭은 null — 설정에서 다시 고르면 채워진다. */
  bjd_code: string | null;
  district_name: string | null;
  crop_id: number;
  crop_name: string | null;
  planting_date: string;
  label: string | null;
  /** 토양 기준값 출처(조회 단위·표본수). null이면 토양 초기화를 건너뜀. */
  soil_source: string | null;
}

/** 밭 수정 입력. 보낸 필드만 바뀐다(PATCH). 시/군을 바꾸면 bjd_code도 함께 보내야 한다. */
export type FarmUpdateInput = Partial<FarmCreateInput>;

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
  /** 창이 해를 넘기므로(11월 조회 → 11·12·1월) 칸마다 연도를 갖는다. */
  year: number;
  month: number; // 1~12
  growth_stage: string | null;
  status: SuitabilityStatus;
  score: number | null;
  grade: Grade | null;
  risk_flags: string[];
  /** 그 달 기온·강수에 3개월전망 보정이 반영됐는지. false면 평년치만 쓴 칸. */
  outlook_applied: boolean;
  /** 이 칸에 쓰인 전망의 발표일(ISO). 보정이 없으면 null.
   *  칸마다 다른 발표분에서 올 수 있어 응답 최상위가 아니라 칸이 갖는다. */
  outlook_published_at: string | null;
}

/** 단기 탭 하루치. 계약: docs/long-term-tab-api.md + PR #33 */
export interface ShortTermDay {
  target_date: string;
  growth_stage: string | null;
  status: SuitabilityStatus;
  score: number | null;
  grade: Grade | null;
  temp_avg: string | null;
  temp_night_min: string | null;
  rainfall: string | null;
  risk_flags: string[];
}

/** 연속 지속되는 기상 위험. 하루짜리 노이즈와 구분된 선제 경보 대상. */
export interface PersistentRisk {
  flag: string;
  days: number;
  dates: string[];
}

/** 오늘의 행동추천. 위험 판정은 백엔드 룰 엔진이 하고 LLM은 문장만 다듬는다. */
export interface DailyAdvice {
  /** 기상 기반 오늘의 행동. 매일 바뀌므로 LLM이 다듬는다. */
  text: string;
  /** false면 규칙 기반 문구 — LLM 실패·미도달. 다듬어진 것처럼 보이게 하지 않는다.
   * soil_text에는 해당하지 않는다(그쪽은 항상 규칙 문구). */
  is_llm: boolean;
  /** 이 밭이 속한 법정동의 토양 특성. 상시 상태라 별도 문단으로 구분해 보여준다. */
  soil_text: string | null;
}

export interface FarmShortTerm {
  farm_id: number;
  crop_id: number;
  region_id: number;
  as_of: string;
  /** 예보 발표시각(UTC). 화면에는 KST로 변환해 표시해야 한다. */
  base_at: string | null;
  /** true면 조회 실패로 직전 캐시를 쓴 것 — "최신 아님"을 표시해야 한다. */
  is_stale: boolean;
  label: string;
  days: ShortTermDay[];
  persistent_risks: PersistentRisk[];
  limitations: string[];
}

/** 다가오는 3개월 전망. 창 범위는 months[0]·months.at(-1)에서 나온다 —
 *  최상위 year는 걸친 창에서 반드시 한쪽이 틀리므로 두지 않는다. */
export interface FarmMonthlyOutlook {
  farm_id: number;
  crop_id: number;
  region_id: number;
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
  spring: "봄 작기",
  fall: "가을 작기",
};

export function stageLabel(stage: string | null, status: SuitabilityStatus): string {
  if (stage !== null) return STAGE_LABELS[stage] ?? stage;
  if (status === "out_of_season") return "제철 아님";
  if (status === "dormant") return "생육기 아님";
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
  // 강수는 단위별로 지표가 나뉜다(월평년 vs 예보 일누적). 단위를 문구에 드러내
  // "비 안 온 날이 과습 위험"으로 읽히는 혼동을 막는다.
  rainfall_monthly: "월 강수량",
  rainfall_daily: "일 강수량",
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

/** 예보 발표시각(UTC ISO) → "7월 25일 17시 발표". 백엔드가 UTC로 주므로 변환이 필요하다. */
export function formatBaseAt(iso: string | null): string {
  if (iso === null) return "발표시각 미확인";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "발표시각 미확인";
  return `${d.getMonth() + 1}월 ${d.getDate()}일 ${d.getHours()}시 발표`;
}

/** "2026-07-25" → "7/25 (금)". 요일이 있으면 며칠 뒤인지 직관적으로 읽힌다. */
const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

export function formatDayLabel(isoDate: string): string {
  const d = new Date(`${isoDate}T00:00:00`);
  if (Number.isNaN(d.getTime())) return isoDate;
  return `${d.getMonth() + 1}/${d.getDate()} (${WEEKDAYS[d.getDay()]})`;
}
