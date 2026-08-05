import { defineConfig } from "vitest/config";

// tsconfig의 @/* 별칭을 vitest도 그대로 쓰도록. lib/·types/ 전부 상대경로로 바꾸는 대신
// 여기 한 곳만 맞춘다. `.mts` + `import.meta.dirname`을 쓰는 이유는 Vite가 다음 메이저에서
// 설정 파일을 native ESM으로만 읽기 때문이다(`__dirname`·CJS는 그때 깨진다).
export default defineConfig({
  resolve: {
    alias: {
      "@": import.meta.dirname,
    },
  },
});
