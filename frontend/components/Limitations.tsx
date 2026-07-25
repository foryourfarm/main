import styles from "./farm.module.css";

/**
 * 데이터 한계 표기. 접거나 숨기지 않는다 — 평년치·시군평균·이론 추정치를 확정 실측처럼
 * 보이게 하는 것은 금지사항이다(CLAUDE.md §18-4, PRD 철학 4 "정직한 한계 표기").
 */
export default function Limitations({ items }: { items: string[] }) {
  if (items.length === 0) return null;
  return (
    <section className={styles.limits}>
      <p className={styles.limitsTitle}>이 수치를 볼 때 알아두세요</p>
      <ul className={styles.limitsList}>
        {items.map((text) => (
          <li key={text}>{text}</li>
        ))}
      </ul>
    </section>
  );
}
