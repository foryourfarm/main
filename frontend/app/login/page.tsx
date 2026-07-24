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
      router.push("/chat");
    } catch {
      // 계정 열거 방지로 백엔드가 일반화한 문구를 그대로 노출(어느 필드가 틀렸는지 구분 안 줌).
      setError("이메일 또는 비밀번호가 올바르지 않습니다.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className={styles.wrap}>
      <form className={styles.form} onSubmit={onSubmit}>
        <h1>로그인</h1>
        <div className={styles.field}>
          <label htmlFor="email">이메일</label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
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
          />
        </div>
        {error && <p className={styles.error}>{error}</p>}
        <button className={styles.submit} type="submit" disabled={busy}>
          {busy ? "로그인 중…" : "로그인"}
        </button>
        <p className={styles.alt}>
          계정이 없으신가요? <Link href="/signup">회원가입</Link>
        </p>
      </form>
    </main>
  );
}
