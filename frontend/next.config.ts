import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Cloud Run 배포용 — node_modules 전체 없이 트레이싱된 파일만으로 서버 실행(Dockerfile 참고).
  output: "standalone",
};

export default nextConfig;
