"use client";

import { CalendarCheck, CheckSquare, CircleSlash, History, NotebookPen, Plus, Scale, Sprout, Square, TreeDeciduous } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import GradeBadge from "@/components/GradeBadge";
import Limitations from "@/components/Limitations";
import Loading from "@/components/Loading";
import RequireAuth from "@/components/RequireAuth";
import { Card, CardHeader, CardNote } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import Gauge from "@/components/ui/Gauge";
import { useAuth } from "@/lib/auth-context";
import { fetchDashboard } from "@/lib/farm";
import { petImage } from "@/lib/pet";
import { fetchQuestProgress } from "@/lib/quest";
import { statusLabel } from "@/types/farm";
import type { DashboardCard, DashboardResponse, Grade } from "@/types/farm";
import type { QuestProgress } from "@/types/quest";

import styles from "./dashboard.module.css";

/** 게이지 원호색 — 등급 토큰(globals.css --grade-*). 색만으로 구분하지 않고 GradeBadge 라벨 병기(§10). */
const GRADE_COLOR: Record<Grade, string> = {
  S: "var(--grade-s)",
  A: "var(--grade-a)",
  B: "var(--grade-b)",
  C: "var(--grade-c)",
};

/**
 * 오늘의 할 일 = 데일리 퀘스트(comUI .todo 배치). 완료는 발화 지점(탭 열람·질문)이 자동으로
 * 올리므로 여기서는 상태만 보여준다 — 동작하는 척하는 체크박스를 만들지 않는다(§1-8).
 * 조회 실패(퀘스트 미지원 백엔드 포함)면 종전 "준비 중" 표시로 폴백한다.
 */
function QuestCard() {
  const [progress, setProgress] = useState<QuestProgress | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    fetchQuestProgress()
      .then(setProgress)
      .catch(() => setFailed(true));
  }, []);

  const done = progress === null ? 0 : progress.quests.filter((q) => q.is_done).length;
  const ratio =
    progress === null
      ? 0
      : Math.min(100, Math.round((progress.exp_into_level / progress.exp_per_level) * 100));

  return (
    <Card span={5}>
      <CardHeader
        icon={<CalendarCheck size={17} />}
        title="오늘의 할 일"
        tag={progress === null ? "데일리 퀘스트" : `${done}/${progress.quests.length} 완료`}
      />
      {progress === null ? (
        <EmptyState
          icon={<CalendarCheck size={26} />}
          title={failed ? "데일리 퀘스트가 준비 중이에요" : "오늘 퀘스트를 불러오는 중…"}
          hint="오늘 밭에서 할 행동이 체크리스트로 제공될 예정입니다."
        />
      ) : (
        <>
          <div className={styles.questLevel}>
            {/* 펫 표시 규칙은 챗 헤더와 같다 — 일러스트가 있으면 이미지, 없으면 서버 emoji. */}
            <span aria-hidden="true">
              {petImage(progress.pet.code) !== null ? (
                <Image
                  src={petImage(progress.pet.code) as string}
                  alt=""
                  width={22}
                  height={22}
                  className={styles.questPetIcon}
                />
              ) : (
                progress.pet.emoji
              )}
            </span>
            <b>
              Lv.{progress.level} {progress.pet.name}
            </b>
            {/* 색만으로 진행도를 알리지 않는다 — 숫자 병기(§10). */}
            <span className={styles.questExp}>
              {progress.exp_into_level}/{progress.exp_per_level} exp
            </span>
          </div>
          <div
            className={styles.expBar}
            role="progressbar"
            aria-valuenow={progress.exp_into_level}
            aria-valuemin={0}
            aria-valuemax={progress.exp_per_level}
            aria-label={`다음 레벨까지 ${progress.exp_per_level - progress.exp_into_level} 경험치`}
          >
            <div className={styles.expFill} style={{ width: `${ratio}%` }} />
          </div>
          <ul className={styles.questTodo}>
            {progress.quests.map((q) => (
              <li key={q.code} className={q.is_done ? styles.questDone : undefined}>
                {q.is_done ? (
                  <CheckSquare size={18} aria-hidden="true" className={styles.questDoneIcon} />
                ) : (
                  <Square size={18} aria-hidden="true" />
                )}
                <span className={styles.questLabel}>{q.label}</span>
                <span className={styles.questExp}>{q.is_done ? "완료" : `+${q.exp}`}</span>
              </li>
            ))}
          </ul>
          <CardNote>단기·장기 탭 확인, 질문하기로 자동 완료돼요. 경험치로 펫이 자랍니다.</CardNote>
        </>
      )}
    </Card>
  );
}

