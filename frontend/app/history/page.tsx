import { NotebookPen } from "lucide-react";
import type { Metadata } from "next";

import { Card, CardHeader } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";

import styles from "./history.module.css";

export const metadata: Metadata = {
  title: "기록 — For Your Farm",
};

/**
 * 행동 기록 화면 — FrontEnd.md §12-1 "칸만 만드는 카드".
 * UI 자리만 두고 기능은 구현하지 않는다: 가짜 목록·동작하는 척하는 버튼 금지,
 * 스키마를 추측한 타입·API 호출도 미리 만들지 않는다. 기능은 추후 별도 작업.
 */
export default function HistoryPage() {
  return (
    // layout.tsx의 <main className="appMain">이 이미 main 랜드마크 — 중첩 main 금지.
    <div className="wrap">
      <h1 className={styles.h1}>행동 기록</h1>
      <p className={styles.sub}>밭에서 한 일과 시스템이 감지한 변화를 시간순으로 모아 보는 공간입니다.</p>
      <Card>
        <CardHeader icon={<NotebookPen size={16} />} title="기록 타임라인" tag="준비 중" />
        <EmptyState
          badge="준비 중"
          icon={<NotebookPen size={28} />}
          title="아직 준비 중인 기능이에요"
          hint="관수·적과 같은 행동 기록과 위험 감지 이력이 여기에 쌓일 예정입니다."
        />
      </Card>
    </div>
  );
}
