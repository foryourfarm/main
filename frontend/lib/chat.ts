import { authFetch, ensureAccessToken } from "@/lib/auth";
import type { ChatMessage, ChatSessionSummary } from "@/types/chat";

// 백엔드 챗봇 SSE 계약: docs/llm-integration.md §11.
// 스트림은 `data: {"token":"..."}\n\n` 프레임 연속 + 종료 `data: [DONE]\n\n`.
// ApiResponse 래퍼를 쓰지 않으므로(§6 스트리밍 예외) EventSource(GET전용) 대신 fetch로 직접 파싱한다.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

const sessionKey = (userId: number) => `chat_session:${userId}`;

/**
 * 지금 보고 있는 대화 스레드 키. **localStorage에 남긴다** — 리로드하면 새 uuid를 만들던 탓에
 * 서버에 저장된 대화가 매번 고아가 됐다(저장은 되는데 아무도 다시 못 읽는 상태).
 * 키에 userId를 넣어 계정이 바뀌면 남의 스레드를 이어받지 않게 한다(§11 소유권).
 * access 토큰과 달리 스레드 키는 비밀이 아니다 — 서버가 (user_id, session_id)로 다시 검증한다.
 */
export function chatSessionId(userId: number): string {
  const saved = localStorage.getItem(sessionKey(userId));
  if (saved !== null) return saved;
  return switchChatSession(userId, randomUUID());
}

/** crypto.randomUUID는 보안 컨텍스트(HTTPS·localhost) 전용이라 LAN IP(http)로 열면 없다 —
 * 그 환경에선 getRandomValues 기반 v4로 폴백한다(스레드 키 용도라 충돌 확률만 낮으면 충분). */
function randomUUID(): string {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

/** 보고 있는 스레드 교체(새 대화 = 새 uuid). 서버 호출이 없다 — 첫 답변이 저장되는 순간
 * 그 스레드가 목록에 나타난다. 빈 스레드를 미리 만들지 않는 이유이기도 하다. */
export function switchChatSession(userId: number, sessionId: string): string {
  localStorage.setItem(sessionKey(userId), sessionId);
  return sessionId;
}

export function fetchChatSessions(): Promise<ChatSessionSummary[]> {
  return authFetch<ChatSessionSummary[]>("/api/v1/chat/sessions");
}

/** 스레드 삭제. 지운 메시지 수를 돌려준다(0 = 없거나 내 것이 아님). */
export function deleteChatSession(sessionId: string): Promise<number> {
  return authFetch<number>(`/api/v1/chat/sessions/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
  });
}

/** 저장된 지난 대화(오래된 순). 실패는 호출부에서 빈 대화로 흡수한다 — 조회 실패가 상담을 막지 않는다. */
export function fetchChatHistory(sessionId: string): Promise<ChatMessage[]> {
  return authFetch<ChatMessage[]>(`/api/v1/chat/history?session_id=${encodeURIComponent(sessionId)}`);
}

/**
 * 질문을 보내고 답변 토큰을 순서대로 흘려준다.
 * - 게스트: history를 매 요청 재전송(무상태).
 * - 로그인(`sessionId` 있음): 서버가 히스토리의 진실 → history는 비우고 보낸다. 밭 컨텍스트 주입용
 *   `farmId`도 함께. `sessionId`가 곧 로그인 모드 표시라 이때만 access를 챙긴다(게스트는 refresh 호출 안 함).
 */
export async function* streamChat(
  question: string,
  history: ChatMessage[],
  opts: { cropId?: number; farmId?: number; sessionId?: string; signal?: AbortSignal } = {},
): AsyncGenerator<string> {
  const token = opts.sessionId !== undefined ? await ensureAccessToken() : null;
  const res = await fetch(`${API_BASE}/api/v1/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token !== null ? { Authorization: `Bearer ${token}` } : {}),
    },
    credentials: "include", // refresh 쿠키 동반(§docs/auth-security.md)
    body: JSON.stringify({
      question,
      history: opts.sessionId !== undefined ? [] : history,
      crop_id: opts.cropId ?? null,
      farm_id: opts.farmId ?? null,
      session_id: opts.sessionId ?? null,
    }),
    signal: opts.signal,
  });
  if (!res.ok || !res.body) throw new Error(`chat 요청 실패: ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    // SSE 프레임 경계 = 빈 줄(\n\n). 경계 없는 잔여는 buf에 남겨 다음 청크와 합친다.
    let sep: number;
    while ((sep = buf.indexOf("\n\n")) !== -1) {
      const frame = buf.slice(0, sep);
      buf = buf.slice(sep + 2);
      const data = frame.startsWith("data: ") ? frame.slice(6) : frame;
      if (data === "[DONE]") return;
      try {
        const parsed: unknown = JSON.parse(data);
        // 런타임 경계 방어(§7): token이 문자열일 때만 흘린다. zod까진 불필요(단일 필드).
        if (parsed && typeof (parsed as { token?: unknown }).token === "string") {
          yield (parsed as { token: string }).token;
        }
      } catch {
        // 깨진 프레임 조각은 무시(스트림을 죽이지 않는다).
      }
    }
  }
}
