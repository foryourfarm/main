import type { Metadata } from "next";
import "./globals.css";

import Header from "@/components/Header";
import Navigation from "@/components/Navigation";
import RequireAuth from "@/components/RequireAuth";
import { AuthProvider } from "@/lib/auth-context";

export const metadata: Metadata = {
  title: "For Your Farm",
  description: "내 땅과 오늘 날씨에 맞는 맞춤형 농사 가이드",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body>
        <AuthProvider>
          <Header />
          <Navigation />
          <main style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <RequireAuth>{children}</RequireAuth>
          </main>
        </AuthProvider>
      </body>
    </html>
  );
}
