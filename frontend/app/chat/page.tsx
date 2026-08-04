"use client";

import { Settings2 } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import ChatPanel from "@/components/ChatPanel";
import PetManager from "@/components/PetManager";
import { usePet } from "@/lib/pet";

import styles from "./chat-page.module.css";

/** 밭 기준 답변: /farm/[farmId]에서 "이 밭 상담하기"로 들어오면 farmId가 붙는다. */
function ChatWithFarmParam() {
  const raw = Number(useSearchParams().get("farmId"));
  const farmId = Number.isInteger(raw) && raw > 0 ? raw : undefined;
  return <ChatPanel initialFarmId={farmId} />;
}

// useSearchParams는 프리렌더 시 Suspense 경계를 요구한다(Next 16 use-search-params 문서).
export default function ChatPage() {
  const pet = usePet();
  const [managing, setManaging] = useState(false);

  return (
    <>
      {/* 펫 바 — 상담 상대(펫) 표시 + 펫 관리 창 토글. 채팅 로직(ChatPanel)은 건드리지 않는다. */}
      <div className={styles.petBar}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={pet.image} alt="" className={styles.petAvatar} />
        <div className={styles.petWho}>
          <b>{pet.name}</b>
          <small>{pet.personality}</small>
        </div>
        <button
          type="button"
          className={styles.manageBtn}
          onClick={() => setManaging((v) => !v)}
          aria-expanded={managing}
        >
          <Settings2 size={16} aria-hidden="true" /> 펫 관리
        </button>
      </div>
      {managing && (
        <div className={styles.managerWrap}>
          <PetManager />
        </div>
      )}
      <Suspense>
        <ChatWithFarmParam />
      </Suspense>
    </>
  );
}
