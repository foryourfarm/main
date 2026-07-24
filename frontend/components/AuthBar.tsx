"use client";

import Link from "next/link";

import { useAuth } from "@/lib/auth-context";

import styles from "./auth.module.css";

/** 화면 우상단 인증 상태. 로그인 상태면 닉네임+로그아웃, 아니면 로그인 링크. */
export default function AuthBar() {
  const { user, loading, logout } = useAuth();

  if (loading) return null; // 세션 복구 중엔 깜빡임 방지로 비움

  return (
    <div className={styles.bar}>
      {user ? (
        <>
          <span className={styles.who}>{user.nickname}님</span>
          <button type="button" onClick={() => void logout()}>
            로그아웃
          </button>
        </>
      ) : (
        <Link href="/login">로그인</Link>
      )}
    </div>
  );
}
