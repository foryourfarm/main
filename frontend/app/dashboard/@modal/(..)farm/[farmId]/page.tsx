"use client";

import { useParams } from "next/navigation";

import { FarmDetail } from "@/app/farm/[farmId]/page";
import Modal from "@/components/Modal";
import RequireAuth from "@/components/RequireAuth";
import styles from "@/components/farm.module.css";

/** 대시보드 카드 클릭 시 이 라우트가 /farm/[farmId]를 가로채 모달로 띄운다(intercepting route).
 * 직접 URL 진입·새로고침 시엔 인터셉트가 걸리지 않아 app/farm/[farmId]/page.tsx가 정상 렌더된다. */
export default function FarmDetailModal() {
  const params = useParams<{ farmId: string }>();
  const farmId = Number(params.farmId);

  return (
    <Modal>
      <h2 className={styles.h1}>밭 상세</h2>
      <RequireAuth>
        {Number.isInteger(farmId) && farmId > 0 ? (
          <FarmDetail farmId={farmId} />
        ) : (
          <p className={styles.error}>잘못된 밭 주소입니다.</p>
        )}
      </RequireAuth>
    </Modal>
  );
}
