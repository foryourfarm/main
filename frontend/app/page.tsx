import { redirect } from "next/navigation";

export default function Home() {
  // 아직 챗봇 화면만 있음. 루트는 상담으로 보낸다(대시보드/온보딩 붙으면 교체).
  redirect("/chat");
}
