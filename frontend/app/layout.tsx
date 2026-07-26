import type { Metadata } from "next";
import { Noto_Sans_KR, Noto_Serif_KR } from "next/font/google";
import "./globals.css";

import Header from "@/components/Header";
import Navigation from "@/components/Navigation";
import { AuthProvider } from "@/lib/auth-context";

const notoSans = Noto_Sans_KR({
  variable: "--font-body",
  subsets: ["latin"],
});

const notoSerif = Noto_Serif_KR({
  variable: "--font-heading",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "For Your Farm",
  description: "내 땅과 오늘 날씨에 맞는 맞춤형 농사 가이드",
};

/**
 * 로그인 게이팅(RequireAuth)을 여기 걸지 않는 이유: children에 /login·/signup이 포함돼
 * 리다이렉트가 자기 자신을 막는다(로그인 폼에 영영 도달 못 함). 게이팅은 보호가 필요한
 * 페이지가 각자 감싼다 — dashboard·farm·onboarding. /chat은 게스트 모드라 의도적으로 열려 있다.
 */
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className={`${notoSans.variable} ${notoSerif.variable}`}>
      <body>
        <AuthProvider>
          <Header />
          <Navigation />
          <main className="appMain">{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
