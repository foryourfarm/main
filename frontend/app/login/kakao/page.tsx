"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { useAuth } from "@/lib/auth-context";
import { consumeKakaoState } from "@/lib/kakao";
import styles from "@/components/auth.module.css";

/**
 * 카카오 인가 콜백. 카카오 앱에 등록하는 Redirect URI가 이 경로다(`/login/kakao`).
 *
 * **여기가 리다이렉트 착지점인 이유**: access token을 메모리에만 두는 정책이라(lib/auth.ts)
 * 백엔드가 리다이렉트를 받으면 토큰을 FE 메모리로 넘길 길이 없다. 그래서 카카오는 FE로 돌아오고
 * FE가 인가코드를 백엔드에 POST한다(`POST /api/v1/auth/kakao`).
 *
 * 화면 자체는 지나가는 자리다 — 성공하면 곧바로 대시보드로 보낸다.
 */
function KakaoCallback() {
  const params = useSearchParams();
  const router = useRouter();
  const { loginWithKakao } = useAuth();
  const [error, setError] = useState<string | null>(null);
  // 인가코드는 **1회용**이다. effect가 두 번 돌면(개발 모드 StrictMode의 이중 실행) 두 번째
  // 교환이 반드시 실패해 "실패" 화면이 뜬다. 그래서 코드당 한 번만 보낸다.
  const sent = useRef(false);

  useEffect(() => {
    if (sent.current) return;
    sent.current = true;

    const code = params.get("code");
    const kakaoError = params.get("error");

    // 유저가 동의 화면에서 취소한 경우 — 실패가 아니라 정상 흐름이라 조용히 로그인으로 돌린다.
    if (kakaoError !== null) {
      router.replace("/login");
      return;
    }
    // state 대조(CSRF): 이 탭이 시작한 로그인이 아니면 코드를 서버로 보내지 않는다.
    if (!consumeKakaoState(params.get("state"))) {
      setError("로그인 요청이 확인되지 않았습니다. 다시 시도해 주세요.");
      return;
    }
    if (code === null) {
      setError("카카오에서 인가코드를 받지 못했습니다. 다시 시도해 주세요.");
      return;
    }

    loginWithKakao(code)
      // 처음 온 사람은 이름부터 정하게 한다 — 카카오가 닉네임을 주지 않아 계정이
      // "카카오 사용자"로 시작하고, 그게 헤더에 그대로 나간다. 이름을 정하면 밭 등록으로 이어진다.
      .then((isNewUser) => router.replace(isNewUser ? "/onboarding/nickname" : "/dashboard"))
      .catch(() => setError("카카오 로그인에 실패했습니다. 다시 시도해 주세요."));
  }, [params, router, loginWithKakao]);

  if (error !== null) {
    return (
      <div className={styles.form}>
        <h1>카카오 로그인</h1>
        <p className={styles.error}>{error}</p>
        <p className={styles.alt}>
          <Link href="/login">로그인으로 돌아가기</Link>
        </p>
      </div>
    );
  }
  return (
    <div className={styles.form}>
      <h1>카카오 로그인</h1>
      <p className={styles.alt}>로그인 중입니다…</p>
    </div>
  );
}

export default function KakaoCallbackPage() {
  // useSearchParams는 가장 가까운 Suspense 경계까지를 클라이언트 렌더로 만든다 — 경계를 두어
  // 나머지가 프리렌더될 수 있게 한다(node_modules/next/dist/docs …/use-search-params.md).
  return (
    <main className={styles.wrap}>
      <Suspense
        fallback={
          <div className={styles.form}>
            <h1>카카오 로그인</h1>
            <p className={styles.alt}>로그인 중입니다…</p>
          </div>
        }
      >
        <KakaoCallback />
      </Suspense>
    </main>
  );
}
