"use client";

import type { HourlyTemp, IndicatorBreakdown } from "@/types/farm";

import styles from "./DayTempChart.module.css";

/**
 * 하루 기온 변화 그래프. 카드의 "낮 최고기온"과 점수의 근거인 "일 평균기온"이 왜 다른
 * 숫자인지를 한 화면에서 보여주는 것이 이 컴포넌트의 목적이다.
 *
 * **차트 라이브러리를 쓰지 않고 인라인 SVG로 그린다.** 의존성이 next/react/react-dom 3개뿐인
 * 프로젝트에서 24점짜리 단일 시계열 + 수평 기준선 + 구간 음영을 위해 번들을 늘릴 이득이 없고,
 * 밴드 음영은 범용 라이브러리에서 오히려 커스터마이즈로 싸우게 된다. §8의 "검증된 라이브러리"는
 * 복잡한 시각화를 손으로 만들지 말라는 취지이므로 이 규모에는 해당하지 않는다.
 *
 * 접근성: 곡선만으로는 값을 읽을 수 없어 같은 데이터를 표로 병기한다(§8 — 색·위치만으로
 * 정보를 전달하지 않는다). SVG 자체는 `aria-hidden`으로 빼고 표를 정보원으로 삼는다.
 */

const W = 640;
const H = 200;
const PAD = { top: 16, right: 12, bottom: 26, left: 34 };

type Props = {
  hourly: HourlyTemp[];
  /** 점수의 근거값(일평균). 수평선으로 얹는다. */
  tempAvg: number | null;
  /** 카드 표시값(일최고). 마커로 얹는다. */
  tempMax: number | null;
  tempNightMin: number | null;
  /** `temp_day` 지표의 채점 밴드 — 적정·허용 구간 음영에 쓴다. */
  band?: IndicatorBreakdown | null;
  /** 표본이 하루를 온전히 덮지 못하면 없는 시간대를 비워 보여준다. */
  isPartial: boolean;
};

