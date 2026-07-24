// 챗봇 API 도메인 타입. FE-BE 공유 개념이라 여기 단일 정의(CLAUDE.md §7).
export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  role: ChatRole;
  content: string;
}
