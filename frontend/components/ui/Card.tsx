import type { ReactNode } from "react";

import styles from "./Card.module.css";

/** comUI 벤토 카드. span은 전역 .bento 그리드에서 차지할 열 수(전역 .sp{n} 클래스). */
export function Card({
  span,
  className = "",
  children,
}: {
  span?: 3 | 4 | 5 | 6 | 7 | 8 | 12;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={`${styles.card} ${span !== undefined ? `sp${span}` : ""} ${className}`}>
      {children}
    </section>
  );
}

/** 카드 머리 — 점 아이콘 + 제목 + 우측 태그(comUI .card-h). */
export function CardHeader({
  icon,
  title,
  tag,
}: {
  icon?: ReactNode;
  title: string;
  tag?: string;
}) {
  return (
    <div className={styles.header}>
      {icon !== undefined && (
        <span className={styles.dotIcon} aria-hidden="true">
          {icon}
        </span>
      )}
      <h3 className={styles.title}>{title}</h3>
      {tag !== undefined && <span className={styles.tag}>{tag}</span>}
    </div>
  );
}

/** 카드 하단 설명 박스(comUI .note) — 한계·출처·주의 문구용. */
export function CardNote({ children }: { children: ReactNode }) {
  return <div className={styles.note}>{children}</div>;
}
