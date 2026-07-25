"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import RequireAuth from "@/components/RequireAuth";
import styles from "@/components/farm.module.css";
import { createFarm, fetchCrops, fetchDistricts, fetchRegions } from "@/lib/farm";
import type { Crop, District, Region } from "@/types/farm";

/**
 * 밭 등록. 지역은 시/군 → 읍면동 2단계로 받는다(PRD §4.2).
 * 읍면동까지 받는 이유는 토양 기준값이 읍면동 단위로만 조회되고 시/군 안 편차가 크기 때문(§5).
 */
function OnboardingForm() {
  const router = useRouter();
  const [regions, setRegions] = useState<Region[]>([]);
  const [crops, setCrops] = useState<Crop[]>([]);
  const [districts, setDistricts] = useState<District[]>([]);

  const [regionId, setRegionId] = useState("");
  const [bjdCode, setBjdCode] = useState("");
  const [cropId, setCropId] = useState("");
  const [plantingDate, setPlantingDate] = useState("");
  const [label, setLabel] = useState("");

  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([fetchRegions(), fetchCrops()])
      .then(([r, c]) => {
        setRegions(r);
        setCrops(c);
      })
      .catch(() => setError("선택지를 가져오지 못했어요. 잠시 후 다시 시도해 주세요."));
  }, []);

  // 시/군을 고르면 그 시/군의 읍면동만 다시 불러온다. 시/군을 바꾸면 이전 선택은 무효.
  useEffect(() => {
    if (regionId === "") {
      setDistricts([]);
      return;
    }
    setBjdCode("");
    fetchDistricts(Number(regionId))
      .then(setDistricts)
      .catch(() => setError("읍면동을 가져오지 못했어요."));
  }, [regionId]);

  // 시/도별로 묶어 보여준다 — 동명 시/군(예: 여러 곳의 '중구')을 구분하려면 시/도가 필요하다.
  const grouped = useMemo(() => {
    const map = new Map<string, Region[]>();
    for (const r of regions) {
      const list = map.get(r.sido) ?? [];
      list.push(r);
      map.set(r.sido, list);
    }
    return [...map.entries()];
  }, [regions]);

  const ready = regionId !== "" && bjdCode !== "" && cropId !== "" && plantingDate !== "";

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!ready || busy) return;
    setError("");
    setBusy(true);
    try {
      await createFarm({
        region_id: Number(regionId),
        bjd_code: bjdCode,
        crop_id: Number(cropId),
        planting_date: plantingDate,
        label: label.trim() === "" ? undefined : label.trim(),
      });
      router.push("/dashboard");
    } catch {
      setError("밭을 등록하지 못했어요. 입력을 확인하고 다시 시도해 주세요.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className={styles.form} onSubmit={onSubmit}>
      <div className={styles.field}>
        <label htmlFor="region">지역 (시/군)</label>
        <select
          id="region"
          value={regionId}
          onChange={(e) => setRegionId(e.target.value)}
          required
        >
          <option value="">선택하세요</option>
          {grouped.map(([sido, list]) => (
            <optgroup key={sido} label={sido}>
              {list.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </div>

      <div className={styles.field}>
        <label htmlFor="district">읍/면/동</label>
        <select
          id="district"
          value={bjdCode}
          onChange={(e) => setBjdCode(e.target.value)}
          disabled={districts.length === 0}
          required
        >
          <option value="">{regionId === "" ? "시/군을 먼저 선택" : "선택하세요"}</option>
          {districts.map((d) => (
            <option key={d.bjd_code} value={d.bjd_code}>
              {d.name}
            </option>
          ))}
        </select>
        <p className={styles.hint}>
          토양 데이터를 읍/면/동 단위로 가져옵니다. 시/군 평균보다 실제 밭에 가깝습니다.
        </p>
      </div>

      <div className={styles.field}>
        <label htmlFor="crop">작물</label>
        <select id="crop" value={cropId} onChange={(e) => setCropId(e.target.value)} required>
          <option value="">선택하세요</option>
          {crops.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.field}>
        <label htmlFor="planting">파종/정식일</label>
        <input
          id="planting"
          type="date"
          value={plantingDate}
          onChange={(e) => setPlantingDate(e.target.value)}
          required
        />
      </div>

      <div className={styles.field}>
        <label htmlFor="label">밭 이름 (선택)</label>
        <input
          id="label"
          type="text"
          maxLength={50}
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="예: 집 앞 사과밭"
        />
      </div>

      {error !== "" && <p className={styles.error}>{error}</p>}

      <button type="submit" disabled={!ready || busy}>
        {busy ? "등록 중…" : "밭 등록하기"}
      </button>
    </form>
  );
}

export default function OnboardingPage() {
  return (
    <main className={styles.page}>
      <div className={styles.inner}>
        <h1 className={styles.h1}>밭 등록</h1>
        <p className={styles.sub}>
          지역과 작물을 등록하면 그 땅의 토양·기후로 적합도를 계산합니다.
        </p>
        <RequireAuth>
          <OnboardingForm />
        </RequireAuth>
      </div>
    </main>
  );
}
