import styles from "./Loading.module.css";

/**
 * 로딩 표시. 텍스트만으로는 "멈췄나?"와 구분이 안 돼 콜드 스타트처럼 몇 초 걸리는
 * 구간에서 체감 대기가 길어진다(2026-08-02 실배포 확인) — 스피너로 진행 중임을 보인다.
 */
export default function Loading({ label = "불러오는 중…" }: { label?: string }) {
  return (
    <p className={styles.wrap} role="status">
      <span className={styles.spinner} aria-hidden="true" />
      {label}
    </p>
  );
}
