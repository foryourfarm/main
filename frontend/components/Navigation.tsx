"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import styles from "./Navigation.module.css";

const ITEMS = [
  { href: "/dashboard", label: "📊 대시보드" },
  { href: "/chat", label: "💬 상담" },
  { href: "/onboarding", label: "🌱 밭 등록" },
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