export default function DayTempChart({
  hourly,
  tempAvg,
  tempMax,
  tempNightMin,
  band,
  isPartial,
}: Props) {
  if (hourly.length === 0) {
    return (
      <p className={styles.empty}>
        이 날짜는 시간별 기온이 저장되지 않았습니다(예보를 다시 받으면 표시됩니다).
      </p>
    );
  }

  const points = hourly
    .map((p) => ({ h: p.h, t: Number(p.t) }))
    .filter((p) => Number.isFinite(p.t));
  if (points.length === 0) {
    return <p className={styles.empty}>시간별 기온을 읽을 수 없습니다.</p>;
  }

  // y축 범위는 **실제 데이터로만** 잡는다(곡선 + 기준선·마커).
  // 밴드 경계까지 넣으면 곡선이 짜부라진다 — 감자 early는 허용 하한이 −3℃라 27~38℃ 곡선이
  // 화면 위쪽 1/3로 밀린다. 밴드는 대신 보이는 범위로 잘라 그리고(bandRect), 정확한 경계값은
  // 모달의 근거표가 숫자로 보여준다.
  const candidates = [
    ...points.map((p) => p.t),
    ...[tempAvg, tempMax, tempNightMin].filter((v): v is number => v !== null),
  ];
  const rawLo = Math.min(...candidates);
  const rawHi = Math.max(...candidates);
  // 위아래 1℃ 여유. 완전히 평평한 하루(lo===hi)에서 0으로 나누지 않게 최소 폭을 준다.
  const lo = Math.floor(rawLo) - 1;
  const hi = Math.max(Math.ceil(rawHi) + 1, lo + 2);

  const x = (h: number) => PAD.left + (h / 23) * (W - PAD.left - PAD.right);
  const y = (t: number) =>
    PAD.top + (1 - (t - lo) / (hi - lo)) * (H - PAD.top - PAD.bottom);

  const line = points.map((p, i) => `${i === 0 ? "M" : "L"}${x(p.h)},${y(p.t)}`).join(" ");

  const bandRect = (from?: number | null, to?: number | null) => {
    if (typeof from !== "number" || typeof to !== "number") return null;
    const top = y(Math.min(to, hi));
    const bottom = y(Math.max(from, lo));
    return { y: top, height: Math.max(bottom - top, 0) };
  };
  const allowed = bandRect(band?.allowed_min, band?.allowed_max);
  const optimal = bandRect(band?.optimal_min, band?.optimal_max);

  const peak = points.reduce((a, b) => (b.t > a.t ? b : a));
  const trough = points.reduce((a, b) => (b.t < a.t ? b : a));
  const ticks = [0, 6, 12, 18, 23].filter((h) => h >= points[0].h && h <= points[points.length - 1].h);

  return (
    <figure className={styles.figure}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className={styles.svg}
        role="presentation"
        aria-hidden="true"
      >
        {/* 채점 밴드 — 허용(연한)과 적정(진한)을 겹쳐 깔아 곡선이 어디를 벗어났는지 보이게 한다 */}
        {allowed && (
          <rect
            x={PAD.left}
            y={allowed.y}
            width={W - PAD.left - PAD.right}
            height={allowed.height}
            className={styles.bandAllowed}
          />
        )}
        {optimal && (
          <rect
            x={PAD.left}
            y={optimal.y}
            width={W - PAD.left - PAD.right}
            height={optimal.height}
            className={styles.bandOptimal}
          />
        )}

        {/* 표본이 없는 시간대 — 첫날이 어디부터 시작하는지 눈에 보이게 한다 */}
        {isPartial && points[0].h > 0 && (
          <rect
            x={PAD.left}
            y={PAD.top}
            width={x(points[0].h) - PAD.left}
            height={H - PAD.top - PAD.bottom}
            className={styles.gap}
          />
        )}
        {isPartial && points[points.length - 1].h < 23 && (
          <rect
            x={x(points[points.length - 1].h)}
            y={PAD.top}
            width={W - PAD.right - x(points[points.length - 1].h)}
            height={H - PAD.top - PAD.bottom}
            className={styles.gap}
          />
        )}

        {/* 점수의 근거인 일평균 — 카드 숫자(일최고)와 다른 값임을 선으로 드러낸다 */}
        {tempAvg !== null && (
          <>
            <line
              x1={PAD.left}
              x2={W - PAD.right}
              y1={y(tempAvg)}
              y2={y(tempAvg)}
              className={styles.avgLine}
            />
            <text x={W - PAD.right} y={y(tempAvg) - 5} className={styles.avgLabel}>
              일평균 {tempAvg}℃ · 점수 기준
            </text>
          </>
        )}

        <path d={line} className={styles.line} />
        {points.map((p) => (
          <circle key={p.h} cx={x(p.h)} cy={y(p.t)} r={2} className={styles.dot} />
        ))}

        <circle cx={x(peak.h)} cy={y(peak.t)} r={4} className={styles.peak} />
        <text x={x(peak.h)} y={y(peak.t) - 8} className={styles.peakLabel}>
          최고 {peak.t}℃
        </text>
        <circle cx={x(trough.h)} cy={y(trough.t)} r={4} className={styles.trough} />
        <text x={x(trough.h)} y={y(trough.t) + 14} className={styles.troughLabel}>
          최저 {trough.t}℃
        </text>

        {/* 축 — 눈금은 최소로. 값은 아래 표가 정확히 준다 */}
        <text x={4} y={y(hi) + 10} className={styles.axis}>
          {hi}℃
        </text>
        <text x={4} y={y(lo)} className={styles.axis}>
          {lo}℃
        </text>
        {ticks.map((h) => (
          <text key={h} x={x(h)} y={H - 8} className={styles.axisX}>
            {h}시
          </text>
        ))}
      </svg>

      <figcaption className={styles.caption}>
        {isPartial
          ? `이 날짜는 ${points[0].h}시~${points[points.length - 1].h}시 예보만 반영됐습니다.`
          : "하루 전체 예보가 반영됐습니다."}
      </figcaption>

      {/* 그래프를 못 보는 경우의 정보원. 접어두되 항상 접근 가능하게 둔다 */}
      <details className={styles.tableWrap}>
        <summary>시간별 기온 값으로 보기</summary>
        <table className={styles.table}>
          <caption className={styles.srOnly}>시각별 예보 기온</caption>
          <thead>
            <tr>
              <th scope="col">시각</th>
              <th scope="col">기온(℃)</th>
            </tr>
          </thead>
          <tbody>
            {points.map((p) => (
              <tr key={p.h}>
                <th scope="row">{p.h}시</th>
                <td>{p.t}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
