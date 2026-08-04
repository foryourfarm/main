"use client";

import { useEffect, useState } from "react";

/**
 * 펫 더미 계약(FrontEnd.md §11) — 이름·성격·이미지는 아직 확정 자산이 아니라 placeholder다.
 * 실제 자산이 오면 PET_DEFAULTS만 바꾸면 전체 화면에 반영된다(한 파일 수정 계약).
 * 사용자별 커스텀은 localStorage에 저장한다 — 펫 백엔드 API가 없어 서버 저장은 [백엔드 확장 필요].
 */
export type PetConfig = {
  name: string;
  personality: string;
  /** public/ 기준 경로 또는 절대 URL. 임시 placeholder. */
  image: string;
};

export const PET_DEFAULTS: PetConfig = {
  name: "텃밭이",
  personality: "당신의 밭에서 함께 일하는 이웃",
  image: "/assets/chatbot_icon.png",
};

const KEY = "fyf-pet";
const EVENT = "fyf-pet-change";

export function getPet(): PetConfig {
  if (typeof window === "undefined") return PET_DEFAULTS;
  try {
    const raw = localStorage.getItem(KEY);
    if (raw === null) return PET_DEFAULTS;
    return { ...PET_DEFAULTS, ...(JSON.parse(raw) as Partial<PetConfig>) };
  } catch {
    // 깨진 저장값은 기본값으로 — 펫 설정이 화면을 죽이지 않는다.
    return PET_DEFAULTS;
  }
}

export function setPet(patch: Partial<PetConfig>): void {
  const next = { ...getPet(), ...patch };
  localStorage.setItem(KEY, JSON.stringify(next));
  window.dispatchEvent(new Event(EVENT));
}

export function resetPet(): void {
  localStorage.removeItem(KEY);
  window.dispatchEvent(new Event(EVENT));
}

/** 저장값 변경 구독 — 플로팅 버튼(ChatDock)과 관리 화면이 같은 값을 본다. */
export function usePet(): PetConfig {
  // SSR·첫 페인트는 기본값 — 마운트 후 저장값으로 동기화(하이드레이션 불일치 방지).
  const [pet, setState] = useState<PetConfig>(PET_DEFAULTS);

  useEffect(() => {
    const sync = () => setState(getPet());
    sync();
    window.addEventListener(EVENT, sync);
    window.addEventListener("storage", sync); // 다른 탭에서 바꾼 경우
    return () => {
      window.removeEventListener(EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  return pet;
}
