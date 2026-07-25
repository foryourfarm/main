import type { Grade, SuitabilityStatus } from "@/types/farm";
import { statusLabel } from "@/types/farm";

import styles from "./farm.module.css";

/** 등급 → 색 클래스. 색만으로 구분하지 않으려고 항상 라벨과 함께 렌더한다(§8). */
export function gradeTone(grade: Grade | null): string {
  if (grade === "S" || grade === "A") return styles.good;
  if (grade === "B") return styles.warn;
  if (grade === "C") return styles.bad;
  return styles.none;
}

const GRADE_MEANING: Record<Grade, string> = {
  S: "매우 적합",
  A: "적합",
  B: "주의",
  C: "부적합",
};

export default function GradeBadge({
  grade,
  status,
}: {
  grade: Grade | null;
  status: SuitabilityStatus;
}) {
  if (grade === null) {
    return <span className={`${styles.badge} ${styles.none}`}>{statusLabel(status)}</span>;
  }
  return (
    <span className={`${styles.badge} ${gradeTone(grade)}`}>
      {grade} {GRADE_MEANING[grade]}
    </span>
  );
}
