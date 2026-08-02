import styles from "./farm.module.css";

/**
 * 데이터 한계 표기(CLAUDE.md §18-4, PRD 철학 4 "정직한 한계 표기").
 *
 * **접되 숨기지 않는다.** 종전엔 전부 펼쳐뒀는데 장기 탭에서 8건까지 쌓여 화면 절반을
 * 먹었다(실측: 단기 2건, 장기 감자 6건, 장기 사과 8건). §18-4가 금지하는 것은 "근사를
 * 확정 실측값처럼 보이게" 하는 것이므로, **"추정치"라는 경고와 건수는 항상 노출**하고
 * 본문만 접는다 — 그 사실이 안 보이면 그때가 위반이다.
 *
 * <details>를 쓰는 이유: 상태·JS 없이 동작하고 키보드 포커스·스크린리더·페이지 내 검색이
 * 브라우저 기본으로 붙는다(§8 접근성). 열림 상태는 기억하지 않는다(YAGNI).
 */
export default function Limitations({
  items,
  label,
}: {
  items: string[];
  /** 여러 밭을 한 화면에 늘어놓을 때, 이 한계가 어느 밭 얘기인지 밝힌다(대시보드).
   * 밭 하나만 보는 화면(장기/단기 탭)에서는 문맥상 자명해 생략한다. */
  label?: string;
}) {
  if (items.length === 0) return null;
  return (
    <details className={styles.limits}>
      <summary className={styles.limitsTitle}>
        {label ? `${label} — ` : ""}이 수치는 추정치입니다
        <span className={styles.limitsCount}>근거 {items.length}건 보기</span>
      </summary>
      <ul className={styles.limitsList}>
        {items.map((text) => (
          <li key={text}>{text}</li>
        ))}
      </ul>
    </details>
  );
}
