import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Cloud Run 배포용 — node_modules 전체 없이 트레이싱된 파일만으로 서버 실행(Dockerfile 참고).
  output: "standalone",
  // 폰 실기 확인용. LAN IP로 dev 서버를 열면 /_next/* 자산·HMR이 교차오리진으로 막혀
  // 하이드레이션이 통째로 실패한다(버튼이 전부 먹통이 된다). 각자 IP는 환경변수로 넣는다:
  //   DEV_LAN_ORIGIN=192.168.0.23 npm run dev -- -H 0.0.0.0
  // 개인 IP를 저장소에 박지 않기 위해 하드코딩하지 않는다.
  allowedDevOrigins: process.env.DEV_LAN_ORIGIN ? [process.env.DEV_LAN_ORIGIN] : undefined,
};

export default nextConfig;
