"use client";

import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/lib/auth-context";
import {
  chatSessionId,
  deleteChatSession,
  fetchChatHistory,
  fetchChatSessions,
  streamChat,
  switchChatSession,
} from "@/lib/chat";
import { fetchDashboard } from "@/lib/farm";
import type { ChatMessage, ChatSessionSummary } from "@/types/chat";
import type { DashboardCard } from "@/types/farm";

import styles from "./chat.module.css";

const GREETING =
  "농사 관련 질문을 물어보세요. 생육 단계, 토양 관리, 기후 대응 등 궁금한 점을 편하게요!";
const THINKING = "답변을 입력하는 중입니다…";
const ERROR_TEXT = "답변을 가져오지 못했어요. 잠시 후 다시 시도해 주세요.";

function farmLabel(card: DashboardCard) {
  return `${card.crop_name ?? "작물 미지정"} · ${card.region_name ?? "지역 미지정"}`;
}

/**
 * 어느 밭 기준으로 답하는지 고르는 줄. `<select>`를 쓴 이유는 클릭하면 목록이 열리고
 * 키보드·모바일 네이티브 피커가 공짜로 따라오기 때문이다(§8 접근성).
 *
 * **밭이 여러 개일 때 기본값을 두지 않는다.** 백엔드 `load_farm_context`는 farmId가 없고
 * 밭이 2개 이상이면 밭 컨텍스트를 아예 넣지 않는다(엉뚱한 밭의 pH로 답하는 것보다 안 넣는
 * 편이 맞다). 그 판단은 옳지만 **유저에게 아무 표시가 없던 것이 문제였다** — 화면은 똑같은데
 * 답변만 조용히 일반론이 됐다. 여기서 임의로 첫 밭을 골라주면 침묵이 오답으로 바뀔 뿐이라,
 * 고르지 않았음을 드러내고 고르라고 말한다(PRD 철학 4 정직한 한계 표기).
 */
function FarmPicker({
  farms,
  farmId,
  onChange,
}: {
  farms: DashboardCard[];
  farmId: number | undefined;
  onChange: (id: number | undefined) => void;
}) {
  if (farms.length === 0) return null;

  // 밭이 하나면 백엔드가 자동으로 그 밭을 쓴다 — 고를 것이 없으니 무엇을 쓰는지만 알린다.
  if (farms.length === 1) {
    return (
      <p className={styles.farmNote}>🌱 {farmLabel(farms[0])} 기준으로 답해요</p>
    );
  }

  return (
    <div className={styles.farmPicker}>
      <label htmlFor="chat-farm">🌱 어느 밭</label>
      <select
        id="chat-farm"
        className={styles.farmSelect}
        value={farmId ?? ""}
        onChange={(e) => onChange(e.target.value === "" ? undefined : Number(e.target.value))}
      >
        <option value="">밭을 고르면 그 밭 토양 기준으로 답해요</option>
        {farms.map((card) => (
          <option key={card.farm_id} value={card.farm_id}>
            {farmLabel(card)}
          </option>
        ))}
      </select>
    </div>
  );
}

/**
 * 상담 챗봇 본체. `/chat` 페이지와 우하단 도크(`ChatDock`) 양쪽이 이걸 쓴다.
 *
 * `useSearchParams`를 여기서 부르지 않는다 — 그러면 이 컴포넌트를 얹는 모든 페이지가
 * Suspense 경계를 요구하고, 없으면 **프로덕션 빌드가 깨진다**(Next 16
 * `use-search-params.md`: "a static page that calls useSearchParams … must be wrapped in a
 * Suspense boundary, otherwise the build fails"). 그래서 farmId는 prop으로 받고, URL 파싱은
 * `/chat/page.tsx`만 한다.
 */
