"use client";

import { Moon, Sun, Wheat } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth-context";
import { getTheme, setTheme, THEME_KEY } from "@/lib/theme";

import { isNavActive, NAV_ITEMS } from "./Navigation";
import styles from "./Header.module.css";

/**
 * comUI 탑바 재현(§8) — sticky + blur, 1240px 컨테이너 안에
 * 브랜드(로고+부제) / 알약 내비(데스크톱) / 유저 칩 / 원형 테마 버튼.
 * 모바일 내비는 Navigation(하단 탭)이 담당한다.
 */
export default function Header() {
  const { user, loading, logout } = useAuth();
  const pathname = usePathname();
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
    <header className={styles.topbar}>
      <div className={styles.inner}>
        <Link href="/dashboard" className={styles.brand}>
          <Wheat size={30} aria-hidden="true" className={styles.brandIcon} />
          <span className={styles.brandText}>
            For Your Farm
            <small>내 땅의 오늘을 읽는 농사 동반자</small>
          </span>
        </Link>

        <nav className={styles.navpill} aria-label="주요 메뉴">
          {NAV_ITEMS.map((item) => {
            const active = isNavActive(pathname, item);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`${styles.pillItem} ${active ? styles.pillActive : ""}`}
                aria-current={active ? "page" : undefined}
              >
                <item.Icon size={16} aria-hidden="true" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* 세션 복구 중엔 비운다 — 로그인 링크가 잠깐 떴다 사라지는 깜빡임 방지. */}
        {!loading &&
          (user ? (
            <div className={styles.userChip}>
              <span className={styles.avatar} aria-hidden="true">
                {user.nickname.slice(0, 1)}
              </span>
              <b>{user.nickname}</b>님
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
          className={styles.iconBtn}
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
