import type { ReactNode } from "react";

import styles from "./EmptyState.module.css";

/**
 * 빈 상태·준비 중 표시(comUI .nodata 패턴). FrontEnd.md §12-1:
 * 준비 중 기능은 완성된 것처럼 위장하지 않는다 — badge="준비 중"을 명시하고
 * 가짜 데이터·동작하는 척하는 버튼을 넣지 않는다.
 */
export default function EmptyState({
  icon,
  title,
  hint,
  badge,
  action,
}: {
  icon?: ReactNode;
  title: string;
  hint?: string;
  /** "준비 중" 등 상태 라벨 — 색만이 아니라 글자로 상태를 알린다(§10). */
  badge?: string;
  /** 빈 상태에서 다음 행동으로 안내하는 링크·버튼(실제 동작하는 것만). */
  action?: ReactNode;
}) {
  return (
    <div className={styles.wrap}>
      {badge !== undefined && <span className={styles.badge}>{badge}</span>}
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