/** comUI .card.field — 작물 아이콘 + 이름·지역 + 도넛 게이지. 카드 전체가 /farm/{id} 링크
 *  (intercepting modal 라우팅 대상이라 경로를 바꾸지 않는다). span은 부모가 7/5 교대로 준다. */
function FarmCard({ card, span }: { card: DashboardCard; span: 5 | 7 }) {
  const CropIcon = card.crop_type === "orchard" ? TreeDeciduous : Sprout;
  return (
    <Link href={`/farm/${card.farm_id}`} className={`sp${span} ${styles.fieldLink}`}>
      <article className={styles.field}>
        <div className={styles.fieldTop}>
          <span className={styles.cropBadge} aria-hidden="true">
            <CropIcon size={26} />
          </span>
          <div>
            <h2 className={styles.fieldName}>{card.label}</h2>
            <div className={styles.fieldLoc}>
              {card.crop_name ?? "작물 미지정"}
              <span className={styles.sep} aria-hidden="true">
                ·
              </span>
              {card.region_name ?? "지역 미지정"}
            </div>
          </div>
          {card.score !== null && (
            <div className={styles.gaugeWrap}>
              <Gauge
                value={card.score}
                color={card.grade !== null ? GRADE_COLOR[card.grade] : "var(--muted)"}
              />
            </div>
          )}
        </div>
        {card.score === null && (
          <div className={styles.nodata}>
            <CircleSlash size={20} aria-hidden="true" />
            {statusLabel(card.status) || "점수 없음"}
          </div>
        )}
        <div className={styles.fieldFoot}>
          <GradeBadge grade={card.grade} status={card.status} />
          <span className={styles.stage}>{card.growth_stage_label ?? "—"}</span>
        </div>
      </article>
    </Link>
  );
}

/** comUI .hero — 실데이터 칩만(오늘 날짜·닉네임·밭 수·첫 밭 점수).
 *  시안의 날씨·강수·EC 수치는 대시보드 계약에 없어 만들지 않는다(FrontEnd.md §1-5). */
function Hero({ nickname, data }: { nickname: string; data: DashboardResponse }) {
  // 클라이언트 렌더 전용(데이터 로드 후에만 그려짐)이라 hydration 불일치 없음.
  const today = new Intl.DateTimeFormat("ko-KR", { dateStyle: "full" }).format(new Date());
  const first = data.farms[0];
  return (
    <section className={styles.hero}>
      <div className={styles.kicker}>{today}</div>
      <h1 className={styles.heroTitle}>
        {nickname !== "" && (
          <>
            <em>{nickname}</em>님,{" "}
          </>
        )}
        오늘의 밭을 확인해 보세요.
      </h1>
      <p className={styles.heroSub}>{data.as_of} 기준으로 계산한 밭 적합도입니다.</p>
      <div className={styles.heroStrip}>
        <span className={styles.mini}>
          등록된 밭 <b className="num">{data.farms.length}</b>곳
        </span>
        <span className={styles.mini}>
          {first.label}{" "}
          {first.score !== null ? (
            <>
              <b className="num">{first.score}</b>점
            </>
          ) : (
            statusLabel(first.status) || "점수 없음"
          )}
        </span>
      </div>
    </section>
  );
}

