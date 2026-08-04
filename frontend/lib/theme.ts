export type Theme = "dark" | "light";

export const THEME_KEY = "theme";

/**
 * layout.tsx <head>에 인라인으로 삽입 — 첫 페인트 전에 실행돼 테마 깜빡임(FOUC)을 막는다.
 * (근거: node_modules/next/dist/docs/01-app/02-guides/preventing-flash-before-hydration.md)
 *
 * 우선순위: localStorage("theme") → 구 "darkMode" 키 마이그레이션 → OS prefers-color-scheme → dark.
 * 구 키를 지우고 새 키로 옮긴다 — 과거에 토글한 사용자의 선택을 보존하기 위해서다(§6-10 다크모드 설정 저장 보존).
 */
export const THEME_INIT_SCRIPT = `(function(){try{var t=localStorage.getItem("theme");if(!t){var d=localStorage.getItem("darkMode");if(d!==null){t=d==="true"?"dark":"light";localStorage.setItem("theme",t);localStorage.removeItem("darkMode")}}if(t!=="dark"&&t!=="light"){t=window.matchMedia("(prefers-color-scheme: light)").matches?"light":"dark"}document.documentElement.setAttribute("data-theme",t)}catch(e){}})()`;

export function getTheme(): Theme {
  return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
}

/** 사용자의 명시적 선택 — 저장하므로 이후 OS 테마 변경보다 우선한다(수동 우선). */
export function setTheme(theme: Theme): void {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem(THEME_KEY, theme);
}
