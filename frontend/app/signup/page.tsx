"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AuthError, signup } from "@/lib/auth";
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
    <main className={styles.wrap}>
      <form className={styles.form} onSubmit={onSubmit}>
        <h1>회원가입</h1>
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
          />
        </div>
        {error && <p className={styles.error}>{error}</p>}
        <button className={styles.submit} type="submit" disabled={busy}>
          {busy ? "가입 중…" : "회원가입"}
        </button>
        <p className={styles.alt}>
          이미 계정이 있으신가요? <Link href="/login">로그인</Link>
        </p>
      </form>
    </main>
  );
}
