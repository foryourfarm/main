"use client";

import DayTempChart from "@/components/DayTempChart";
import Modal from "@/components/Modal";
import { gradeTone } from "@/components/GradeBadge";
import styles from "@/components/DayDetailModal.module.css";
import type { ShortTermDay } from "@/types/farm";
import {
  describeRiskFlag,
  formatBaseAt,
  formatDayLabel,
  indicatorName,
  stageLabel,
  statusLabel,
} from "@/types/farm";

/**
 * 날짜 카드 상세. 카드가 좁아 담을 수 없던 두 가지를 여기서 설명한다.
 *
 *  1. **표시값과 채점값이 다르다** — 카드의 "낮 최고기온"(일최고)과 점수를 매긴 "일 평균기온"이
 *     서로 다른 숫자다. 그래프에 곡선·일최고 마커·일평균 기준선을 함께 얹어 눈으로 보게 한다.
 *  2. **첫날은 하루 전체가 아니다** — 발표시각 이후 시간대만 온다. 그래프의 빈 구간과 배지로
 *     드러낸다(§18-4).
 *
 * 점수 근거표는 `breakdown`이 있을 때만 그린다 — 0032 이전 캐시나 구버전 응답에는 없다.
 */

const num = (v: string | null) => (v === null ? "—" : v);

function ScoreRows({ day }: { day: ShortTermDay }) {
  const breakdown = day.breakdown;
  if (!breakdown || Object.keys(breakdown).length === 0) return null;

  const band = (lo?: number | null, hi?: number | null) => {
    if (typeof lo === "number" && typeof hi === "number") return `${lo} ~ ${hi}`;
    if (typeof lo === "number") return `${lo} 이상`;
    if (typeof hi === "number") return `${hi} 이하`;
    return "—";
  };

  return (
    // 접은 것이 기본이다 — 이 표는 "왜 이 점수인지" 따져보려는 사람만 펼치면 된다.
    // 펼친 채로 두면 모달을 열자마자 숫자 표가 먼저 보여, 정작 봐야 할 기온·주의가 아래로 밀린다.
    <details className={styles.fold}>
      <summary>
        점수가 이렇게 나온 이유
        <span className={styles.foldHint}>지표 {Object.keys(breakdown).length}개</span>
      </summary>
      <div className={styles.tableScroll}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">지표</th>
              <th scope="col">값</th>
              <th scope="col">적정</th>
              <th scope="col">허용</th>
              <th scope="col">점수</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(breakdown).map(([key, b]) => (
              <tr key={key}>
                <th scope="row">{indicatorName(key)}</th>
                <td>{b.value ?? "—"}</td>
                <td>{band(b.optimal_min, b.optimal_max)}</td>
                <td>{band(b.allowed_min, b.allowed_max)}</td>
                {/* 점수만 색으로 두지 않고 상태를 글자로 병기한다(§8 색만으로 구분 금지) */}
                <td>
                  {b.score ?? "—"}
                  {b.status ? <span className={styles.statusTag}>{b.status}</span> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

export default function DayDetailModal({
  day,
  baseAt,
  onClose,
}: {
  day: ShortTermDay;
  baseAt: string | null;
  onClose: () => void;
}) {
  const tone = gradeTone(day.grade);
  const risks = day.risk_flags.filter((f) => f.endsWith(":outside_allowed"));
  const label = `${formatDayLabel(day.target_date)} 기온 상세`;

  return (
    <Modal onClose={onClose} label={label}>
      <header className={styles.head}>
        <h3 className={styles.title}>{formatDayLabel(day.target_date)}</h3>
        <span className={`${styles.grade} ${tone}`}>
          {day.grade ?? statusLabel(day.status)}
        </span>
        {day.score !== null && <span className={styles.score}>{day.score}점</span>}
      </header>
      {/* 발표시각을 크게 둔다 — 상세를 열면 기대치가 올라가므로 "예보는 발표마다 바뀐다"를
          먼저 보여줘야 한다(FORECAST_LIMITATION과 같은 취지) */}
      <p className={styles.meta}>
        {stageLabel(day.growth_stage, day.status)} · {formatBaseAt(baseAt)}
        {day.is_imputed && <span className={styles.partialTag}>일부 시간대만 반영</span>}
      </p>

      <DayTempChart
        hourly={day.hourly_temp ?? []}
        tempAvg={day.temp_avg === null ? null : Number(day.temp_avg)}
        isPartial={day.is_imputed}
      />

      <dl className={styles.metrics}>
        <div>
          <dt>낮 최고기온</dt>
          <dd>{num(day.temp_max)}℃</dd>
        </div>
        <div>
          <dt>야간 최저</dt>
          <dd>{num(day.temp_night_min)}℃</dd>
        </div>
        <div>
          <dt>일 평균기온</dt>
          <dd>
            {num(day.temp_avg)}℃<span className={styles.hint}>점수 기준</span>
          </dd>
        </div>
        <div>
          <dt>강수</dt>
          <dd>{num(day.rainfall)}mm</dd>
        </div>
      </dl>

      {risks.length > 0 && (
        <>
          <h4 className={styles.sectionTitle}>주의</h4>
          <ul className={styles.risks}>
            {risks.map((f) => (
              <li key={f}>{describeRiskFlag(f)}</li>
            ))}
          </ul>
        </>
      )}

      <ScoreRows day={day} />
    </Modal>
  );
}
