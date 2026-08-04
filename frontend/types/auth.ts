// 인증 도메인 타입. 계약: docs/auth-security.md.
export interface User {
  id: number;
  /** 카카오 계정은 null — 카카오에서 이메일을 받지 않는다(마이그레이션 0037). */
  email: string | null;
  nickname: string;
}
