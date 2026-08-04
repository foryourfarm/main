"use client";

import { createContext, useContext, useEffect, useState } from "react";

import {
  login as apiLogin,
  loginWithKakao as apiLoginWithKakao,
  logout as apiLogout,
  me,
  updateNickname as apiUpdateNickname,
} from "@/lib/auth";
import type { User } from "@/types/auth";

interface AuthState {
  user: User | null;
  loading: boolean; // 최초 세션 복구 중
  login: (email: string, password: string) => Promise<void>;
  /** 계정이 방금 만들어졌는지 돌려준다 — 호출부가 닉네임 화면으로 보낼지 판단한다. */
  loginWithKakao: (code: string) => Promise<boolean>;
  updateNickname: (nickname: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // access는 메모리라 리로드 시 사라짐 → me() 호출이 401이면 authFetch가 refresh 쿠키로 복구 시도.
  // 복구 실패(쿠키 없음/만료)면 그냥 게스트로 둔다(에러 아님).
  useEffect(() => {
    me()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    setUser(await apiLogin(email, password));
  };
  const loginWithKakao = async (code: string) => {
    const { user: next, isNewUser } = await apiLoginWithKakao(code);
    setUser(next);
    return isNewUser;
  };
  const updateNickname = async (nickname: string) => {
    // 서버가 돌려준 유저로 갈아끼운다 — 헤더의 "○○님"이 즉시 따라온다.
    setUser(await apiUpdateNickname(nickname));
  };
  const logout = async () => {
    await apiLogout();
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{ user, loading, login, loginWithKakao, updateNickname, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (ctx === null) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