export default function ChatPanel({
  initialFarmId,
  embedded = false,
}: {
  initialFarmId?: number;
  embedded?: boolean;
}) {
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
  const { user, loading } = useAuth();
  const [farmId, setFarmId] = useState<number | undefined>(initialFarmId);
  const [farms, setFarms] = useState<DashboardCard[]>([]);

  // 밭 목록은 로그인 유저만. `loading` 중에 부르면 세션 복구 전이라 401이 난다.
  useEffect(() => {
    if (loading || user === null) return;
    fetchDashboard()
      .then((d) => setFarms(d.farms))
      .catch(() => setFarms([])); // 목록 실패가 상담을 막지 않는다 — 선택 줄만 안 보인다
  }, [loading, user]);

  // 로그인 유저의 대화는 계정에 붙어 계속 이어진다 — 스레드 키는 localStorage, 내용은 서버 DB.
  // 리로드·다른 페이지·도크/전체화면 전환 어디서 열어도 같은 스레드를 이어간다.
  // localStorage는 서버 렌더 때 없으므로(SSR) 여기가 아니라 effect 안에서 읽는다.
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);

  const refreshSessions = () => {
    fetchChatSessions()
      .then(setSessions)
      .catch(() => {}); // 목록 실패는 조용히 — 지금 대화는 그대로 된다
  };

  useEffect(() => {
    if (loading) return;
    if (user === null) {
      setSessionId(undefined); // 로그아웃 → 게스트 무상태 경로로 되돌린다
      setSessions([]);
      return;
    }
    const sid = chatSessionId(user.id);
    setSessionId(sid);
    refreshSessions();
    fetchChatHistory(sid)
      .then((past) => {
        // 복원이 늦게 도착해도 이미 나눈 대화를 덮지 않는다(빈 화면일 때만 채운다).
        if (past.length === 0) return;
        setMessages((m) => (m.length === 0 ? past : m));
        scrollToEnd(); // 복원된 대화는 맨 아래(=가장 최근)부터 보여야 한다
      })
      .catch(() => {}); // 복원 실패는 빈 대화로 — 상담 자체를 막지 않는다
  }, [loading, user]);

  /** 스레드 전환. 여기서는 화면을 **덮는 게 맞다** — 유저가 명시적으로 다른 대화를 연 것이다. */
  function openSession(sid: string) {
    if (user === null || busy) return;
    switchChatSession(user.id, sid);
    setSessionId(sid);
    setMessages([]);
    fetchChatHistory(sid)
      .then((past) => {
        setMessages(past);
        scrollToEnd();
      })
      .catch(() => setMessages([]));
  }

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
      // 이 턴이 저장되면서 새 스레드가 생겼거나 제목이 정해졌을 수 있다.
      if (sessionId !== undefined) refreshSessions();
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
    <div className={`${styles.page} ${embedded ? styles.embedded : ""}`}>
      <header className={styles.header}>
        <span className={styles.avatar} aria-hidden>
          🧑‍🌾
        </span>
        <div>
          {/* 도크로 얹힐 때는 그 페이지에 이미 h1이 있다 — 문서에 h1을 둘 두지 않는다. */}
          {embedded ? <h2>텃밭이</h2> : <h1>텃밭이</h1>}
          <p>당신의 밭에서 함께 일하는 이웃</p>
        </div>
      </header>

      {sessionId !== undefined && (
        <div className={styles.sessionBar}>
          <label htmlFor="chat-session" className="sr-only" hidden>
            대화 선택
          </label>
          <select
            id="chat-session"
            className={styles.sessionSelect}
            // 아직 저장된 적 없는 새 대화는 목록에 없다 — 그때는 "새 대화"를 고른 상태로 보인다.
            value={sessions.some((s) => s.session_id === sessionId) ? sessionId : ""}
            onChange={(e) => openSession(e.target.value === "" ? crypto.randomUUID() : e.target.value)}
            disabled={busy}
          >
            <option value="">새 대화</option>
            {sessions.map((s) => (
              <option key={s.session_id} value={s.session_id}>
                {s.title || "(제목 없음)"} · {s.message_count}개
              </option>
            ))}
          </select>
          <button
            type="button"
            className={styles.sessionButton}
            onClick={() => openSession(crypto.randomUUID())}
            disabled={busy}
          >
            + 새 대화
          </button>
          <button
            type="button"
            className={styles.sessionButton}
            // 저장된 적 없는 스레드는 지울 게 없다.
            disabled={busy || !sessions.some((s) => s.session_id === sessionId)}
            onClick={() => {
              if (!confirm("이 대화를 지울까요? 되돌릴 수 없습니다.")) return;
              void deleteChatSession(sessionId)
                .then(() => {
                  refreshSessions();
                  openSession(crypto.randomUUID()); // 지운 자리에 남지 않고 새 대화로
                })
                .catch(() => {});
            }}
          >
            삭제
          </button>
        </div>
      )}

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

      {/* 입력창 바로 위 — 밭을 고르는 순간이 곧 질문을 쓰는 순간이라 손이 가는 자리에 둔다. */}
      <FarmPicker farms={farms} farmId={farmId} onChange={setFarmId} />

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
