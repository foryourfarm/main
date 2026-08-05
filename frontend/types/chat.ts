// 챗봇 API 도메인 타입. FE-BE 공유 개념이라 여기 단일 정의(CLAUDE.md §7).
export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  role: ChatRole;
  content: string;
}

/** 대화 스레드 한 줄. 세션 테이블은 없고 서버가 chat_message를 집계해 만든다. */
export interface ChatSessionSummary {
  session_id: string;
  title: string;
  message_count: number;
  last_at: string;
}

/**
 * 대화 목록의 시각 표기 — "오늘" / "어제" / "8월 2일".
 *
 * 오늘·어제만 상대 표기로 두는 이유: 대화 목록은 "최근 것이 위"라 그 둘만 눈에 띄면
 * 충분하고, 그 이상 상대화하면("3일 전") 오히려 언제인지 세어봐야 한다.
 * 백엔드가 UTC ISO로 주므로 로컬 날짜로 비교한다(자정 근처에서 하루가 어긋나지 않게
 * 시:분을 버리고 날짜만 본다).
 */
export function formatSessionWhen(iso: string, now: Date = new Date()): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const dayStart = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diffDays = Math.round((dayStart(now) - dayStart(d)) / 86_400_000);
  if (diffDays === 0) return "오늘";
  if (diffDays === 1) return "어제";
  return `${d.getMonth() + 1}월 ${d.getDate()}일`;
}
