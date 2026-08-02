"use client";

import { useEffect, useState } from "react";

import { gradeTone } from "@/components/GradeBadge";
import Limitations from "@/components/Limitations";
import Loading from "@/components/Loading";
import styles from "@/components/farm.module.css";
import { fetchShortTerm } from "@/lib/farm";
import type { DailyAdvice, FarmShortTerm, PersistentRisk, ShortTermDay } from "@/types/farm";
import {
  describeRiskFlag,
  formatBaseAt,
  formatDayLabel,
  stageLabel,
  statusLabel,
} from "@/types/farm";

/**
 * 지속 위험 배너. 이 탭의 존재 이유 — A씨는 "봄철 야간저온 3일"을 미리 몰라 활착에 실패했다.
 * 그래서 날짜별 카드보다 위에, 가장 먼저 보이게 둔다(PRD 철학 3 선제적 안내).
 */
function RiskBanner({ risks }: { risks: PersistentRisk[] }) {
  if (risks.length === 0) {
    return (
      <p className={styles.calmBanner}>
        이번 예보 기간에 연속되는 기상 위험은 없습니다.
      </p>
    );
  }
  return (
    <section className={styles.alertBanner}>
      <p className={styles.alertTitle}>미리 대비하세요</p>
      <ul className={styles.alertList}>
        {risks.map((r) => (
          <li key={r.flag}>
            <strong>{describeRiskFlag(r.flag)}</strong> — {r.days}일 연속 예상
            <span className={styles.alertDates}>
              {" "}
              ({r.dates.map(formatDayLabel).join(", ")})
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

/**
 * 오늘의 행동추천. 위험 배너보다 위에 둔다 — 배너는 "무엇이 위험한가"고 이건 "그래서 뭘
 * 하라"라서, 초보자에게는 후자가 먼저 읽혀야 한다(PRD 철학 2 눈높이 번역).
 *
 * is_llm=false를 숨기지 않는다(§18-4). 규칙 문구도 내용은 정확하지만 "다듬어진 것"처럼
 * 보이게 하면 품질 기대가 어긋난다.
 */
function AdviceCard({ advice }: { advice: DailyAdvice }) {
  return (
    <section className={styles.adviceCard} aria-label="오늘의 행동추천">
      <p className={styles.adviceTitle}>
        오늘 이렇게 하세요
        {!advice.is_llm && <span className={styles.adviceTag}>자동 생성 문구</span>}
      </p>
      <p className={styles.adviceText}>{advice.text}</p>
    </section>
  );
}

function DayCard({ day }: { day: ShortTermDay }) {
  const tone = gradeTone(day.grade);
  // 결측(missing)은 위험이 아니라 데이터 없음이므로 카드에 경고로 띄우지 않는다.
  const risks = day.risk_flags.filter((f) => f.endsWith(":outside_allowed"));
  return (
    <div className={styles.dayCard}>
      <div className={styles.dayHead}>
        <span className={styles.dayDate}>{formatDayLabel(day.target_date)}</span>
        <span className={`${styles.cellGrade} ${tone}`}>
          {day.grade ?? statusLabel(day.status)}
        </span>
      </div>
      <div className={`${styles.cellScore} ${tone}`}>{day.score ?? "—"}</div>
      <div className={styles.dayStage}>{stageLabel(day.growth_stage, day.status)}</div>
      <dl className={styles.metrics}>
        <div>
          <dt>낮 기온</dt>
          <dd>{day.temp_avg ?? "—"}℃</dd>
        </div>
        <div>
          <dt>야간 최저</dt>
          <dd>{day.temp_night_min ?? "—"}℃</dd>
        </div>
        <div>
          <dt>강수</dt>
          <dd>{day.rainfall ?? "—"}mm</dd>
        </div>
      </dl>
      {risks.length > 0 && (
        <ul className={styles.dayRisks}>
          {risks.map((f) => (
            <li key={f}>{describeRiskFlag(f)}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function ShortTermPanel({ farmId }: { farmId: number }) {
  const [data, setData] = useState<FarmShortTerm | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchShortTerm(farmId)
      .then(setData)
      .catch(() => setError("예보를 가져오지 못했어요. 잠시 후 다시 시도해 주세요."));
  }, [farmId]);

  if (error !== null) return <p className={styles.error}>{error}</p>;
  if (data === null) return <Loading />;

  if (data.days.length === 0) {
    // 격자 매핑·예보 조회가 안 된 경우. 조용히 0점 내지 않는다는 백엔드 방침과 맞춘다.
    return <p className={styles.notice}>이 지역의 예보를 아직 가져오지 못했습니다.</p>;
  }

  return (
    <>
      <p className={styles.sub}>
        {formatBaseAt(data.base_at)} · {data.label}
        {data.is_stale && <span className={styles.staleTag}>최신 아님</span>}
      </p>
      {data.advice && <AdviceCard advice={data.advice} />}
      <RiskBanner risks={data.persistent_risks} />
      <div className={styles.dayGrid}>
        {data.days.map((d) => (
          <DayCard key={d.target_date} day={d} />
        ))}
      </div>
      <Limitations items={data.limitations} />
    </>
  );
}
