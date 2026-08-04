"use client";

import { changePet } from "@/lib/quest";
import type { QuestProgress } from "@/types/quest";

import styles from "./chat.module.css";

/**
 * 펫·레벨·오늘 퀘스트 줄(PRD.md §14.5). 챗봇 패널 안에 산다 — 펫이 곧 텃밭이의 외형이라
 * 새 화면을 만들 이유가 없다.
 *
 * `<details>`를 쓴 이유는 **접기/펼치기가 공짜**라서다 — 상태·키보드 조작·스크린리더 처리를
 * 직접 만들지 않는다(§8 접근성). 기본은 접혀 있어 대화 공간을 뺏지 않는다.
 *
 * 상태를 스스로 들지 않고 prop으로 받는다: 질문 전송(ask_chat)으로도 퀘스트가 완료돼
 * 진실이 두 곳에 생기면 안 되기 때문이다. 소유자는 ChatPanel 하나다.
 */
export default function PetQuestBar({
  progress,
  onChange,
}: {
  progress: QuestProgress;
  onChange: (next: QuestProgress) => void;
}) {
  const { level, pet, pets, quests, exp_into_level, exp_per_level } = progress;
  const doneCount = quests.filter((q) => q.is_done).length;
  const ratio = Math.min(100, Math.round((exp_into_level / exp_per_level) * 100));

  return (
    <details className={styles.questBox}>
      <summary className={styles.questSummary}>
        <span aria-hidden>{pet.emoji}</span>
        <span>
          Lv.{level} {pet.name} · {pet.stage_label}
        </span>
        {/* 색만으로 진행도를 알리지 않는다 — 숫자를 함께 적는다(§8). */}
        <span className={styles.questCount}>
          오늘 퀘스트 {doneCount}/{quests.length}
        </span>
      </summary>

      <div className={styles.expBar}>
        <div
          className={styles.expFill}
          style={{ width: `${ratio}%` }}
          role="progressbar"
          aria-valuenow={exp_into_level}
          aria-valuemin={0}
          aria-valuemax={exp_per_level}
          aria-label={`다음 레벨까지 ${exp_per_level - exp_into_level} 경험치`}
        />
      </div>

      <ul className={styles.questList}>
        {quests.map((q) => (
          <li key={q.code} className={q.is_done ? styles.questDone : undefined}>
            <span aria-hidden>{q.is_done ? "✅" : "⬜"}</span>
            <span>{q.label}</span>
            <span className={styles.questExp}>{q.is_done ? "완료" : `+${q.exp}`}</span>
          </li>
        ))}
      </ul>

      <div className={styles.petPick}>
        <span>펫 바꾸기</span>
        {pets.map((p) => (
          <button
            key={p.code}
            type="button"
            className={styles.petButton}
            aria-pressed={pet.code === p.code}
            disabled={pet.code === p.code}
            onClick={() => {
              // 실패해도 화면을 되돌릴 게 없다(낙관적 갱신을 안 했다) — 조용히 무시한다.
              void changePet(p.code)
                .then(onChange)
                .catch(() => {});
            }}
          >
            {p.emoji} {p.name}
          </button>
        ))}
      </div>
    </details>
  );
}
