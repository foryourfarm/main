"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import RequireAuth from "@/components/RequireAuth";
import styles from "@/components/auth.module.css";
import { useAuth } from "@/lib/auth-context";

/** 저장 후 갈 곳. 온보딩 흐름(카카오 신규)이 기본이고, 설정에서 들어오면 `?next=/settings`. */
const DEFAULT_NEXT = "/onboarding";
// 열린 리다이렉트를 만들지 않는다 — 외부 URL이나 `//evil.com`을 next로 넣어도 못 나가게
// **우리 앱 안의 절대경로만** 허용한다(§17 신뢰 경계).
const isInternalPath = (path: string) => path.startsWith("/") && !path.startsWith("//");

/**
 * 이름(닉네임) 정하는 화면.
 *
 * **카카오로 처음 로그인한 사람이 여기로 자동 이동한다.** 카카오는 닉네임 동의항목을 요청하지
 * 않으면 이름을 주지 않아 계정이 "카카오 사용자"로 시작하는데, 그게 헤더에 그대로 노출된다.
 * 동의항목을 늘리는 대신(카카오 계정에만 해당하는 반쪽 해결) 직접 정하게 한다 — 이메일 가입자도
 * 가입 후에는 이름을 바꿀 수 없었으므로 같은 화면이 양쪽을 해결한다.
 */
function NicknameForm() {
  const params = useSearchParams();
  const router = useRouter();
  const { user, updateNickname } = useAuth();
  // 기존 이름을 미리 채우지 않는다 — 카카오 신규는 "카카오 사용자"가 들어와 지우고 써야 한다.
  const [nickname, setNickname] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const nextParam = params.get("next");
  const next = nextParam !== null && isInternalPath(nextParam) ? nextParam : DEFAULT_NEXT;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await updateNickname(nickname.trim());
      router.replace(next);
    } catch {
      setError("이름을 저장하지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className={styles.form} onSubmit={onSubmit}>
      <h1>어떻게 불러드릴까요?</h1>
      <p className={styles.alt}>
        앱에서 보일 이름입니다. 나중에 설정에서 바꿀 수 있어요.
      </p>
      <div className={styles.field}>
        <label htmlFor="nickname">이름</label>
        <input
          id="nickname"
          type="text"
          autoComplete="nickname"
          required
          maxLength={50}
          placeholder={user?.nickname ?? "예: 초보농부"}
          value={nickname}
          onChange={(e) => setNickname(e.target.value)}
        />
      </div>
      {error && <p className={styles.error}>{error}</p>}
      <button className={styles.submit} type="submit" disabled={busy || nickname.trim() === ""}>
        {busy ? "저장 중…" : "저장하고 계속하기"}
      </button>
      {/* 막다른 화면으로 만들지 않는다 — 지금 정하지 않아도 앱을 쓸 수 있어야 한다. */}
      <button
        type="button"
        className={styles.skip}
        onClick={() => router.replace(next)}
        disabled={busy}
      >
        나중에 하기
      </button>
    </form>
  );
}

export default function NicknamePage() {
  return (
    <main className={styles.wrap}>
      {/* useSearchParams는 가장 가까운 Suspense 경계까지를 클라이언트 렌더로 만든다. */}
      <Suspense fallback={<div className={styles.form} />}>
        <RequireAuth>
          <NicknameForm />
        </RequireAuth>
      </Suspense>
    </main>
  );
}
