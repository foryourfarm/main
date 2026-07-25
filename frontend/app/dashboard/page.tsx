"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import GradeBadge, { gradeTone } from "@/components/GradeBadge";
import Limitations from "@/components/Limitations";
import RequireAuth from "@/components/RequireAuth";
import styles from "@/components/farm.module.css";
import { fetchDashboard } from "@/lib/farm";
import type { DashboardCard, DashboardResponse } from "@/types/farm";

function FarmCard({ card }: { card: DashboardCard }) {
  return (
    <Link href={`/farm/${card.farm_id}`} className={styles.cardLink}>
      <article className={styles.card}>
        <div className={styles.cardTop}>
          <div>
            <div className={styles.cropName}>
              {card.crop_type === "orchard" ? "🌳" : "🌾"} {card.crop_name ?? "작물 미지정"}
            </div>
            <div className={styles.regionName}>{card.region_name ?? "지역 미지정"}</div>
          </div>
          <GradeBadge grade={card.grade} status={card.status} />
        </div>
        <div className={styles.scoreRow}>
          <span className={`${styles.score} ${gradeTone(card.grade)}`}>
            {card.score ?? "—"}
          </span>
          {card.score !== null && <span className={styles.scoreUnit}>점</span>}
        </div>
        <div className={styles.stage}>{card.growth_stage_label ?? "—"}</div>
      </article>
    </Link>
  );
}

function DashboardBody() {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDashboard()
      .then(setData)
      .catch(() => setError("밭 정보를 가져오지 못했어요. 잠시 후 다시 시도해 주세요."));
  }, []);

  if (error !== null) return <p className={styles.error}>{error}</p>;
  if (data === null) return <p className={styles.notice}>불러오는 중…</p>;

  if (data.farms.length === 0) {
    // 밭 등록(온보딩) 화면은 POST /api/v1/farms가 없어 아직 없다 — 빈 상태를 정직하게 안내.
    return <p className={styles.notice}>등록된 밭이 없습니다. 밭 등록 기능은 준비 중입니다.</p>;
  }

  // 카드마다 같은 한계 문구가 반복되므로 화면 하단에 한 번만 모아 보여준다.
  const limitations = [...new Set(data.farms.flatMap((f) => f.limitations))];

  return (
    <>
      <p className={styles.sub}>
        {data.as_of} 기준 · {data.farms[0].label}
      </p>
      <div className={styles.cards}>
        {data.farms.map((card) => (
          <FarmCard key={card.farm_id} card={card} />
        ))}
      </div>
      <Limitations items={limitations} />
    </>
  );
}

export default function DashboardPage() {
  return (
    <main className={styles.page}>
      <div className={styles.inner}>
        <h1 className={styles.h1}>내 밭</h1>
        <RequireAuth>
          <DashboardBody />
        </RequireAuth>
      </div>
    </main>
  );
}
