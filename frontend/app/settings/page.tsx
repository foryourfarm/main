"use client";

import { Database, Pencil, Plus, Sprout } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import FarmForm from "@/components/FarmForm";
import Loading from "@/components/Loading";
import RequireAuth from "@/components/RequireAuth";
import styles from "@/components/auth.module.css";
import { Card, CardHeader } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import { deleteFarm, fetchFarms, updateFarm } from "@/lib/farm";
import type { Farm } from "@/types/farm";

/** 데이터 출처 — 화면에 쓰는 값의 근거를 숨기지 않는다(CLAUDE.md §4 정직한 한계 표기, 설계 §1.6). */
const SOURCES = [
  "기상(단기): 기상청 단기예보 — 실시간 조회 후 캐시",
  // 기상청 "평년값"(30년, 1991~2020)이 아니다 — 우리 값은 5년 관측 평균이라 그렇게 적으면
  // 거짓이 된다. 백엔드 CLIMATOLOGY_PERIOD_LIMITATION과 같은 사실을 말해야 한다.
  "기상(장기): 최근 5년(2021~2025) 관측 평균 + 기상청 3개월 전망 — 기상청 30년 평년값이 아니며 그보다 약 1℃ 따뜻합니다. 관측지점 미보유 지역은 최근접 지역 값 대체",
  "토양: 농촌진흥청 흙토람 토양검정 — 읍/면/동 표본 평균(내 밭 실측이 아님)",
  "작물 기준: 농사로·문헌 기반 생육 지침 시드",
];

function FarmRow({ farm, onChanged }: { farm: Farm; onChanged: () => void }) {
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState("");

  async function remove() {
    // 되돌릴 수 없는 삭제 — 브라우저 기본 확인창으로 한 번 막는다.
    if (!window.confirm(`'${farm.label ?? farm.crop_name ?? "이 밭"}'을 삭제할까요?\n밭에 딸린 토양 상태·기록도 함께 사라지고 되돌릴 수 없습니다.`)) {
      return;
    }
    try {
      await deleteFarm(farm.id);
      onChanged();
    } catch {
      setError("삭제하지 못했어요. 잠시 후 다시 시도해 주세요.");
    }
  }

  return (
    <Card>
      <div className={styles.rowTop}>
        <div>
          <div className={styles.farmName}>
            {farm.label ?? farm.crop_name ?? "이름 없는 밭"}
          </div>
          <div className={styles.farmMeta}>
            {farm.crop_name ?? "작물 미지정"} · {farm.region_name ?? "지역 미지정"}{" "}
            {farm.district_name ?? "읍면동 미지정"}
          </div>
          <div className={styles.farmMeta}>파종/정식일 {farm.planting_date}</div>
        </div>
        <div className={styles.rowActions}>
          <button type="button" className={styles.secondaryBtn} onClick={() => setEditing((v) => !v)}>
            {editing ? "닫기" : "수정"}
          </button>
          <button type="button" className={styles.dangerBtn} onClick={remove}>
            삭제
          </button>
        </div>
      </div>

      <div className={styles.rowBody}>
        {farm.bjd_code === null && (
          <p className={styles.hint}>
            읍/면/동 정보가 없는 밭입니다. 수정에서 다시 선택하면 토양 데이터가 정확해집니다.
          </p>
        )}
        {farm.soil_source !== null && <p className={styles.hint}>토양 출처: {farm.soil_source}</p>}
        {error !== "" && <p className={styles.error}>{error}</p>}

        {editing && (
          <FarmForm
            farm={farm}
            submitLabel="저장"
            onCancel={() => setEditing(false)}
            onSubmit={async (input) => {
              await updateFarm(farm.id, input);
              setEditing(false);
              onChanged();
            }}
          />
        )}
      </div>
    </Card>
  );
}

function SettingsBody() {
  const [farms, setFarms] = useState<Farm[] | null>(null);
  const [error, setError] = useState("");

  function reload() {
    fetchFarms()
      .then(setFarms)
      .catch(() => setError("밭 정보를 가져오지 못했어요. 잠시 후 다시 시도해 주세요."));
  }

  useEffect(reload, []);

  if (error !== "") return <p className={styles.error}>{error}</p>;
  if (farms === null) return <Loading />;

  return (
    <>
      {farms.length === 0 ? (
        <EmptyState
          icon={<Sprout size={28} />}
          title="등록된 밭이 없습니다"
          hint="첫 밭을 등록하면 그 땅의 토양·기후로 적합도를 계산합니다."
          action={
            <Link href="/onboarding" className={styles.ctaLink}>
              첫 밭 등록하기
            </Link>
          }
        />
      ) : (
        <div className={styles.cards}>
          {farms.map((f) => (
            <FarmRow key={f.id} farm={f} onChanged={reload} />
          ))}
        </div>
      )}
      <p>
        <Link href="/onboarding" className={styles.addLink}>
          <Plus size={18} aria-hidden="true" />밭 추가 등록
        </Link>
      </p>
    </>
  );
}

export default function SettingsPage() {
  return (
    // layout.tsx의 <main className="appMain">이 이미 main 랜드마크 — 중첩 main 금지.
    <div className="wrap">
      <h1 className={styles.title}>설정</h1>
      <p className={styles.lead}>등록한 밭의 지역·작물·파종일을 고치거나 삭제할 수 있습니다.</p>
      <RequireAuth>
        {/* 이름 바꾸는 화면은 카카오 신규 유저가 자동으로 거쳐가는 그 화면을 그대로 쓴다 —
            폼을 두 곳에 두면 제약(1~50자)이 갈린다. 돌아올 곳만 알려준다. */}
        <p>
          <Link href="/onboarding/nickname?next=/settings" className={styles.addLink}>
            <Pencil size={18} aria-hidden="true" />내 이름 바꾸기
          </Link>
        </p>
        <SettingsBody />
      </RequireAuth>

      <Card className={styles.sourcesCard}>
        <CardHeader icon={<Database size={16} />} title="데이터 출처" />
        <ul className={styles.sourceList}>
          {SOURCES.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
