'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import styles from './Navigation.module.css';

export default function Navigation() {
  const pathname = usePathname();

  const isActive = (path: string) => {
    if (path === '/dashboard' && pathname.startsWith('/dashboard')) return true;
    if (path === '/chat' && pathname === '/chat') return true;
    if (path === '/settings' && pathname === '/settings') return true;
    return false;
  };

  return (
    <nav className={styles.nav}>
      <Link
        href="/dashboard"
        className={`${styles.navItem} ${isActive('/dashboard') ? styles.active : ''}`}
      >
        📊 대시보드
      </Link>
      <Link
        href="/chat"
        className={`${styles.navItem} ${isActive('/chat') ? styles.active : ''}`}
      >
        💬 상담
      </Link>
      <Link
        href="/settings"
        className={`${styles.navItem} ${isActive('/settings') ? styles.active : ''}`}
      >
        ⚙️ 설정
      </Link>
    </nav>
  );
}
