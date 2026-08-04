"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { usePet } from "@/lib/pet";

import ChatPanel from "./ChatPanel";
import styles from "./ChatDock.module.css";

/**
 * 우하단 텃밭이 버튼 → 우측 상담 패널. 화면을 떠나지 않고 물어볼 수 있게 하는 것이 목적이다.
 *
 * `<dialog>` + `showModal()`을 쓰는 이유는 **Esc 닫기와 포커스 트랩이 공짜**라서다(§8이
 * 요구하는 접근성 기본). 직접 만들면 keydown 리스너 + 포커스 복원 코드를 쓰게 된다.
 *
 * `<ChatPanel>`은 열림 여부와 무관하게 **항상 마운트해 둔다** — 닫을 때 언마운트하면 대화가
 * 날아가서, 닫았다 열면 처음부터 다시 물어야 한다.
 */
export default function ChatDock() {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  // 펫 이름·이미지는 더미 설정(lib/pet) — 펫 관리 창에서 바꾸면 즉시 반영된다.
  const pet = usePet();

  // /chat은 그 자체가 상담 화면이다 — 같은 챗봇을 두 개 띄우지 않는다.
  const hidden = pathname === "/chat";

  useEffect(() => {
    const el = dialogRef.current;
    if (el === null) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) el.close();
  }, [open]);

  useEffect(() => {
    if (hidden) setOpen(false);
  }, [hidden]);

  if (hidden) return null;

  return (
    <>
      <button
        type="button"
        className={styles.launcher}
        onClick={() => setOpen(true)}
        aria-label={`${pet.name}에게 상담하기`}
      >
        {/* next/image 대신 img: 펫 관리에서 임의 URL을 넣을 수 있어 도메인 화이트리스트를 안 탄다. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={pet.image} alt="" width={56} height={56} className={styles.launcherIcon} />
      </button>

      <dialog
        ref={dialogRef}
        className={styles.drawer}
        // Esc·닫기 버튼 모두 이 이벤트로 들어온다 — 상태를 한 곳에서 되맞춘다.
        onClose={() => setOpen(false)}
        // 네이티브 dialog는 배경 클릭으로 닫히지 않는다. 클릭 대상이 dialog 자신이면
        // (=자식이 아니면) 배경을 누른 것이다.
        onClick={(e) => {
          if (e.target === dialogRef.current) setOpen(false);
        }}
      >
        <div className={styles.drawerInner}>
          <button
            type="button"
            className={styles.close}
            onClick={() => setOpen(false)}
            aria-label="상담 닫기"
          >
            ✕
          </button>
          <ChatPanel embedded />
        </div>
      </dialog>
    </>
  );
}