function DashboardBody() {
  const { user } = useAuth(); // 히어로 인사말에 쓰는 닉네임
  const router = useRouter();
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDashboard()
      .then(setData)
      .catch(() => setError("밭 정보를 가져오지 못했어요. 잠시 후 다시 시도해 주세요."));
  }, []);

  // 밭이 없으면 대시보드는 보여줄 것이 없다 — 링크를 누르게 하지 않고 등록 화면으로 바로 보낸다
  // (가입 직후가 이 경우다). `replace`라 뒤로가기가 빈 대시보드로 튕기지 않는다.
  useEffect(() => {
    if (data !== null && data.farms.length === 0) router.replace("/onboarding");
  }, [data, router]);

  if (error !== null) return <p className={styles.error}>{error}</p>;
  if (data === null) return <Loading />;

  if (data.farms.length === 0) {
    // 위 effect가 곧 /onboarding으로 이동시킨다. 그 사이 "밭이 없습니다"가 번쩍이지 않게
    // 로딩을 유지한다 — 재편 때 두었던 빈 상태 카드는 이 흐름에서 스쳐 지나갈 뿐이라 뺀다.
    return <Loading />;
  }

  const hasLimitations = data.farms.some((card) => card.limitations.length > 0);

  return (
    <>
      <Hero nickname={user?.nickname ?? ""} data={data} />
      <div className="bento">
        {data.farms.map((card, i) => (
          <FarmCard key={card.farm_id} card={card} span={i % 2 === 0 ? 7 : 5} />
        ))}

        {/* 오늘의 할 일 = 데일리 퀘스트(PRD §14.5, docs/quest-pet-api.md). 나머지는 §12-1 칸만. */}
        <QuestCard />
        <Card span={4}>
          <CardHeader icon={<NotebookPen size={17} />} title="행동 기록" tag="준비 중" />
          <EmptyState
            icon={<NotebookPen size={26} />}
            title="아직 준비 중인 기능이에요"
            hint="관수·적과 같은 행동을 기록하는 기능이 들어올 예정입니다."
          />
        </Card>

        {/* comUI .addfield — dashed 큰 카드. */}
        <Link href="/onboarding" className={`sp3 ${styles.addField}`}>
          <span>
            <span className={styles.addPlus} aria-hidden="true">
              <Plus size={26} />
            </span>
            밭 추가 등록
            <small>지역과 작물을 골라 등록합니다</small>
          </span>
        </Link>

        <Card span={5}>
          <CardHeader icon={<History size={17} />} title="최근 기록" tag="준비 중" />
          <EmptyState
            icon={<History size={26} />}
            title="아직 준비 중인 기능이에요"
            hint="밭에서 감지된 변화와 기록 이력이 시간순으로 쌓일 예정입니다."
          />
        </Card>

        {/* comUI "이 화면의 근거" 카드. 밭마다 한계가 다르다(예: 어떤 밭만 유기물이 채점 안 됨).
            하나로 합쳐 보여주면 그 사실이 어느 밭 얘기인지 사라져 다른 밭에도 적용되는 것처럼
            오독된다(§18-4) — 그래서 밭별 Limitations를 분리한 채 카드 안에 나열한다. */}
        {hasLimitations && (
          <Card span={7}>
            <CardHeader icon={<Scale size={17} />} title="이 화면의 근거" tag={`밭 ${data.farms.length}곳`} />
            {data.farms.map((card) => (
              <Limitations
                key={card.farm_id}
                label={`${card.crop_name ?? "작물 미지정"} · ${card.region_name ?? "지역 미지정"}`}
                items={card.limitations}
              />
            ))}
          </Card>
        )}
      </div>
    </>
  );
}

export default function DashboardPage() {
  return (
    <main className="wrap">
      <RequireAuth>
        <DashboardBody />
      </RequireAuth>
    </main>
  );
}
