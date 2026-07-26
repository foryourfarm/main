"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import styles from "./Navigation.module.css";

// 설계 §1.2: 대시보드 | 상담 | 설정 3개로 간결하게. 밭 등록은 설정·대시보드에서 들어간다.
const ITEMS = [
  { href: "/dashboard", label: "📊 대시보드" },
  { href: "/chat", label: "💬 상담" },
  { href: "/settings", label: "⚙️ 설정" },
] as const;

export default function Navigation() {
  const pathname = usePathname();

  return (
    <nav className={styles.nav}>
      {ITEMS.map(({ href, label }) => {
        const isActive = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            className={`${styles.navItem} ${isActive ? styles.active : ""}`}
            aria-current={isActive ? "page" : undefined}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
