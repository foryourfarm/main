import { authFetch } from "@/lib/auth";
import type { QuestProgress } from "@/types/quest";

// 세 호출 모두 같은 QuestProgress를 돌려준다 — 응답으로 상태를 통째로 갈아끼우면 재조회가 없다.
// 계약: docs/quest-pet-api.md.

export function fetchQuestProgress(): Promise<QuestProgress> {
  return authFetch<QuestProgress>("/api/v1/quests/today");
}

/** 퀘스트 완료(멱등). 화면 곳곳(탭 전환·질문 전송)에서 불리므로 실패는 조용히 삼킨다 —
 * 넛지 장치가 본 기능을 막으면 안 된다. 비로그인이면 아무것도 하지 않는다. */
export async function completeQuest(code: string): Promise<QuestProgress | null> {
  try {
    return await authFetch<QuestProgress>(`/api/v1/quests/${code}`, { method: "POST" });
  } catch {
    return null;
  }
}

export function changePet(code: string): Promise<QuestProgress> {
  return authFetch<QuestProgress>("/api/v1/pet", {
    method: "PUT",
    body: JSON.stringify({ code }),
  });
}
