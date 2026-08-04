"use client";

import { ArrowLeft, MessageCircle } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import LongTermPanel from "@/components/LongTermPanel";
import RequireAuth from "@/components/RequireAuth";
import ShortTermPanel from "@/components/ShortTermPanel";
import styles from "@/components/farm.module.css";
import { fetchFarms } from "@/lib/farm";
import { completeQuest } from "@/lib/quest";
import type { Farm } from "@/types/farm";
import { QUEST } from "@/types/quest";

/** 장기(시즌 커리큘럼·예방) / 단기(당일~3일 대응) 분리 제공 — PRD.md §4.4~4.5. */
const TABS = [
  { key: "short", label: "단기 (오늘~3일)" },
  { key: "long", label: "장기 (앞으로 3개월)" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

/**
 * comUI VIEW 2 .detail-head + 패널. backHref는 전체 페이지에서만 넘긴다 —
 * intercepting modal에서는 모달 닫기(뒤로가기)가 그 역할이라 뒤로가기 알약을 겹치지 않는다.
 */
export function FarmDetail({ farmId, backHref }: { farmId: number; backHref?: string }) {
  // 단기를 먼저 보여준다 — "오늘 뭘 해야 하나"가 매일 접속하는 이유다(FrontEnd.md §8:
  // comUI는 장기가 기본이지만 실제 앱은 단기 기본을 유지한다).
  const [tab, setTab] = useState<TabKey>("short");
  // 헤더의 밭 이름·지역은 등록 정보(/farms)에서 온다. 실패해도 패널은 그대로 뜬다.
  const [farm, setFarm] = useState<Farm | null>(null);

  useEffect(() => {
    fetchFarms()
      .then((farms) => setFarm(farms.find((f) => f.id === farmId) ?? null))
      .catch(() => {});
  }, [farmId]);

  // 데일리 퀘스트 발화 지점(docs/quest-pet-api.md §3): 탭이 보이면 완료 호출.
  // 멱등이라 탭을 오가며 여러 번 불려도 하루 한 번만 적립되고, 실패는 조용히 무시된다.
  useEffect(() => {
    void completeQuest(tab === "short" ? QUEST.viewShort : QUEST.viewLong);
  }, [tab]);

  const title =
    farm === null
      ? "밭 상세"
      : [farm.label, farm.crop_name].filter(Boolean).join(" · ") || "밭 상세";
  const loc =
    farm === null ? "" : [farm.region_name, farm.district_name].filter(Boolean).join(" ");

  return (
    <>
      <div className={styles.detailHead}>
        {backHref !== undefined && (
          <Link href={backHref} className={styles.back}>
            <ArrowLeft size={18} aria-hidden="true" />내 밭
          </Link>
        )}
        <h2 className={styles.headTitle}>
          {title}
          {loc !== "" && <span className={styles.headLoc}>{loc}</span>}
        </h2>
        <div className={styles.seg} role="tablist" aria-label="밭 상세 보기">
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={t.key === tab}
              className={styles.segBtn}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>
      {/* 이 밭을 컨텍스트로 상담 — 챗봇이 작물·지역·경과일을 알고 답한다. */}
      <Link href={`/chat?farmId=${farmId}`} className={styles.chatLink}>
        <MessageCircle size={16} aria-hidden="true" /> 이 밭으로 상담하기
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
    <main className="wrap">
      <RequireAuth>
        {Number.isInteger(farmId) && farmId > 0 ? (
          <FarmDetail farmId={farmId} backHref="/dashboard" />
        ) : (
          <p className={styles.error}>잘못된 밭 주소입니다.</p>
        )}
      </RequireAuth>
    </main>
  );
}
