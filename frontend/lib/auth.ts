import type { User } from "@/types/auth";

// 인증 계약: docs/auth-security.md.
// access = 메모리에만(localStorage 금지, XSS 시 탈취 표면 최소화). refresh = httpOnly 쿠키(브라우저 자동, JS 접근 불가).
// 모든 요청 credentials:"include"(refresh 쿠키 동반). 응답은 공통 래퍼 {success,data,error}(스트리밍 챗봇만 예외).
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

let accessToken: string | null = null;
let accessIssuedAt = 0;
export const getAccessToken = (): string | null => accessToken;

// access TTL 30분(backend config). 스트리밍(SSE) 호출은 authFetch의 "401 → refresh → 재시도"를
// 쓸 수 없다 — 챗봇은 무효 토큰을 401이 아니라 게스트로 처리하므로(docs/llm-integration.md §11)
// 만료를 알아챌 방법이 없고, 조용히 밭 컨텍스트만 사라진다. 그래서 보내기 전에 선제 갱신한다.
const ACCESS_REFRESH_AFTER_MS = 25 * 60_000;

interface ApiResponse<T> {
  success: boolean;
  data: T | null;
  error: { code: string; message: string } | null;
}

export class AuthError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "AuthError";
  }
}

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
    credentials: "include",
  });
  const body = (await res.json()) as ApiResponse<T>;
  if (!res.ok || !body.success) {
    throw new AuthError(
      body.error?.code ?? `HTTP_${res.status}`,
      body.error?.message ?? "요청을 처리하지 못했습니다.",
      res.status,
    );
  }
  return body.data as T;
}

export function signup(email: string, password: string, nickname: string): Promise<User> {
  return api<User>("/api/v1/auth/signup", {
    method: "POST",
    body: JSON.stringify({ email, password, nickname }),
  });
}

export async function login(email: string, password: string): Promise<User> {
  const data = await api<{ access_token: string; user: User }>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  accessToken = data.access_token; // 메모리 저장
  accessIssuedAt = Date.now();
  return data.user;
}

export async function refresh(): Promise<string> {
  // 본문 없음 — 브라우저가 refresh 쿠키 자동 첨부. 실패(401)면 AuthError → 재로그인 강제.
  const data = await api<{ access_token: string }>("/api/v1/auth/refresh", { method: "POST" });
  accessToken = data.access_token;
  accessIssuedAt = Date.now();
  return data.access_token;
}

/** 곧 만료될(또는 없는) access를 미리 갱신해서 돌려준다. 실패하면 null(게스트로 진행). */
export async function ensureAccessToken(): Promise<string | null> {
  if (accessToken !== null && Date.now() - accessIssuedAt < ACCESS_REFRESH_AFTER_MS) return accessToken;
  try {
    return await refresh();
  } catch {
    return null;
  }
}

export async function logout(): Promise<void> {
  try {
    await api<string>("/api/v1/auth/logout", { method: "POST" });
  } finally {
    accessToken = null; // 서버 실패와 무관하게 클라 access는 폐기
  }
}

/**
 * 보호된 API 호출: Bearer access 첨부 + 401이면 refresh 1회 후 재시도(docs/auth-security.md §51).
 * 토큰이 없거나(리로드 직후) 만료면 401 → refresh 쿠키로 복구 시도 → 그래도 401이면 던진다(로그인 필요).
 */
export async function authFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const call = () =>
    api<T>(path, {
      ...init,
      headers: {
        ...(init.headers ?? {}),
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
    });
  try {
    return await call();
  } catch (e) {
    if (e instanceof AuthError && e.status === 401) {
      await refresh(); // 실패 시 AuthError 전파
      return await call(); // 새 access로 원요청 1회 재시도
    }
    throw e;
  }
}

export function me(): Promise<User> {
  return authFetch<User>("/api/v1/auth/me");
}
