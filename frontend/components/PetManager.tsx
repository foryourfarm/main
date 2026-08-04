"use client";

import { PawPrint } from "lucide-react";
import { useState } from "react";

import { Card, CardHeader, CardNote } from "@/components/ui/Card";
import type { PetConfig } from "@/lib/pet";
import { resetPet, setPet, usePet } from "@/lib/pet";

import styles from "./PetManager.module.css";

/**
 * 펫 관리 창 — 이름·성격·이미지를 바꿔볼 수 있다(FrontEnd.md §11 더미 자산 계약).
 * 저장은 localStorage(이 브라우저 한정). 서버 저장·이미지 업로드는 [백엔드 확장 필요].
 */
export default function PetManager() {
  const pet = usePet();
  // null = 아직 편집 안 함 → 저장값 그대로 표시.
  const [draft, setDraft] = useState<PetConfig | null>(null);
  const [saved, setSaved] = useState(false);
  const value = draft ?? pet;

  const edit = (patch: Partial<PetConfig>) => {
    setSaved(false);
    setDraft({ ...value, ...patch });
  };

  return (
    <Card className={styles.card}>
      <CardHeader icon={<PawPrint size={16} />} title="펫 관리" tag="임시 placeholder" />
      <form
        className={styles.form}
        onSubmit={(e) => {
          e.preventDefault();
          setPet(value);
          setDraft(null);
          setSaved(true);
        }}
      >
        <div className={styles.preview}>
          {/* next/image 대신 img: 사용자가 임의 URL을 넣을 수 있어 도메인 화이트리스트를 안 탄다. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={value.image} alt="펫 이미지 미리보기" className={styles.avatar} />
          <div>
            <b className={styles.previewName}>{value.name}</b>
            <p className={styles.previewPersona}>{value.personality}</p>
          </div>
        </div>

        <div className={styles.field}>
          <label htmlFor="pet-name">이름</label>
          <input
            id="pet-name"
            type="text"
            maxLength={20}
            required
            value={value.name}
            onChange={(e) => edit({ name: e.target.value })}
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="pet-persona">성격 (한 줄 소개)</label>
          <input
            id="pet-persona"
            type="text"
            maxLength={60}
            value={value.personality}
            onChange={(e) => edit({ personality: e.target.value })}
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="pet-image">이미지 경로 또는 URL</label>
          <input
            id="pet-image"
            type="text"
            required
            value={value.image}
            onChange={(e) => edit({ image: e.target.value })}
          />
        </div>

        <div className={styles.actions}>
          <button type="submit" className={styles.save}>
            저장
          </button>
          <button
            type="button"
            className={styles.reset}
            onClick={() => {
              resetPet();
              setDraft(null);
              setSaved(false);
            }}
          >
            기본값 복원
          </button>
          {saved && (
            <span className={styles.savedTag} role="status">
              저장됨
            </span>
          )}
        </div>
      </form>
      <CardNote>
        임시 이미지·이름입니다 — 실제 펫 자산이 확정되면 교체됩니다. 저장은 이 브라우저에만
        적용됩니다.
      </CardNote>
    </Card>
  );
}
