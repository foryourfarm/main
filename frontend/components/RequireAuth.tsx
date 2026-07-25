"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/lib/auth-context";

import styles from "./farm.module.css";

/**
 * 로그인 게이팅. proxy.ts(구 middleware)로 못 하는 이유:
 * refresh 쿠키가 백엔드 오리진(:8000) + path=/api/v1/auth/refresh로 스코프돼 있어
 * 프론트 오리진(:3000)의 프록시에는 아예 보이지 않는다. access는 메모리에만 있다.
 * 그래서 세션 복구 결과(AuthProvider)를 보고 클라이언트에서 리다이렉트한다.
 *
 * 이건 UX 게이팅일 뿐 인가가 아니다 — 실제 인가는 백엔드가 401/404로 강제한다(§11).
 */
export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user === null) router.replace("/login");
  }, [loading, user, router]);

  if (loading) return <p className={styles.notice}>불러오는 중…</p>;
  if (user === null) return <p className={styles.notice}>로그인이 필요합니다.</p>;
  return <>{children}</>;
}
