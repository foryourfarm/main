"use client";

import { useRef, useState } from "react";

import { streamChat } from "@/lib/chat";
import type { ChatMessage } from "@/types/chat";

import styles from "./chat.module.css";

const GREETING =
  "농사 관련 질문을 물어보세요. 생육 단계, 토양 관리, 기후 대응 등 궁금한 점을 편하게요!";
const THINKING = "답변을 생각하고 있어요…";
const ERROR_TEXT = "답변을 가져오지 못했어요. 잠시 후 다시 시도해 주세요.";

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

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
      for await (const token of streamChat(question, history)) {
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
        {messages.length === 0 && <div className={`${styles.bubble} ${styles.assistant}`}>{GREETING}</div>}
        {messages.map((m, i) => {
          const isLast = i === messages.length - 1;
          const pending = busy && isLast && m.role === "assistant" && m.content === "";
          return (
            <div
              key={i}
              className={`${styles.bubble} ${m.role === "user" ? styles.user : styles.assistant} ${
                pending ? styles.pending : ""
              }`}
            >
              {pending ? THINKING : m.content}
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
