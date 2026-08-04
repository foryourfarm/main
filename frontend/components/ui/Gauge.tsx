import styles from "./Gauge.module.css";

const R = 48;
const CIRC = 2 * Math.PI * R; // ≈ 301.6 — comUI stroke-dasharray와 동일

/**
 * comUI 도넛 게이지 — 0~100 점수를 원호로 그린다.
 * value가 null(점수 없음)이면 트랙만 그리고 "—"를 표시한다(가짜 값 금지, §12).
 */
export default function Gauge({
  value,
  label = "적합도",
  size = 96,
  color = "var(--primary)",
}: {
  value: number | null;
  label?: string;
  size?: number;
  color?: string;
}) {
  const p = value === null ? 0 : Math.min(Math.max(value, 0), 100) / 100;
  return (
    <div
      className={styles.wrap}
      style={{ width: size, height: size }}
      role="img"
      aria-label={value === null ? `${label} 점수 없음` : `${label} ${value}점`}
    >
      <svg className={styles.svg} viewBox="0 0 120 120" aria-hidden="true">
        <circle className={styles.track} cx="60" cy="60" r={R} fill="none" strokeWidth="13" />
        {value !== null && (
          <circle
            className={styles.fill}
            cx="60"
            cy="60"
            r={R}
            fill="none"
            stroke={color}
            strokeWidth="13"
            strokeLinecap="round"
            strokeDasharray={CIRC}
            strokeDashoffset={CIRC * (1 - p)}
          />
        )}
      </svg>
      <div className={styles.val}>
        <span className={`num ${styles.value}`}>{value ?? "—"}</span>
        <small className={styles.label}>{label}</small>
      </div>
    </div>
  );
}
