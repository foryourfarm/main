"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import type { ReactNode } from "react";

import styles from "./Modal.module.css";

/** 대시보드 카드 → 밭 상세를 오버레이로 띄우는 데 쓰는 범용 모달 (intercepting route 전용). */
export default function Modal({ children }: { children: ReactNode }) {
  const router = useRouter();
  const close = () => router.back();

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className={styles.overlay} onClick={close}>
      <div
        className={styles.content}
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
      >
        <button type="button" className={styles.close} onClick={close} aria-label="닫기">
          ✕
        </button>
        {children}
      </div>
    </div>
  );
}
