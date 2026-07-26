"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { useAuth } from "@/lib/auth-context";
import { streamChat } from "@/lib/chat";
import type { ChatMessage } from "@/types/chat";

import styles from "./chat.module.css";

const GREETING =
  "농사 관련 질문을 물어보세요. 생육 단계, 토양 관리, 기후 대응 등 궁금한 점을 편하게요!";
const THINKING = "답변을 입력하는 중입니다…";
const ERROR_TEXT = "답변을 가져오지 못했어요. 잠시 후 다시 시도해 주세요.";

function ChatView() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  // 답변 말풍선 최소폭 — 지금까지 나온 것 중 가장 넓었던 폭으로만 올라간다(내려가지 않는다).
  // 그래야 짧은 답변 다음에 긴 답변이 와도 "줄었다 늘었다"로 안 보인다.
  const [answerFloor, setAnswerFloor] = useState(0);
  useEffect(() => {
    const els = listRef.current?.querySelectorAll<HTMLElement>("[data-answer-bubble]");
    if (!els) return;
    const widest = Math.max(0, ...[...els].map((el) => el.getBoundingClientRect().width));
    if (widest > answerFloor) setAnswerFloor(widest);
  });
  const { user } = useAuth();
  // 밭 기준 답변: /farm/[farmId]에서 "이 밭 상담하기"로 들어오면 farmId가 붙는다.
  // 없으면 백엔드가 밭이 하나뿐일 때 그 밭을 자동 선택한다(docs/llm-integration.md §10).
  const farmIdParam = Number(useSearchParams().get("farmId"));
  const farmId = Number.isInteger(farmIdParam) && farmIdParam > 0 ? farmIdParam : undefined;

  // 로그인 상태면 스레드 하나당 uuid4 하나 — 서버가 히스토리를 저장/이어간다.
  // 리로드하면 새 스레드로 시작한다(지난 대화를 불러올 조회 API가 없어, 화면과 서버 스레드를 같이 리셋).
  const sessionRef = useRef<string | null>(null);
  const sessionId = user === null ? undefined : (sessionRef.current ??= crypto.randomUUID());

  const scrollToEnd = () => {
    // 렌더 후 맨 아래로(스트리밍 중 새 토큰 따라가기).
    requestAnimationFrame(() => {
      if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
    });
  };

  async function send() {
    const question = input.trim();
    if (!question || busy) return;
    setInput("");
    setBusy(true);

    // 게스트 멀티턴: 지금까지 대화를 history로 재전송(백엔드가 최근 6개만 사용).
    const history = messages;
    setMessages((m) => [...m, { role: "user", content: question }, { role: "assistant", content: "" }]);
    scrollToEnd();

    try {
      for await (const token of streamChat(question, history, { farmId, sessionId })) {
        setMessages((m) => {
          const next = [...m];
          next[next.length - 1] = {
            role: "assistant",
            content: next[next.length - 1].content + token,
          };
          return next;
        });
        scrollToEnd();
      }
    } catch {
      setMessages((m) => {
        const next = [...m];
        // 답변이 하나도 안 온 경우에만 오류 문구로 대체(부분 응답은 보존).
        if (next[next.length - 1].content === "") {
          next[next.length - 1] = { role: "assistant", content: ERROR_TEXT };
        }
        return next;
      });
    } finally {
      setBusy(false);
      scrollToEnd();
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <span className={styles.avatar} aria-hidden>
          🧑‍🌾
        </span>
        <div>
          <h1>텃밭이</h1>
          <p>당신의 밭에서 함께 일하는 이웃</p>
        </div>
      </header>

      <div className={styles.messages} ref={listRef} aria-live="polite" aria-busy={busy}>
        {messages.length === 0 && (
          <div
            className={`${styles.bubble} ${styles.assistant}`}
            data-answer-bubble
            style={answerFloor ? { minWidth: answerFloor } : undefined}
          >
            {GREETING}
          </div>
        )}
        {messages.map((m, i) => {
          const isLast = i === messages.length - 1;
          const pending = busy && isLast && m.role === "assistant" && m.content === "";
          const isAnswer = m.role === "assistant" && !pending;
          // pending도 answerFloor를 받아야 한다 — 안 그러면 직전 답변보다 짧은 "생각 중" 상태로
          // 훅 좁아졌다가 답변이 오면서 다시 넓어져 화면이 줄었다 늘었다 하는 것처럼 보인다.
          const applyFloor = (isAnswer || pending) && answerFloor;
          return (
            <div
              key={i}
              className={`${styles.bubble} ${m.role === "user" ? styles.user : styles.assistant}`}
              data-answer-bubble={isAnswer ? "" : undefined}
              style={applyFloor ? { minWidth: answerFloor } : undefined}
            >
              {pending ? (
                <span className={styles.typing} role="status">
                  {THINKING}
                </span>
              ) : (
                m.content
              )}
            </div>
          );
        })}
      </div>

      <form
        className={styles.form}
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <label htmlFor="chat-input" className="sr-only" hidden>
          질문 입력
        </label>
        <textarea
          id="chat-input"
          className={styles.input}
          rows={1}
          placeholder="질문을 입력하세요 (Enter 전송, Shift+Enter 줄바꿈)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
        />
        <button className={styles.send} type="submit" disabled={busy || input.trim() === ""}>
          전송
        </button>
      </form>
    </div>
  );
}

// useSearchParams는 프리렌더 시 Suspense 경계를 요구한다(Next 16 use-search-params 문서).
export default function ChatPage() {
  return (
    <Suspense>
      <ChatView />
    </Suspense>
  );
}
