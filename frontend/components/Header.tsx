"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth-context";

import styles from "./Header.module.css";

const DARK_MODE_KEY = "darkMode";

/** 상단바 — 로고, 인증 상태(구 AuthBar), 다크모드 토글. */
export default function Header() {
  const { user, loading, logout } = useAuth();
  const [isDarkMode, setIsDarkMode] = useState(false);

  // 토글 상태는 localStorage에만 둔다(서버에 저장할 만한 값이 아님).
  // SSR에서 읽을 수 없어 마운트 후 적용 — 첫 프레임이 라이트로 깜빡일 수 있다.
  useEffect(() => {
    if (localStorage.getItem(DARK_MODE_KEY) === "true") {
      setIsDarkMode(true);
      document.body.classList.add("dark-mode");
    }
  }, []);

  const toggleDarkMode = () => {
    const next = !isDarkMode;
    setIsDarkMode(next);
    localStorage.setItem(DARK_MODE_KEY, String(next));
    document.body.classList.toggle("dark-mode", next);
  };

  return (
    <header className={styles.header}>
      <Link href="/dashboard" className={styles.logo}>
        🌾 For Your Farm
      </Link>
      <div className={styles.headerRight}>
        {/* 세션 복구 중엔 비운다 — 로그인 링크가 잠깐 떴다 사라지는 깜빡임 방지. */}
        {!loading &&
          (user ? (
            <div className={styles.userInfo}>
              <span className={styles.userName}>{user.nickname}님</span>
              <button type="button" className={styles.textButton} onClick={() => void logout()}>
                로그아웃
              </button>
            </div>
          ) : (
            <Link href="/login" className={styles.textButton}>
              로그인
            </Link>
          ))}
        <button
          type="button"
          className={styles.darkToggle}
          onClick={toggleDarkMode}
          aria-pressed={isDarkMode}
          aria-label={isDarkMode ? "라이트 모드로 전환" : "다크 모드로 전환"}
        >
          {isDarkMode ? "☀️" : "🌙"}
        </button>
      </div>
    </header>
  );
}
