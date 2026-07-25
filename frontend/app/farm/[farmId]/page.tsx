"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { gradeTone } from "@/components/GradeBadge";
import Limitations from "@/components/Limitations";
import RequireAuth from "@/components/RequireAuth";
import styles from "@/components/farm.module.css";
import { fetchMonthlyOutlook } from "@/lib/farm";
import type { FarmMonthlyOutlook, MonthlyOutlookEntry } from "@/types/farm";
import { describeRiskFlag, stageLabel, statusLabel } from "@/types/farm";

function MonthCell({ entry }: { entry: MonthlyOutlookEntry }) {
  const tone = gradeTone(entry.grade);
  return (
    <div className={styles.cell}>
      <div className={styles.cellMonth}>{entry.month}월</div>
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
          <li key={m.month}>
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

function OutlookBody({ farmId }: { farmId: number }) {
  const [data, setData] = useState<FarmMonthlyOutlook | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMonthlyOutlook(farmId)
      .then(setData)
      .catch(() => setError("월별 전망을 가져오지 못했어요. 잠시 후 다시 시도해 주세요."));
  }, [farmId]);

  if (error !== null) return <p className={styles.error}>{error}</p>;
  if (data === null) return <p className={styles.notice}>불러오는 중…</p>;

  return (
    <>
      <p className={styles.sub}>
        {data.year}년 · {data.label}
      </p>
      <div className={styles.heatmap}>
        {data.months.map((m) => (
          <MonthCell key={m.month} entry={m} />
        ))}
      </div>
      <RiskSummary months={data.months} />
      <Limitations items={data.limitations} />
    </>
  );
}

export default function FarmDetailPage() {
  const params = useParams<{ farmId: string }>();
  const farmId = Number(params.farmId);

  return (
    <main className={styles.page}>
      <div className={styles.inner}>
        <Link href="/dashboard" className={styles.backLink}>
          ← 내 밭
        </Link>
        <h1 className={styles.h1}>월별 전망</h1>
        <RequireAuth>
          {Number.isInteger(farmId) && farmId > 0 ? (
            <OutlookBody farmId={farmId} />
          ) : (
            <p className={styles.error}>잘못된 밭 주소입니다.</p>
          )}
        </RequireAuth>
      </div>
    </main>
  );
}
