"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AuthError, signup } from "@/lib/auth";
import { buildKakaoAuthUrl, isKakaoEnabled } from "@/lib/kakao";
import styles from "@/components/auth.module.css";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [nickname, setNickname] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await signup(email, password, nickname);
      // 가입은 토큰 발급 안 함 → 로그인 화면으로(docs/auth-security.md).
      router.push("/login");
    } catch (err) {
      if (err instanceof AuthError && err.code === "EMAIL_EXISTS") {
        setError("이미 가입된 이메일입니다.");
      } else if (err instanceof AuthError && err.status === 422) {
        setError("입력 형식을 확인해 주세요. (비밀번호 8자 이상)");
      } else {
        setError("가입에 실패했습니다. 잠시 후 다시 시도해 주세요.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    // layout.tsx의 <main className="appMain">이 이미 main 랜드마크 — 중첩 main 금지.
    <div className={styles.wrap}>
      <section className={styles.card}>
        <h1 className={styles.title}>회원가입</h1>
        <p className={styles.lead}>내 밭에 맞는 오늘의 안내를 받아보세요.</p>
        <form className={styles.form} onSubmit={onSubmit}>
          <div className={styles.field}>
            <label htmlFor="email">이메일</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              aria-describedby={error !== "" ? "signup-error" : undefined}
            />
          </div>
          <div className={styles.field}>
            <label htmlFor="nickname">닉네임</label>
            <input
              id="nickname"
              type="text"
              maxLength={50}
              required
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
            />
          </div>
          <div className={styles.field}>
            <label htmlFor="password">비밀번호 (8자 이상)</label>
            <input
              id="password"
              type="password"
              autoComplete="new-password"
              minLength={8}
              maxLength={128}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-describedby={error !== "" ? "signup-error" : undefined}
            />
          </div>
          {error && (
            <p id="signup-error" role="alert" className={styles.error}>
              {error}
            </p>
          )}
          <button className={styles.submit} type="submit" disabled={busy}>
            {busy ? "가입 중…" : "회원가입"}
          </button>
        </form>
        {/* 카카오는 가입·로그인이 같은 경로다(신규면 콜백이 이름 정하는 화면으로 보낸다) —
            그래서 문구만 "시작하기"로 두고 로그인 화면과 같은 버튼을 쓴다(§6-13).
            구분선은 아래에 버튼이 있을 때만 — 빈 구분선을 두지 않는다. */}
        {isKakaoEnabled && (
          <>
            <div className={styles.divider} aria-hidden="true">
              또는
            </div>
            <button
              type="button"
              className={styles.kakao}
              onClick={() => {
                window.location.href = buildKakaoAuthUrl();
              }}
            >
              카카오로 시작하기
            </button>
          </>
        )}
        <p className={styles.alt}>
          이미 계정이 있으신가요? <Link href="/login">로그인</Link>
        </p>
      </section>
    </div>
  );
}
