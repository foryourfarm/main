"use client";

import { Moon, Sun, Wheat } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth-context";
import { getTheme, setTheme, THEME_KEY } from "@/lib/theme";

import styles from "./Header.module.css";

/** 상단바 — 로고, 인증 상태(구 AuthBar), 다크모드 토글. */
export default function Header() {
  const { user, loading, logout } = useAuth();
  // 실제 테마는 layout의 인라인 스크립트가 페인트 전에 html[data-theme]로 이미 적용했다.
  // 여기 상태는 토글 아이콘 표시용 — 마운트 후 DOM에서 읽어 동기화한다.
  const [isDarkMode, setIsDarkMode] = useState(true);

  useEffect(() => {
    setIsDarkMode(getTheme() === "dark");
    // 사용자가 직접 고르지 않았을 때만 OS 테마 변경을 따라간다(수동 우선).
    const mq = window.matchMedia("(prefers-color-scheme: light)");
    const onChange = () => {
      if (localStorage.getItem(THEME_KEY)) return;
      const next = mq.matches ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      setIsDarkMode(next === "dark");
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const toggleDarkMode = () => {
    const next = isDarkMode ? "light" : "dark";
    setTheme(next);
    setIsDarkMode(next === "dark");
  };

  return (
    <header className={styles.header}>
      <Link href="/dashboard" className={styles.logo}>
        <Wheat size={22} aria-hidden="true" /> For Your Farm
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
          {isDarkMode ? <Sun size={18} aria-hidden="true" /> : <Moon size={18} aria-hidden="true" />}
        </button>
      </div>
    </header>
  );
}
