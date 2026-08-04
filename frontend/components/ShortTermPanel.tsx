"use client";

import { useCallback, useEffect, useState } from "react";

import DayDetailModal from "@/components/DayDetailModal";
import { gradeTone } from "@/components/GradeBadge";
import Limitations from "@/components/Limitations";
import Loading from "@/components/Loading";
import styles from "@/components/farm.module.css";
import { fetchAdvice, fetchShortTerm } from "@/lib/farm";
import type { DailyAdvice, FarmShortTerm, PersistentRisk, ShortTermDay } from "@/types/farm";
import {
  describeRiskFlag,
  formatBaseAt,
  formatDayLabel,
  stageLabel,
  statusLabel,
} from "@/types/farm";

/**
 * 지속 위험 배너. 이 탭의 존재 이유 — A씨는 "봄철 야간저온 3일"을 미리 몰라 활착에 실패했다.
 * 그래서 날짜별 카드보다 위에, 가장 먼저 보이게 둔다(PRD 철학 3 선제적 안내).
 */
function RiskBanner({ risks }: { risks: PersistentRisk[] }) {
  if (risks.length === 0) {
    return (
      <p className={styles.calmBanner}>
        이번 예보 기간에 연속되는 기상 위험은 없습니다.
      </p>
    );
  }
  return (
    <section className={styles.alertBanner}>
      <p className={styles.alertTitle}>미리 대비하세요</p>
      <ul className={styles.alertList}>
        {risks.map((r) => (
          <li key={r.flag}>
            <strong>{describeRiskFlag(r.flag)}</strong> — {r.days}일 연속 예상
            <span className={styles.alertDates}>
              {" "}
              ({r.dates.map(formatDayLabel).join(", ")})
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

/**
 * 오늘의 행동추천. 위험 배너보다 위에 둔다 — 배너는 "무엇이 위험한가"고 이건 "그래서 뭘
 * 하라"라서, 초보자에게는 후자가 먼저 읽혀야 한다(PRD 철학 2 눈높이 번역).
 *
 * **탭과 따로 부른다.** 한 응답에 묶었더니 LLM 동기 재시도가 탭 전체를 막아 화면이
 * 12초간 "불러오는 중…"으로 비는 것을 실측했다. 여기서만 기다리게 한다.
 *
 * is_llm=false를 숨기지 않는다(§18-4). 규칙 문구도 내용은 정확하지만 "다듬어진 것"처럼
 * 보이게 하면 품질 기대가 어긋난다. 토양 문단은 항상 규칙 문구라 태그 대상이 아니다.
 */
function AdviceCard({ farmId }: { farmId: number }) {
  const [advice, setAdvice] = useState<DailyAdvice | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    fetchAdvice(farmId).then(setAdvice).catch(() => setFailed(true));
  }, [farmId]);

  // 추천 실패가 탭을 망치지 않는다 — 이 블록만 빠지고 예보·위험은 그대로 보인다(§18-5).
  if (failed) return null;

  return (
    <section className={styles.adviceCard} aria-label="오늘의 행동추천">
      <p className={styles.adviceTitle}>
        오늘 이렇게 하세요
        {advice && !advice.is_llm && <span className={styles.adviceTag}>자동 생성 문구</span>}
      </p>
      {advice === null ? (
        <p className={styles.adviceLoading}>행동 안내를 준비하고 있어요…</p>
      ) : (
        <>
          <p className={styles.adviceText}>{advice.text}</p>
          {advice.soil_text && (
            // 매일 바뀌는 기상과 성격이 달라 문단을 나눈다 — 상시 토양 상태다.
            <p className={styles.adviceSoil}>{advice.soil_text}</p>
          )}
        </>
      )}
    </section>
  );
}

/**
 * 날짜별 요약 카드. 누르면 하루 기온 곡선과 점수 근거를 모달로 연다.
 *
 * **"낮 기온"이 아니라 "낮 최고기온"(`temp_max`)을 보여준다.** 종전엔 일평균(`temp_avg`)을
 * "낮 기온"이라 띄웠는데 실측에서 일평균 31.3℃ vs 일최고 38℃로 6.7℃ 벌어졌다. 점수는 여전히
 * 일평균으로 매기므로(채점 무변경) 두 값이 다르다는 설명은 모달이 맡는다.
 */
function DayCard({ day, onOpen }: { day: ShortTermDay; onOpen: () => void }) {
  const tone = gradeTone(day.grade);
  // 결측(missing)은 위험이 아니라 데이터 없음이므로 카드에 경고로 띄우지 않는다.
  const risks = day.risk_flags.filter((f) => f.endsWith(":outside_allowed"));
  return (
    // 카드 전체가 눌리지만 **카드 자체를 button으로 만들지 않는다** — button의 콘텐츠 모델은
    // phrasing content라 안에 dl·ul·p를 넣으면 유효하지 않은 HTML이 된다. 대신 아래 버튼
    // 하나만 두고 그 클릭영역을 ::after로 카드 전체에 넓힌다(표준 카드 패턴). 포커스 가능한
    // 요소가 하나뿐이라 키보드 탐색도 단순하다(§8).
    <div className={styles.dayCard}>
      <div className={styles.dayHead}>
        <span className={styles.dayDate}>{formatDayLabel(day.target_date)}</span>
        <span className={`${styles.cellGrade} ${tone}`}>
          {day.grade ?? statusLabel(day.status)}
        </span>
      </div>
      <div className={`${styles.cellScore} ${tone}`}>{day.score ?? "—"}</div>
      <div className={styles.dayStage}>{stageLabel(day.growth_stage, day.status)}</div>
      <dl className={styles.metrics}>
        <div>
          <dt>낮 최고기온</dt>
          <dd>{day.temp_max ?? "—"}℃</dd>
        </div>
        <div>
          <dt>야간 최저</dt>
          <dd>{day.temp_night_min ?? "—"}℃</dd>
        </div>
        <div>
          <dt>강수</dt>
          <dd>{day.rainfall ?? "—"}mm</dd>
        </div>
      </dl>
      {/* 이 날짜 집계가 부분 표본이라는 사실을 카드에서 바로 알린다 — 첫날 값이 왜 튀는지
          모르면 유저는 그 경고를 실제 위험으로 받아들인다(§18-4). */}
      {day.is_imputed && <p className={styles.partialTag}>일부 시간대만 반영</p>}
      {risks.length > 0 && (
        <ul className={styles.dayRisks}>
          {risks.map((f) => (
            <li key={f}>{describeRiskFlag(f)}</li>
          ))}
        </ul>
      )}
      <button
        type="button"
        className={styles.dayMore}
        onClick={onOpen}
        aria-label={`${formatDayLabel(day.target_date)} 기온 상세 보기`}
      >
        기온 변화 보기
      </button>
    </div>
  );
}

export default function ShortTermPanel({ farmId }: { farmId: number }) {
  const [data, setData] = useState<FarmShortTerm | null>(null);
  const [error, setError] = useState<string | null>(null);
  // 어느 날짜 상세를 열었는지. 날짜 상세는 URL을 갖지 않아(같은 탭 안의 보조 정보)
  // intercepting route가 아니라 지역 상태로 둔다.
  const [openDate, setOpenDate] = useState<string | null>(null);
  const closeDetail = useCallback(() => setOpenDate(null), []);

  useEffect(() => {
    fetchShortTerm(farmId)
      .then(setData)
      .catch(() => setError("예보를 가져오지 못했어요. 잠시 후 다시 시도해 주세요."));
  }, [farmId]);

  if (error !== null) return <p className={styles.error}>{error}</p>;
  if (data === null) return <Loading />;

  if (data.days.length === 0) {
    // 격자 매핑·예보 조회가 안 된 경우. 조용히 0점 내지 않는다는 백엔드 방침과 맞춘다.
    return <p className={styles.notice}>이 지역의 예보를 아직 가져오지 못했습니다.</p>;
  }

  return (
    <>
      <p className={styles.sub}>
        {formatBaseAt(data.base_at)} · {data.label}
        {data.is_stale && <span className={styles.staleTag}>최신 아님</span>}
      </p>
      <AdviceCard farmId={farmId} />
      <RiskBanner risks={data.persistent_risks} />
      <div className={styles.dayGrid}>
        {/* FrontEnd.md §6-14: API가 최대 4일(오늘+3)을 주더라도 화면에는 앞의 3개만 노출한다. */}
        {data.days.slice(0, 3).map((d) => (
          <DayCard key={d.target_date} day={d} onOpen={() => setOpenDate(d.target_date)} />
        ))}
      </div>
      <Limitations items={data.limitations} />
      {openDate !== null && (() => {
        const day = data.days.find((d) => d.target_date === openDate);
        // 재조회로 날짜 목록이 바뀌면 열려 있던 날짜가 사라질 수 있다 — 그때 렌더를 시도하면
        // undefined를 넘겨 터진다.
        if (!day) return null;
        return <DayDetailModal day={day} baseAt={data.base_at} onClose={closeDetail} />;
      })()}
    </>
  );
}
