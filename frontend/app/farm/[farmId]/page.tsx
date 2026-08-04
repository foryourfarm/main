"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import LongTermPanel from "@/components/LongTermPanel";
import RequireAuth from "@/components/RequireAuth";
import ShortTermPanel from "@/components/ShortTermPanel";
import styles from "@/components/farm.module.css";
import { completeQuest } from "@/lib/quest";
import { QUEST } from "@/types/quest";

/** 장기(시즌 커리큘럼·예방) / 단기(당일~3일 대응) 분리 제공 — PRD.md §4.4~4.5. */
const TABS = [
  { key: "short", label: "단기 (오늘~며칠)", hint: "실시간 예보 기반 위험 대응" },
  { key: "long", label: "장기 (앞으로 3개월)", hint: "과거 5년 평균·3개월전망 기반 월별 조망" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

export function FarmDetail({ farmId }: { farmId: number }) {
  // 단기를 먼저 보여준다 — "오늘 뭘 해야 하나"가 매일 접속하는 이유다.
  const [tab, setTab] = useState<TabKey>("short");
  const active = TABS.find((t) => t.key === tab) ?? TABS[0];

  // 데일리 퀘스트(PRD §14.5). 첫 렌더의 기본 탭(단기)도 "본 것"이라 onClick이 아니라 여기서 쏜다.
  // 멱등이라 탭을 오갈 때 중복 호출돼도 경험치는 하루 한 번이다.
  useEffect(() => {
    void completeQuest(tab === "short" ? QUEST.viewShort : QUEST.viewLong);
  }, [tab]);

  return (
    <>
      <div className={styles.tabs} role="tablist" aria-label="밭 상세 보기">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={t.key === tab}
            className={`${styles.tab} ${t.key === tab ? styles.tabActive : ""}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <p className={styles.tabHint}>{active.hint}</p>
      {/* 이 밭을 컨텍스트로 상담 — 챗봇이 작물·지역·경과일을 알고 답한다. */}
      <Link href={`/chat?farmId=${farmId}`} className={styles.backLink}>
        💬 이 밭으로 상담하기
      </Link>
      {/* 탭 전환 시 언마운트해 각 패널이 자기 데이터만 조회하게 둔다(불필요한 호출 방지). */}
      {tab === "short" ? (
        <ShortTermPanel farmId={farmId} />
      ) : (
        <LongTermPanel farmId={farmId} />
      )}
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
        <h1 className={styles.h1}>밭 상세</h1>
        <RequireAuth>
          {Number.isInteger(farmId) && farmId > 0 ? (
            <FarmDetail farmId={farmId} />
          ) : (
            <p className={styles.error}>잘못된 밭 주소입니다.</p>
          )}
        </RequireAuth>
      </div>
    </main>
  );
}
