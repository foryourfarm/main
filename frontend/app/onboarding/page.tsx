"use client";

import { useRouter } from "next/navigation";

import FarmForm from "@/components/FarmForm";
import RequireAuth from "@/components/RequireAuth";
import styles from "@/components/farm.module.css";
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
    <main className={styles.page}>
      <div className={styles.inner}>
        <h1 className={styles.h1}>밭 등록</h1>
        <p className={styles.sub}>
          지역과 작물을 등록하면 그 땅의 토양·기후로 적합도를 계산합니다.
        </p>
        <RequireAuth>
          <OnboardingForm />
        </RequireAuth>
      </div>
    </main>
  );
}
