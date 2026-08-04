// 펫·레벨·데일리 퀘스트 도메인 타입(PRD.md §14.5). 계약: docs/quest-pet-api.md.
export interface PetState {
  /** 레벨 단계 코드(egg·chick·fledgling·swallow). 일러스트 경로가 이 코드로 갈린다 — lib/pet.ts. */
  stage_code: string;
  name: string;
  emoji: string;
  stage_label: string;
}

export interface QuestState {
  code: string;
  label: string;
  exp: number;
  is_done: boolean;
}

export interface QuestProgress {
  level: number;
  exp: number;
  exp_into_level: number;
  exp_per_level: number;
  pet: PetState;
  quests: QuestState[];
}

/** 퀘스트 코드 — 발화 지점이 화면 곳곳이라 문자열 오타를 타입으로 막는다. */
export const QUEST = {
  viewShort: "view_short",
  viewLong: "view_long",
  askChat: "ask_chat",
} as const;
