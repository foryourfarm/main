// 펫·레벨·데일리 퀘스트 도메인 타입(PRD.md §14.5). 계약: docs/quest-pet-api.md.
export interface PetState {
  code: string;
  name: string;
  emoji: string;
  stage_label: string;
}

/** 고를 수 있는 펫(카탈로그는 서버가 준다 — FE가 따로 들지 않는다). */
export interface PetOption {
  code: string;
  name: string;
  emoji: string;
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
  pets: PetOption[];
  quests: QuestState[];
}

/** 퀘스트 코드 — 발화 지점이 화면 곳곳이라 문자열 오타를 타입으로 막는다. */
export const QUEST = {
  viewShort: "view_short",
  viewLong: "view_long",
  askChat: "ask_chat",
} as const;
