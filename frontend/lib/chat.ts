import { ensureAccessToken } from "@/lib/auth";
import type { ChatMessage } from "@/types/chat";

// 백엔드 챗봇 SSE 계약: docs/llm-integration.md §11.
// 스트림은 `data: {"token":"..."}\n\n` 프레임 연속 + 종료 `data: [DONE]\n\n`.
// ApiResponse 래퍼를 쓰지 않으므로(§6 스트리밍 예외) EventSource(GET전용) 대신 fetch로 직접 파싱한다.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

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
