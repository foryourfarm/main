import { CheckSquare, Square } from "lucide-react";
import Image from "next/image";

import { petImage } from "@/lib/pet";
import type { QuestProgress } from "@/types/quest";

import styles from "./chat.module.css";

/**
 * 펫·레벨·오늘 퀘스트 줄(PRD.md §14.5). 챗봇 패널 안에 산다 — 펫이 곧 텃밭이의 외형이라
 * 새 화면을 만들 이유가 없다.
 *
 * `<details>`를 쓴 이유는 **접기/펼치기가 공짜**라서다 — 상태·키보드 조작·스크린리더 처리를
 * 직접 만들지 않는다(§8 접근성). 기본은 접혀 있어 대화 공간을 뺏지 않는다.
 *
 * 캐릭터가 제비 한 마리로 확정돼 **펫 선택 줄이 사라졌다** — 고를 것이 없다. 그래서 이
 * 컴포넌트는 이제 상태를 바꾸지 않고 받은 진행도만 그린다(순수 표시).
 */
export default function PetQuestBar({ progress }: { progress: QuestProgress }) {
  const { level, pet, quests, exp_into_level, exp_per_level } = progress;
  const doneCount = quests.filter((q) => q.is_done).length;
  const ratio = Math.min(100, Math.round((exp_into_level / exp_per_level) * 100));
  const image = petImage(pet.stage_code);

  return (
    <details className={styles.questBox}>
      <summary className={styles.questSummary}>
        <span aria-hidden>
          {/* 단계 일러스트가 없는 코드(서버가 단계를 추가한 경우)는 단계 이름 글자로 떨어진다
              — 이모지는 시안 v2에서 전면 제거했다. */}
          {image !== null ? (
            <Image src={image} alt="" width={30} height={18} className={styles.questPetIcon} />
          ) : (
            pet.stage_label
          )}
        </span>
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
            {/* 이모지 대신 아이콘 — 시안 v2가 이모지를 전면 제거했고, 이모지는 OS·폰트마다
                모양이 달라 "완료"라는 신호가 기기별로 흔들린다. 옆의 "완료"·"+N" 라벨이
                실제 정보원이라 아이콘은 aria-hidden으로 둔다(§8 색·기호만으로 구분 금지). */}
            <span aria-hidden>
              {q.is_done ? <CheckSquare size={16} /> : <Square size={16} />}
            </span>
            <span>{q.label}</span>
            <span className={styles.questExp}>{q.is_done ? "완료" : `+${q.exp}`}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}
