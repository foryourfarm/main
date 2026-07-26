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
