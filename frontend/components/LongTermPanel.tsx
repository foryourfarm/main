"use client";

import { useEffect, useState } from "react";

import { gradeTone } from "@/components/GradeBadge";
import Limitations from "@/components/Limitations";
import Loading from "@/components/Loading";
import styles from "@/components/farm.module.css";
import { fetchLongTermAdvice, fetchMonthlyOutlook } from "@/lib/farm";
import type { FarmMonthlyOutlook, LongTermAdvice, MonthlyOutlookEntry } from "@/types/farm";
import { describeRiskFlag, stageLabel, statusLabel } from "@/types/farm";

/** 창이 해를 넘기면 "11월 · 12월 · 1월"이 되어 1월이 앞선 달로 읽힌다. 연도가 바뀌는
 *  칸에만 연도를 붙여 순서를 드러낸다(모든 칸에 붙이면 시끄럽다). */
function cellLabel(entry: MonthlyOutlookEntry, previous: MonthlyOutlookEntry | undefined) {
  return previous !== undefined && previous.year !== entry.year
    ? `${entry.year}년 ${entry.month}월`
    : `${entry.month}월`;
}

function MonthCell({ entry, label }: { entry: MonthlyOutlookEntry; label: string }) {
  const tone = gradeTone(entry.grade);
  return (
    <div className={styles.cell}>
      <div className={styles.cellMonth}>{label}</div>
      <div className={`${styles.cellScore} ${tone}`}>{entry.score ?? "—"}</div>
      <div className={`${styles.cellGrade} ${tone}`}>
        {entry.grade ?? statusLabel(entry.status)}
      </div>
      <div className={styles.cellStage}>{stageLabel(entry.growth_stage, entry.status)}</div>
      {/* 어느 칸이 전망 반영인지 구분해 보여준다 — 나머지는 평년치만 쓴 칸이다. */}
      {entry.outlook_applied && <div className={styles.cellOutlook}>전망 반영</div>}
    </div>
  );
}

/**
 * 앞으로 3개월을 어떻게 대비할지 한 문단(PRD §10-2).
 *
 * 히트맵과 **따로** 부른다. 단기 탭에서 한 응답에 묶었다가 LLM 동기 재시도가 탭 전체를
 * 12초 막은 실측이 있어 같은 방식을 피한다 — 히트맵은 즉시 뜨고 이 카드만 기다린다.
 *
 * 아래 RiskSummary와 역할이 갈린다: 이 카드는 **무엇을 준비하나**, 목록은 **어느 달에 무슨
 * 지표가 걸리나**다. 같은 risk_flags에서 나오지만 목록은 사실 확인용이라 남겨 둔다.
 *
 * is_llm=false를 숨기지 않는다(§18-4).
 */
function AdviceCard({ farmId }: { farmId: number }) {
  const [advice, setAdvice] = useState<LongTermAdvice | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    fetchLongTermAdvice(farmId).then(setAdvice).catch(() => setFailed(true));
  }, [farmId]);

  // 추천 실패가 탭을 망치지 않는다 — 이 블록만 빠지고 히트맵·위험 목록은 그대로 보인다(§18-5).
  if (failed) return null;

  return (
    <section className={styles.adviceCard} aria-label="3개월 대비 안내">
      <p className={styles.adviceTitle}>
        앞으로 3개월, 이렇게 준비하세요
        {advice && !advice.is_llm && <span className={styles.adviceTag}>자동 생성 문구</span>}
      </p>
      {advice === null ? (
        <p className={styles.adviceLoading}>3개월 안내를 준비하고 있어요…</p>
      ) : (
        <p className={styles.adviceText}>{advice.text}</p>
      )}
    </section>
  );
}

/** 주의가 필요한 달만 모아 이유를 사람 말로 풀어준다(선제적 안내 — PRD 철학 3). */
function RiskSummary({ months }: { months: MonthlyOutlookEntry[] }) {
  const risky = months.filter(
    (m) => m.status === "ok" && m.risk_flags.some((f) => f.endsWith(":outside_allowed")),
  );
  if (risky.length === 0) return null;
  return (
    <section className={styles.section}>
      <h2 className={styles.sectionTitle}>주의가 필요한 시기</h2>
      <ul className={styles.riskList}>
        {risky.map((m) => (
          <li key={`${m.year}-${m.month}`}>
            <strong>{m.month}월</strong> ({stageLabel(m.growth_stage, m.status)}) —{" "}
            {m.risk_flags
              .filter((f) => f.endsWith(":outside_allowed"))
              .map(describeRiskFlag)
              .join(", ")}
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function LongTermPanel({ farmId }: { farmId: number }) {
  const [data, setData] = useState<FarmMonthlyOutlook | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMonthlyOutlook(farmId)
      .then(setData)
      .catch(() => setError("월별 전망을 가져오지 못했어요. 잠시 후 다시 시도해 주세요."));
  }, [farmId]);

  if (error !== null) return <p className={styles.error}>{error}</p>;
  if (data === null) return <Loading />;

  const first = data.months[0];
  const last = data.months[data.months.length - 1];
  // 창 범위는 백엔드가 따로 안 내려준다 — months가 순서 배열이라 양 끝에서 나온다.
  const range =
    first === undefined
      ? ""
      : first.year === last.year
        ? `${first.year}년 ${first.month}~${last.month}월`
        : `${first.year}년 ${first.month}월 ~ ${last.year}년 ${last.month}월`;

  return (
    <>
      <p className={styles.sub}>
        {range} · {data.label}
      </p>
      {/* 단기 탭도 `.sub` 아래·데이터 그리드 위에 추천 카드를 둔다 — 두 탭을 같은 리듬으로. */}
      <AdviceCard farmId={farmId} />
      <div className={styles.heatmap}>
        {data.months.map((m, i) => (
          // 창이 해를 넘기면 month만으로는 키가 겹칠 수 있다(12개월 초과 시).
          <MonthCell key={`${m.year}-${m.month}`} entry={m} label={cellLabel(m, data.months[i - 1])} />
        ))}
      </div>
      <RiskSummary months={data.months} />
      <Limitations items={data.limitations} />
    </>
  );
}
