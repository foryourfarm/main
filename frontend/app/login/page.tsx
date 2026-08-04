"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/lib/auth-context";
import { buildKakaoAuthUrl, isKakaoEnabled } from "@/lib/kakao";
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

        {isKakaoEnabled && (
          <>
            <p className={styles.divider}>또는</p>
            {/* 카카오 인가 화면으로 **페이지 전체가 이동**한다(fetch가 아니다) — 그래서 form
                안이지만 submit이 되지 않게 type="button"이고, state를 남긴 뒤 이동한다. */}
            <button
              type="button"
              className={styles.kakao}
              onClick={() => {
                window.location.href = buildKakaoAuthUrl();
              }}
            >
              {/* 색만으로 카카오임을 알리지 않는다 — 텍스트로 명시(§8). */}
              카카오로 로그인
            </button>
          </>
        )}

        <p className={styles.alt}>
          계정이 없으신가요? <Link href="/signup">회원가입</Link>
        </p>
      </form>
    </main>
  );
}
