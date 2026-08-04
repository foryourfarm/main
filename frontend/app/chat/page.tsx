"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

import ChatPanel from "@/components/ChatPanel";

/** 밭 기준 답변: /farm/[farmId]에서 "이 밭 상담하기"로 들어오면 farmId가 붙는다. */
function ChatWithFarmParam() {
  const raw = Number(useSearchParams().get("farmId"));
  const farmId = Number.isInteger(raw) && raw > 0 ? raw : undefined;
  return <ChatPanel initialFarmId={farmId} />;
}

// useSearchParams는 프리렌더 시 Suspense 경계를 요구한다(Next 16 use-search-params 문서).
// 펫·레벨·퀘스트 줄은 ChatPanel 안의 PetQuestBar가 서버 상태로 그린다 — 여기서 따로 얹지 않는다.
export default function ChatPage() {
  return (
    <Suspense>
      <ChatWithFarmParam />
    </Suspense>
  );
}
