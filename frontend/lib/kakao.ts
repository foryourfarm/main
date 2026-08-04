// 카카오 인가 요청 URL + CSRF state. 계약: docs/auth-security.md §카카오.
//
// **인가 URL을 FE가 만든다.** 백엔드가 리다이렉트를 받으면 access token을 FE 메모리로 넘길 길이
// 없기 때문이다(access는 localStorage에 두지 않는 정책 — lib/auth.ts). 그래서 카카오는 FE 콜백
// 페이지로 돌아오고, FE가 인가코드를 백엔드에 POST한다.
//
// REST API 키는 비밀이 아니다(인가 URL에 그대로 실려 나가는 값이다). 비밀인 client secret은
// 서버에만 있다.

const REST_API_KEY = process.env.NEXT_PUBLIC_KAKAO_REST_API_KEY ?? "";
const REDIRECT_URI = process.env.NEXT_PUBLIC_KAKAO_REDIRECT_URI ?? "";

const STATE_KEY = "kakao_oauth_state";

/** 설정이 없으면 버튼을 아예 숨긴다 — 눌러도 실패하는 버튼을 보여주지 않는다. */
export const isKakaoEnabled = REST_API_KEY !== "" && REDIRECT_URI !== "";

/**
 * 인가 요청 URL. 부수효과로 state를 sessionStorage에 남긴다 — 콜백에서 대조해 **이 탭이 시작한
 * 로그인인지** 확인한다(CSRF 방어). 서버 세션이 없으므로 브라우저에 묶는 것이 이 방식의 요점이고,
 * sessionStorage라 탭을 닫으면 사라진다.
 */
export function buildKakaoAuthUrl(): string {
  const state = crypto.randomUUID();
  sessionStorage.setItem(STATE_KEY, state);
  const params = new URLSearchParams({
    client_id: REST_API_KEY,
    redirect_uri: REDIRECT_URI,
    response_type: "code",
    state,
    // 동의 항목을 요청하지 않는다 — 회원번호(식별)와 닉네임(표시)만 쓰고, 이메일은 받지 않는다.
    // 받아서 저장하면 기존 이메일 계정과의 충돌·연결 문제가 생긴다(backend 0037 주석).
  });
  return `https://kauth.kakao.com/oauth/authorize?${params.toString()}`;
}

/**
 * 콜백으로 돌아온 state가 우리가 보낸 것과 같은지. **한 번 쓰면 지운다**(재사용 방지).
 * 저장된 state가 없으면(직접 URL 진입 등) 실패로 본다.
 */
export function consumeKakaoState(returned: string | null): boolean {
  const saved = sessionStorage.getItem(STATE_KEY);
  sessionStorage.removeItem(STATE_KEY);
  return saved !== null && returned !== null && saved === returned;
}
