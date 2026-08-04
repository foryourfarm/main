"use client";

import { MessageCircle, Settings, Sprout } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import styles from "./Navigation.module.css";

/**
 * 탭은 내 밭 / 상담 / 설정. "밭 상세"는 밭 컨텍스트 종속이라 탭이 아니라 대시보드 카드에서
 * 진입한다. 데스크톱은 상단 탭, 모바일(<768px)은 하단 고정 탭으로 같은 마크업을 CSS가 바꾼다(§9).
 *
 * FrontEnd.md §6-5는 원래 내 밭 / **기록** / 설정이었다. 기록 탭은 사용자 요청으로 상담으로
 * 교체됐고, 이후 `/history` 페이지(행동기록 "준비 중" 껍데기)까지 삭제했다 — 행동기록은 유저가
 * 직접 입력해야 하는데 그 화면을 만들 계획이 없어 영원히 빈 채로 남는 자리였다.
 */
export const NAV_ITEMS = [
  // /farm/*(밭 상세)도 "내 밭" 흐름이므로 활성 표시를 이어준다.
  { href: "/dashboard", label: "내 밭", Icon: Sprout, also: "/farm" },
  { href: "/chat", label: "상담", Icon: MessageCircle, also: null },
  { href: "/settings", label: "설정", Icon: Settings, also: null },
] as const;

/** 항목이 현재 경로에서 활성인지 — Header(데스크톱 알약)와 하단 탭이 공유한다. */
export function isNavActive(pathname: string, item: (typeof NAV_ITEMS)[number]): boolean {
  return (
    pathname === item.href ||
    pathname.startsWith(`${item.href}/`) ||
    (item.also !== null && pathname.startsWith(`${item.also}/`))
  );
}

/** 모바일 전용 하단 탭(§9). 데스크톱(≥768px)에서는 CSS가 숨기고 Header의 알약 내비가 대신한다. */
export default function Navigation() {
  const pathname = usePathname();

  return (
    <nav className={styles.nav} aria-label="주요 메뉴">
      {NAV_ITEMS.map((item) => {
        const { href, label, Icon } = item;
        const isActive = isNavActive(pathname, item);
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
