import type { Grade, SuitabilityStatus } from "@/types/farm";
import { GRADE_MEANING, statusLabel } from "@/types/farm";

import styles from "./Gauge.module.css";

const R = 48;
const CIRC = 2 * Math.PI * R; // ≈ 301.6 — comUI stroke-dasharray와 동일

/**
 * comUI 도넛 게이지 — 0~100 점수를 원호로 그린다.
 * value가 null(점수 없음)이면 트랙만 그리고 "—"를 표시한다(가짜 값 금지, §12).
 *
 * **가운데에 무엇을 넣는가**: `grade`를 주면 점수 숫자 대신 **등급**(글자 + 뜻)이 들어간다.
 * 원호 길이가 이미 점수를 그대로 보여주므로 가운데 숫자는 같은 정보를 두 번 말하는 것이고,
 * 초보 귀농인에게 필요한 건 "78"이 아니라 "그래서 괜찮은가"다(PRD 철학 2 눈높이 번역).
 * 점수가 사라지는 게 아니라 자리를 옮긴다 — 밭 상세의 근거표에서 본다.
 *
 * 등급을 **색으로만 구분하지 않는다** — 글자(A)와 뜻(적합)을 항상 함께 렌더한다(§8, PR #111 원칙).
 * `grade`를 넘기지 않은 호출부는 종전대로 점수를 보여준다(기존 동작 무변경).
 */
export default function Gauge({
  value,
  label = "적합도",
  size = 96,
  color = "var(--primary)",
  grade,
  status,
}: {
  value: number | null;
  label?: string;
  size?: number;
  color?: string;
  /** 주면 가운데가 점수 대신 등급이 된다. null이면 `status` 사유를 대신 보여준다. */
  grade?: Grade | null;
  /** grade가 null일 때 사유("제철 아님" 등)를 쓰기 위해 함께 받는다. */
  status?: SuitabilityStatus;
}) {
  const p = value === null ? 0 : Math.min(Math.max(value, 0), 100) / 100;
  // prop을 아예 안 넘긴 호출부와 null을 넘긴 호출부를 구분해야 한다 — 후자는 "등급 없음"이다.
  const showsGrade = grade !== undefined;
  const reason = status === undefined ? "" : statusLabel(status);

  // 화면에서 숫자를 뺀 것이지 정보를 없앤 게 아니다 — 스크린리더에는 점수까지 읽어준다.
  const ariaLabel = !showsGrade
    ? value === null
      ? `${label} 점수 없음`
      : `${label} ${value}점`
    : grade === null
      ? `${label} ${reason || "등급 없음"}`
      : `${label} ${grade}등급 ${GRADE_MEANING[grade]}${value === null ? "" : `, ${value}점`}`;

  return (
    <div
      className={styles.wrap}
      // fontSize는 장식이 아니다 — 안쪽 등급 글자를 em으로 잡아 게이지 크기에 비례시킨다.
      // px로 고정하면 72px 날짜 게이지에서 글자가 원호를 넘는다.
      style={{ width: size, height: size, fontSize: size }}
      role="img"
      aria-label={ariaLabel}
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
      {/* 위 aria-label이 전부 읽어주므로 안쪽 글자는 중복 낭독을 막는다. */}
      <div className={styles.val} aria-hidden="true">
        {!showsGrade ? (
          <>
            <span className={`num ${styles.value}`}>{value ?? "—"}</span>
            <small className={styles.label}>{label}</small>
          </>
        ) : grade === null ? (
          // 등급이 없는 칸(제철 아님·데이터 부족)은 사유만 — 없는 등급을 지어내지 않는다(§18-4).
          <span className={styles.reason}>{reason || "—"}</span>
        ) : (
          <>
            <span className={`num ${styles.gradeLetter}`} style={{ color }}>
              {grade}
            </span>
            <small className={styles.gradeWord} style={{ color }}>
              {GRADE_MEANING[grade]}
            </small>
          </>
        )}
      </div>
    </div>
  );
}
