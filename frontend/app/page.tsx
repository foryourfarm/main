import { redirect } from "next/navigation";

export default function Home() {
  // 로그인 여부는 서버에서 알 수 없다(access는 메모리, refresh 쿠키는 백엔드 오리진 스코프).
  // 일단 대시보드로 보내고, 미로그인이면 RequireAuth가 /login으로 넘긴다.
  redirect("/dashboard");
}
