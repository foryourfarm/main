"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import GradeBadge, { gradeTone } from "@/components/GradeBadge";
import Limitations from "@/components/Limitations";
import Loading from "@/components/Loading";
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
  const router = useRouter();
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDashboard()
      .then(setData)
      .catch(() => setError("밭 정보를 가져오지 못했어요. 잠시 후 다시 시도해 주세요."));
  }, []);

  // 밭이 없으면 대시보드는 보여줄 것이 없다 — 링크를 누르게 하지 않고 등록 화면으로 바로 보낸다
  // (가입 직후가 이 경우다). `replace`라 뒤로가기가 빈 대시보드로 튕기지 않는다.
  useEffect(() => {
    if (data !== null && data.farms.length === 0) router.replace("/onboarding");
  }, [data, router]);

  if (error !== null) return <p className={styles.error}>{error}</p>;
  if (data === null) return <Loading />;

  if (data.farms.length === 0) {
    // 위 effect가 곧 이동시킨다. 그 사이 "밭이 없습니다"가 번쩍이지 않게 로딩을 유지한다.
    return <Loading />;
  }

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
      <p>
        <Link href="/onboarding" className={styles.backLink}>
          + 밭 추가 등록
        </Link>
      </p>
      {/* 밭마다 한계가 다르다(예: 어떤 밭만 유기물이 채점 안 됨). 하나로 합쳐 보여주면
          그 사실이 어느 밭 얘기인지 사라져 다른 밭에도 적용되는 것처럼 오독된다(§18-4) —
          그래서 밭별로 분리해서 보여준다. */}
      {data.farms.map((card) => (
        <Limitations
          key={card.farm_id}
          label={`${card.crop_name ?? "작물 미지정"} · ${card.region_name ?? "지역 미지정"}`}
          items={card.limitations}
        />
      ))}
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
