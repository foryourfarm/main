"use client";

import { useRouter } from "next/navigation";

import FarmForm from "@/components/FarmForm";
import RequireAuth from "@/components/RequireAuth";
import styles from "@/components/auth.module.css";
import { createFarm } from "@/lib/farm";

function OnboardingForm() {
  const router = useRouter();
  return (
    <FarmForm
      submitLabel="밭 등록하기"
      onSubmit={async (input) => {
        await createFarm(input);
        router.push("/dashboard");
      }}
    />
  );
}

export default function OnboardingPage() {
  return (
    // layout.tsx의 <main className="appMain">이 이미 main 랜드마크 — 중첩 main 금지.
    <div className={styles.wrap}>
      <section className={`${styles.card} ${styles.cardWide}`}>
        <h1 className={styles.title}>밭 등록</h1>
        <p className={styles.lead}>
          지역과 작물을 등록하면 그 땅의 토양·기후로 적합도를 계산합니다.
        </p>
        <RequireAuth>
          <OnboardingForm />
        </RequireAuth>
      </section>
    </div>
  );
}
