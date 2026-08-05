"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

import ChatPanel from "@/components/ChatPanel";
import RequireAuth from "@/components/RequireAuth";

/**
 * 밭 기준 답변: /farm/[farmId]에서 "이 밭 상담하기"로 들어오면 farmId가 붙는다.
 * 지난 대화 이어가기: 대시보드 "챗봇과 나눈 이야기"에서 오면 session이 붙는다.
 */
function ChatWithParams() {
  const params = useSearchParams();
  const raw = Number(params.get("farmId"));
  const farmId = Number.isInteger(raw) && raw > 0 ? raw : undefined;
  // 빈 문자열(`?session=`)은 세션 지정이 아니다 — undefined로 떨어뜨려 기본 스레드를 쓴다.
  const session = params.get("session")?.trim() || undefined;
  return <ChatPanel initialFarmId={farmId} initialSessionId={session} />;
}

// useSearchParams는 프리렌더 시 Suspense 경계를 요구한다(Next 16 use-search-params 문서).
// 펫·레벨·퀘스트 줄은 ChatPanel 안의 PetQuestBar가 서버 상태로 그린다 — 여기서 따로 얹지 않는다.
//
// `RequireAuth`로 감싼다 — 백엔드 `/api/v1/chat`이 로그인을 요구하므로(PRD §4.1 "비로그인
// 접근 시 로그인으로 리다이렉트") 비로그인은 입력창을 보기 전에 로그인 화면으로 보낸다.
// 종전에는 게스트가 이 화면에서 질문을 다 쓰고 나서야 실패했다.
export default function ChatPage() {
  return (
    <RequireAuth>
      <Suspense>
        <ChatWithParams />
      </Suspense>
    </RequireAuth>
  );
}
