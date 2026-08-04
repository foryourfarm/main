"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/lib/auth-context";
import styles from "@/components/auth.module.css";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(email, password);
      router.push("/dashboard"); // 로그인 후 기본 착지는 내 밭(대시보드)
    } catch {
      // 계정 열거 방지로 백엔드가 일반화한 문구를 그대로 노출(어느 필드가 틀렸는지 구분 안 줌).
      setError("이메일 또는 비밀번호가 올바르지 않습니다.");
    } finally {
      setBusy(false);
    }
  }

  return (
    // layout.tsx의 <main className="appMain">이 이미 main 랜드마크 — 중첩 main 금지.
    <div className={styles.wrap}>
      <section className={styles.card}>
        <h1 className={styles.title}>로그인</h1>
        <p className={styles.lead}>내 밭의 오늘을 읽는 농사 동반자</p>
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
              aria-describedby={error !== "" ? "login-error" : undefined}
            />
          </div>
          <div className={styles.field}>
            <label htmlFor="password">비밀번호</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-describedby={error !== "" ? "login-error" : undefined}
            />
          </div>
          {error && (
            <p id="login-error" role="alert" className={styles.error}>
              {error}
            </p>
          )}
          <button className={styles.submit} type="submit" disabled={busy}>
            {busy ? "로그인 중…" : "로그인"}
          </button>
        </form>
        <div className={styles.divider} aria-hidden="true">
          또는
        </div>
        {/* 카카오 로그인 버튼 자리(FrontEnd.md §6-13) — 백엔드 OAuth 준비 전에는
            동작하는 척하는 버튼을 렌더하지 않는다. 준비되면 이 divider 아래에 추가. */}
        <p className={styles.alt}>
          계정이 없으신가요? <Link href="/signup">회원가입</Link>
        </p>
      </section>
    </div>
  );
}
