"use client";

import { X } from "lucide-react";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/lib/auth-context";
import { LAUNCHER_ICON } from "@/lib/pet";

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
  const { user, loading } = useAuth();

  // 숨기는 경우 둘:
  // 1. /chat — 그 자체가 상담 화면이다. 같은 챗봇을 두 개 띄우지 않는다.
  // 2. 비로그인 — 백엔드 `/api/v1/chat`이 로그인을 요구한다(PRD §4.1 "로그인 필수"). 버튼을
  //    남겨두면 눌렀을 때 401로 실패하는 "동작하는 척하는 버튼"이 된다(§1-8). 세션 복구가
  //    끝나기 전(`loading`)에도 감춘다 — 리로드 직후 버튼이 깜빡였다 사라지지 않게.
  const hidden = pathname === "/chat" || loading || user === null;

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
        aria-label="농사 상담 열기"
      >
        {/* 지금은 펫 단계와 무관한 고정 아이콘이다 — 몇 레벨인지는 패널을 열면 PetQuestBar가
            서버 값으로 보여준다. (이 버튼은 로그인 유저만 보므로 단계를 따라가게 만드는 것도
            가능하다 — lib/pet.ts의 LAUNCHER_ICON ponytail 주석.) */}
        <Image
          src={LAUNCHER_ICON}
          alt=""
          width={56}
          height={56}
          className={styles.launcherIcon}
        />
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
            {/* 문자 기호가 아니라 아이콘 — 이모지·기호는 폰트에 따라 크기·굵기가 흔들린다. */}
            <X size={18} aria-hidden />
          </button>
          <ChatPanel embedded />
        </div>
      </dialog>
    </>
  );
}
