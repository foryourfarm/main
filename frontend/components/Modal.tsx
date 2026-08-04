"use client";

import { useCallback, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";

import styles from "./Modal.module.css";

/** 오버레이 모달. 닫는 방식이 두 가지다.
 *
 *  - **라우트 기반**(대시보드 → 밭 상세): `onClose` 없이 쓰면 히스토리를 뒤로 돌린다.
 *    intercepting route가 URL로 모달 상태를 표현하는 구조라 뒤로가기가 곧 닫기다.
 *  - **지역 상태 기반**(단기 탭 → 날짜 상세): `onClose`를 넘기면 그 함수를 부른다. 날짜 상세는
 *    URL을 갖지 않아(같은 탭 안의 보조 정보) 라우터를 건드릴 이유가 없다.
 *
 * `onClose`는 함수 prop이라 **호출부가 클라이언트 컴포넌트여야 한다** — 서버 컴포넌트에서
 * 클라이언트 컴포넌트로 함수를 넘길 수 없다(Next `use client` 문서의 직렬화 제약).
 */
export default function Modal({
  children,
  onClose,
  label,
}: {
  children: ReactNode;
  onClose?: () => void;
  /** 스크린리더용 대화상자 이름. 없으면 속성을 붙이지 않는다. */
  label?: string;
}) {
  const router = useRouter();
  const close = useCallback(() => {
    if (onClose) onClose();
    else router.back();
  }, [onClose, router]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [close]);

  // 열릴 때 포커스를 대화상자 안으로 옮기고, 닫히면 원래 자리로 되돌린다. 이게 없으면
  // 키보드 사용자는 모달이 떠도 포커스가 뒤 화면에 남아 Tab이 배경을 돌아다닌다(§8 접근성).
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    return () => previous?.focus?.();
  }, []);

  return (
    <div className={styles.overlay} onClick={close}>
      <div
        className={styles.content}
        role="dialog"
        aria-modal="true"
        aria-label={label}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          ref={closeRef}
          type="button"
          className={styles.close}
          onClick={close}
          aria-label="닫기"
        >
          ✕
        </button>
        {children}
      </div>
    </div>
  );
}
