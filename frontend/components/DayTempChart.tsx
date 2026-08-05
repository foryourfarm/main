"use client";

import type { HourlyTemp } from "@/types/farm";

import styles from "./DayTempChart.module.css";

/**
 * 하루 기온을 **1시간 칸**으로 늘어놓고 좌우로 넘겨 보게 한다.
 *
 * **왜 곡선을 걷어냈나**: 종전에는 24개 점을 640px SVG에 욱여넣어, 모양은 보이지만 "몇 시에
 * 몇 도인지"를 읽을 수 없었다. 초보 귀농인이 이 화면에서 실제로 하는 판단은 "언제 나가서
 * 일할까"라 **시각별 값**이 곡선의 모양보다 먼저다. 값은 칸으로 읽고, 하루의 흐름은 칸마다
 * 깔린 막대 높이로 한눈에 본다.
 *
 * **데이터는 이미 1시간 단위다** — 기상청 단기예보 TMP가 시간별로 오고(`forecast_client`가
 * 시각까지 보관한다) 화면에 쓰는 3일은 전부 1시간 간격이다. 첫날만 발표시각 이후부터 온다.
 *
 * 날씨 아이콘·강수확률은 아직 없다. 백엔드가 SKY·PTY·POP을 **시간별로** 저장하지 않아서다
 * (지금은 일 단위 집계만). 없는 값을 그림으로 지어내지 않는다(§18-4).
 *
 * 접근성: 칸은 시각적 표현이라 `aria-hidden`으로 빼고, 같은 데이터를 표로 병기해 그쪽을
 * 정보원으로 삼는다(§8 — 위치·색만으로 정보를 전달하지 않는다).
 */

type Props = {
  hourly: HourlyTemp[];
  /** 점수의 근거값(일평균). 칸 위에 기준선으로 얹는다. */
  tempAvg: number | null;
  /** 표본이 하루를 온전히 덮지 못하면 없는 시간대를 명시한다. */
  isPartial: boolean;
};

/** 막대 최소 높이(%) — 가장 추운 시각도 칸이 비어 보이지 않게 바닥을 준다. */
const MIN_BAR = 12;

export default function DayTempChart({ hourly, tempAvg, isPartial }: Props) {
  const points = hourly
    .map((p) => ({ h: p.h, t: Number(p.t) }))
    .filter((p) => Number.isFinite(p.t));

  if (points.length === 0) {
    return (
      <p className={styles.empty}>
        이 날짜는 시간별 기온이 저장되지 않았습니다(예보를 다시 받으면 표시됩니다).
      </p>
    );
  }

  const temps = points.map((p) => p.t);
  const lo = Math.min(...temps);
  const hi = Math.max(...temps);
  const span = hi - lo || 1; // 하루 내내 같은 기온이면 0으로 나누게 된다
  const peakHour = points.reduce((a, b) => (b.t > a.t ? b : a)).h;

  const first = points[0].h;
  const last = points[points.length - 1].h;

  return (
    <figure className={styles.figure}>
      {/* tabIndex — 마우스가 없으면 키보드로 스크롤해야 한다(§8 키보드 접근). */}
      <div
        className={styles.strip}
        tabIndex={0}
        role="group"
        aria-label="시간별 예보 기온. 좌우로 넘겨 보세요. 정확한 값은 아래 표에 있습니다."
      >
        {points.map((p) => {
          const ratio = (p.t - lo) / span;
          const isPeak = p.h === peakHour;
          return (
            <div
              key={p.h}
              className={`${styles.hour} ${isPeak ? styles.peak : ""}`}
              aria-hidden="true"
            >
              <span className={styles.temp}>{p.t}°</span>
              <span className={styles.barTrack}>
                <span
                  className={styles.bar}
                  style={{ height: `${MIN_BAR + ratio * (100 - MIN_BAR)}%` }}
                />
              </span>
              <span className={styles.time}>{p.h}시</span>
            </div>
          );
        })}
      </div>

      <figcaption className={styles.caption}>
        <b className={styles.peakNote}>{peakHour}시가 가장 덥습니다 ({hi}℃)</b>
        {tempAvg !== null && <> · 점수는 일평균 {tempAvg}℃로 매깁니다</>}
        <br />
        {isPartial
          ? `이 날짜는 ${first}시~${last}시 예보만 반영됐습니다.`
          : "하루 전체 예보가 반영됐습니다."}
      </figcaption>

      {/* 칸을 못 보는 경우의 정보원. 접어두되 항상 접근 가능하게 둔다 */}
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
