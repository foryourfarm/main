// 인증 도메인 타입. 계약: docs/auth-security.md.
export interface User {
  id: number;
  /** 카카오 계정은 null — 카카오에서 이메일을 받지 않는다(마이그레이션 0037). */
  email: string | null;
  nickname: string;
}

/** 카카오 로그인 결과. `isNewUser`면 계정이 방금 만들어진 것 → 닉네임부터 받는다. */
export interface KakaoLoginResult {
  user: User;
  isNewUser: boolean;
}
