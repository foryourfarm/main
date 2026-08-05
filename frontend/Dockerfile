# 빌드 컨텍스트는 frontend/ (docker build -f frontend/Dockerfile frontend 로 실행).
# NEXT_PUBLIC_* 값은 next build 시점에 클라이언트 번들에 굳는다 — 런타임 env로는 못 바꾸므로
# 반드시 --build-arg로 넘긴다(gcloud run deploy의 --set-env-vars는 여기엔 안 먹는다).
FROM node:24-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:24-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_API_BASE
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
# 카카오 로그인(0037). 인가 URL을 FE가 만들므로 이 둘도 **빌드 시점에** 굳어야 한다
# (lib/kakao.ts). 빠지면 `isKakaoEnabled`가 false가 되어 **버튼이 조용히 사라진다** —
# 배포는 성공하고 화면에서야 없어진 것을 알게 되는 부류다. REST API 키는 비밀이 아니다
# (인가 URL에 그대로 실려 나간다). 비밀인 client secret은 백엔드 env에만 둔다.
ARG NEXT_PUBLIC_KAKAO_REST_API_KEY
ENV NEXT_PUBLIC_KAKAO_REST_API_KEY=$NEXT_PUBLIC_KAKAO_REST_API_KEY
ARG NEXT_PUBLIC_KAKAO_REDIRECT_URI
ENV NEXT_PUBLIC_KAKAO_REDIRECT_URI=$NEXT_PUBLIC_KAKAO_REDIRECT_URI
RUN npm run build

FROM node:24-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

# Cloud Run은 $PORT로 리스닝 포트를 주입한다(기본 8080).
ENV PORT=8080
ENV HOSTNAME=0.0.0.0
EXPOSE 8080

CMD ["node", "server.js"]
