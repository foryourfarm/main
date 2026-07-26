"use client";

import { useEffect, useId, useMemo, useState } from "react";

import styles from "@/components/farm.module.css";
import { fetchCrops, fetchDistricts, fetchRegions } from "@/lib/farm";
import type { Crop, District, Farm, FarmCreateInput, Region } from "@/types/farm";

/**
 * 밭 등록/수정 공용 폼. 지역은 시/군 → 읍면동 2단계로 받는다(PRD §4.2).
 * 읍면동까지 받는 이유는 토양 기준값이 읍면동 단위로만 조회되고 시/군 안 편차가 크기 때문(§5).
 *
 * `farm`을 주면 수정 모드(초기값 채움 + 취소 버튼). 저장은 호출자가 한다 — 등록은 POST,
 * 수정은 PATCH이고 성공 후 이동/새로고침도 다르기 때문.
 */
export default function FarmForm({
  farm,
  onSubmit,
  onCancel,
  submitLabel,
}: {
  farm?: Farm;
  onSubmit: (input: FarmCreateInput) => Promise<void>;
  onCancel?: () => void;
  submitLabel: string;
}) {
  // 설정 화면은 여러 밭의 수정 폼이 동시에 열릴 수 있다 → id 충돌(label 연결 깨짐)을 막는다.
  const uid = useId();
  const [regions, setRegions] = useState<Region[]>([]);
  const [crops, setCrops] = useState<Crop[]>([]);
  const [districts, setDistricts] = useState<District[]>([]);

  const [regionId, setRegionId] = useState(farm ? String(farm.region_id) : "");
  const [bjdCode, setBjdCode] = useState(farm?.bjd_code ?? "");
  const [cropId, setCropId] = useState(farm ? String(farm.crop_id) : "");
  const [plantingDate, setPlantingDate] = useState(farm?.planting_date ?? "");
  const [label, setLabel] = useState(farm?.label ?? "");

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
  // 수정 모드 첫 렌더에서는 기존 읍면동을 지우지 않는다(초기값 유지).
  useEffect(() => {
    if (regionId === "") {
      setDistricts([]);
      return;
    }
    setBjdCode((prev) => (regionId === String(farm?.region_id) ? prev : ""));
    fetchDistricts(Number(regionId))
      .then(setDistricts)
      .catch(() => setError("읍면동을 가져오지 못했어요."));
  }, [regionId, farm?.region_id]);

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

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!ready || busy) return;
    setError("");
    setBusy(true);
    try {
      await onSubmit({
        region_id: Number(regionId),
        bjd_code: bjdCode,
        crop_id: Number(cropId),
        planting_date: plantingDate,
        label: label.trim() === "" ? undefined : label.trim(),
      });
    } catch {
      setError("저장하지 못했어요. 입력을 확인하고 다시 시도해 주세요.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      <div className={styles.field}>
        <label htmlFor={`${uid}-region`}>지역 (시/군)</label>
        <select id={`${uid}-region`} value={regionId} onChange={(e) => setRegionId(e.target.value)} required>
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
        <label htmlFor={`${uid}-district`}>읍/면/동</label>
        <select
          id={`${uid}-district`}
          value={bjdCode}
          onChange={(e) => setBjdCode(e.target.value)}
          disabled={districts.length === 0}
          required
        >
          <option value="">{regionId === "" ? "시/군을 먼저 선택" : "선택하세요"}</option>
          {/* 수정 모드에서 목록이 아직 안 왔을 때도 현재 값을 보여준다. */}
          {districts.length === 0 && bjdCode !== "" && (
            <option value={bjdCode}>{farm?.district_name ?? bjdCode}</option>
          )}
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
        <label htmlFor={`${uid}-crop`}>작물</label>
        <select id={`${uid}-crop`} value={cropId} onChange={(e) => setCropId(e.target.value)} required>
          <option value="">선택하세요</option>
          {crops.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.field}>
        <label htmlFor={`${uid}-planting`}>파종/정식일</label>
        <input
          id={`${uid}-planting`}
          type="date"
          value={plantingDate}
          onChange={(e) => setPlantingDate(e.target.value)}
          required
        />
      </div>

      <div className={styles.field}>
        <label htmlFor={`${uid}-label`}>밭 이름 (선택)</label>
        <input
          id={`${uid}-label`}
          type="text"
          maxLength={50}
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="예: 집 앞 사과밭"
        />
      </div>

      {farm !== undefined && (
        <p className={styles.hint}>
          지역이나 작물을 바꾸면 토양 기준값을 새 위치·작물 기준으로 다시 조회합니다.
        </p>
      )}

      {error !== "" && <p className={styles.error}>{error}</p>}

      <button type="submit" disabled={!ready || busy}>
        {busy ? "저장 중…" : submitLabel}
      </button>
      {onCancel !== undefined && (
        <button type="button" className={styles.secondaryBtn} onClick={onCancel} disabled={busy}>
          취소
        </button>
      )}
    </form>
  );
}
