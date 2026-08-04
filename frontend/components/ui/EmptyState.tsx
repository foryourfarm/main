import type { ReactNode } from "react";

import styles from "./EmptyState.module.css";

/**
 * 빈 상태 표시(comUI .nodata 패턴). 가짜 데이터·동작하는 척하는 버튼을 넣지 않는다.
 *
 * `badge`("준비 중" 라벨) prop이 있었지만 유일한 사용처였던 `/history`를 지우면서 함께 걷어냈다
 * — 쓰는 곳 없는 prop은 다음 사람이 "준비 중 칸을 또 만들어도 된다"고 읽는다.
 */
export default function EmptyState({
  icon,
  title,
  hint,
  action,
}: {
  icon?: ReactNode;
  title: string;
  hint?: string;
  /** 빈 상태에서 다음 행동으로 안내하는 링크·버튼(실제 동작하는 것만). */
  action?: ReactNode;
}) {
  return (
    <div className={styles.wrap}>
      {icon !== undefined && (
        <span className={styles.icon} aria-hidden="true">
          {icon}
        </span>
      )}
      <p className={styles.title}>{title}</p>
      {hint !== undefined && <p className={styles.hint}>{hint}</p>}
      {action}
    </div>
  );
}
