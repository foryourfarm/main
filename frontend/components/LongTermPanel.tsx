"use client";

import { CalendarRange, TriangleAlert } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import Limitations from "@/components/Limitations";
import Loading from "@/components/Loading";
import { Card, CardHeader } from "@/components/ui/Card";
import Gauge from "@/components/ui/Gauge";
import styles from "@/components/farm.module.css";
import { fetchLongTermAdvice, fetchMonthlyOutlook } from "@/lib/farm";
import type { FarmMonthlyOutlook, LongTermAdvice, MonthlyOutlookEntry } from "@/types/farm";
import { GRADE_COLOR, describeRiskFlag, stageLabel } from "@/types/farm";

/** 창이 해를 넘기면 "11월 · 12월 · 1월"이 되어 1월이 앞선 달로 읽힌다. 연도가 바뀌는
 *  칸에만 연도를 붙여 순서를 드러낸다(모든 칸에 붙이면 시끄럽다). */
function cellLabel(entry: MonthlyOutlookEntry, previous: MonthlyOutlookEntry | undefined) {
  return previous !== undefined && previous.year !== entry.year
    ? `${entry.year}년 ${entry.month}월`
    : `${entry.month}월`;
}

function MonthCell({
  entry,
  label,
  best,
}: {
  entry: MonthlyOutlookEntry;
  label: string;
  best: boolean;
}) {
  return (
    <div className={`${styles.mo} ${best ? styles.moBest : ""}`}>
      <div className={styles.moName}>{label}</div>
      {/* 대시보드·단기 탭과 같은 도넛을 쓴다 — 화면마다 등급이 다르게 생기면 그때마다 새로 배운다. */}
      <Gauge
        value={entry.score}
        size={88}
        grade={entry.grade}
        status={entry.status}
        color={entry.grade !== null ? GRADE_COLOR[entry.grade] : "var(--muted)"}
      />
      {/* GradeBadge를 뺐다 — 도넛 안에 이미 등급과 뜻이 있다. 대신 점수를 작게 남긴다:
          달끼리 비교할 때는 등급이 같아도(A vs A) 점수 차가 판단 근거가 된다. */}
      {entry.score !== null && <div className={styles.moScore}>{entry.score}점</div>}
      <div className={styles.moStage}>{stageLabel(entry.growth_stage, entry.status)}</div>
      {/* 색만으로 "가장 좋은 달"을 알리지 않는다 — 테두리 색은 색각 이상에서 안 보인다(§8). */}
      {best && <div className={styles.moBestTag}>가장 좋은 달</div>}
      {/* 어느 칸이 전망 반영인지 구분해 보여준다 — 나머지는 평년치만 쓴 칸이다. */}
      {entry.outlook_applied && <div className={styles.moTag}>전망 반영</div>}
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
    <Card className={styles.sectionCard}>
      <CardHeader
        icon={<TriangleAlert size={16} />}
        title="주의가 필요한 시기"
        tag={`${risky.length}개 구간`}
      />
      {risky.map((m) => (
        <div className={styles.alert} key={`${m.year}-${m.month}`}>
          <span className={styles.moBadge}>
            {m.month}월<small>{stageLabel(m.growth_stage, m.status)}</small>
          </span>
          <div className={styles.why}>
            {m.risk_flags
              .filter((f) => f.endsWith(":outside_allowed"))
              .map((f) => (
                <strong key={f}>{describeRiskFlag(f)}</strong>
              ))
              // eslint 없이 구분자 넣기 — strong 사이 " · "
              .reduce<ReactNode[]>(
                (acc, el, i) => (i === 0 ? [el] : [...acc, " · ", el]),
                [],
              )}
          </div>
        </div>
      ))}
    </Card>
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
  // comUI .mo.best — 창에서 점수가 가장 높은 달에만 색 장식(라벨은 GradeBadge가 병기).
  const best = data.months.reduce<MonthlyOutlookEntry | null>(
    (acc, m) =>
      m.score === null ? acc : acc === null || (acc.score ?? -1) < m.score ? m : acc,
    null,
  );
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
      <Card className={styles.sectionCard}>
        <CardHeader
          icon={<CalendarRange size={16} />}
          title="월별 예상 적합도"
          tag={`${data.months.length}개월`}
        />
        <div className={styles.months}>
          {data.months.map((m, i) => (
            // 창이 해를 넘기면 month만으로는 키가 겹칠 수 있다(12개월 초과 시).
            <MonthCell
              key={`${m.year}-${m.month}`}
              entry={m}
              label={cellLabel(m, data.months[i - 1])}
              best={best !== null && m === best}
            />
          ))}
        </div>
      </Card>
      <RiskSummary months={data.months} />
      <Limitations items={data.limitations} />
    </>
  );
}
