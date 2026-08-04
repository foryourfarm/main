"use client";

import { History, Settings, Sprout } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import styles from "./Navigation.module.css";

/**
 * FrontEnd.md §6-5: 탭은 내 밭 / 기록 / 설정 — 상담 탭은 두지 않는다(상담 진입은
 * 펫 플로팅 버튼(ChatDock)이 전담). "밭 상세"는 밭 컨텍스트 종속이라 탭이 아니라
 * 대시보드 카드에서 진입한다.
 * 데스크톱은 상단 탭, 모바일(<768px)은 하단 고정 탭으로 같은 마크업을 CSS가 바꾼다(§9).
 */
const ITEMS = [
  // /farm/*(밭 상세)도 "내 밭" 흐름이므로 활성 표시를 이어준다.
  { href: "/dashboard", label: "내 밭", Icon: Sprout, also: "/farm" },
  { href: "/history", label: "기록", Icon: History, also: null },
  { href: "/settings", label: "설정", Icon: Settings, also: null },
] as const;

export default function Navigation() {
  const pathname = usePathname();

  return (
    <nav className={styles.nav} aria-label="주요 메뉴">
      {ITEMS.map(({ href, label, Icon, also }) => {
        const isActive =
          pathname === href ||
          pathname.startsWith(`${href}/`) ||
          (also !== null && pathname.startsWith(`${also}/`));
        return (
          <Link
            key={href}
            href={href}
            className={`${styles.navItem} ${isActive ? styles.active : ""}`}
            aria-current={isActive ? "page" : undefined}
          >
            <Icon size={20} aria-hidden="true" />
            <span>{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
