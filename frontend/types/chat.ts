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
