"use client";

import { useEffect, useId, useMemo, useState } from "react";

import styles from "@/components/auth.module.css";
import { fetchCrops, fetchDistricts, fetchRegions } from "@/lib/farm";
import type { Crop, District, Farm, FarmCreateInput, Region } from "@/types/farm";

/**
 * 밭 등록/수정 공용 폼. 지역은 시/군 → 법정동 말단(리가 있으면 리) 2단계로 받는다(PRD §4.2).
 * 말단까지 받는 이유는 흙토람 조회 단위가 말단이고, 면 평균과 리 실측이 최대 60점 갈리기
 * 때문이다(`docs/design/ri-level-district.md`).
 *
 * `farm`을 주면 수정 모드(초기값 채움 + 취소 버튼). 저장은 호출자가 한다 — 등록은 POST,
 * 수정은 PATCH이고 성공 후 이동/새로고침도 다르기 때문.
 *
 * 스타일은 auth.module.css(comUI 톤) — 위치/작물·시기/이름을 fieldset 단계로 묶는다.
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
  const [regionQuery, setRegionQuery] = useState("");
  const [bjdCode, setBjdCode] = useState(farm?.bjd_code ?? "");
  // 시/군과 달리 표기를 조립할 필요가 없다 — 밭 응답의 district_name이 곧 목록의 name이다.
  const [districtQuery, setDistrictQuery] = useState(farm?.district_name ?? "");
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
    const kept = regionId === String(farm?.region_id);
    setBjdCode((prev) => (kept ? prev : ""));
    setDistrictQuery((prev) => (kept ? prev : ""));
    fetchDistricts(Number(regionId))
      .then(setDistricts)
      .catch(() => setError("읍면동을 가져오지 못했어요."));
  }, [regionId, farm?.region_id]);

  // 256개 시/군을 select로 훑는 건 못 쓸 만큼 불편하다 → datalist로 입력하며 걸러낸다.
  // 표기에 시/도를 붙여야 동명 시/군(여러 곳의 '중구')이 구분되고 항목도 고유해진다.
  const regionLabel = (r: Region) => `${r.name} (${r.sido})`;
  const byLabel = useMemo(
    () => new Map(regions.map((r) => [regionLabel(r), r.id])),
    [regions],
  );

  // 리 단위 전환으로 시군당 선택지가 중앙값 69·최대 236개가 됐다 → 시/군과 같은 datalist 검색.
  const byDistrictName = useMemo(
    () => new Map(districts.map((d) => [d.name, d.bjd_code])),
    [districts],
  );

  // 수정 모드: 지역 목록이 도착한 뒤에야 기존 밭의 표기를 채울 수 있다.
  useEffect(() => {
    if (farm === undefined) return;
    const current = regions.find((r) => r.id === farm.region_id);
    if (current) setRegionQuery(regionLabel(current));
  }, [regions, farm?.region_id]);

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
      <fieldset className={styles.step}>
        <legend className={styles.stepLegend}>1단계 · 밭 위치</legend>
        <div className={styles.field}>
          <label htmlFor={`${uid}-region`}>지역 (시/군)</label>
          <input
            id={`${uid}-region`}
            list={`${uid}-region-list`}
            value={regionQuery}
            onChange={(e) => {
              setRegionQuery(e.target.value);
              setRegionId(String(byLabel.get(e.target.value) ?? ""));
            }}
            placeholder="시/군 이름을 입력하세요 (예: 고창)"
            autoComplete="off"
            required
            aria-describedby={
              regionQuery !== "" && regionId === "" ? `${uid}-region-hint` : undefined
            }
          />
          <datalist id={`${uid}-region-list`}>
            {regions.map((r) => (
              <option key={r.id} value={regionLabel(r)} />
            ))}
          </datalist>
          {/* 목록에 없는 글자를 남겨두면 등록 버튼이 왜 안 눌리는지 알 수 없다. */}
          {regionQuery !== "" && regionId === "" && (
            <p id={`${uid}-region-hint`} className={styles.hint}>
              목록에서 시/군을 골라 주세요.
            </p>
          )}
        </div>

        <div className={styles.field}>
          <label htmlFor={`${uid}-district`}>읍/면/동·리</label>
          <input
            id={`${uid}-district`}
            list={`${uid}-district-list`}
            value={districtQuery}
            onChange={(e) => {
              setDistrictQuery(e.target.value);
              setBjdCode(byDistrictName.get(e.target.value) ?? "");
            }}
            disabled={regionId === ""}
            placeholder={
              regionId === "" ? "시/군을 먼저 선택" : "리 이름을 입력하세요 (예: 구암리)"
            }
            autoComplete="off"
            required
            aria-describedby={
              districtQuery !== "" && bjdCode === "" ? `${uid}-district-hint` : undefined
            }
          />
          <datalist id={`${uid}-district-list`}>
            {districts.map((d) => (
              <option key={d.bjd_code} value={d.name} />
            ))}
          </datalist>
          {districtQuery !== "" && bjdCode === "" && (
            <p id={`${uid}-district-hint`} className={styles.hint}>
              목록에서 읍/면/동·리를 골라 주세요.
            </p>
          )}
          <p className={styles.hint}>
            토양 데이터를 리 단위로 가져옵니다. 읍·면 평균보다 실제 밭에 가깝습니다.
          </p>
        </div>
      </fieldset>

      <fieldset className={styles.step}>
        <legend className={styles.stepLegend}>2단계 · 작물과 시기</legend>
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
      </fieldset>

      <fieldset className={styles.step}>
        <legend className={styles.stepLegend}>3단계 · 이름 붙이기</legend>
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
      </fieldset>

      {farm !== undefined && (
        <p className={styles.hint}>
          지역이나 작물을 바꾸면 토양 기준값을 새 위치·작물 기준으로 다시 조회합니다.
        </p>
      )}

      {error !== "" && <p className={styles.error}>{error}</p>}

      <button type="submit" className={styles.submit} disabled={!ready || busy}>
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
