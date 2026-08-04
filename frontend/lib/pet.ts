/**
 * 펫 표시 자산. **펫의 진실은 서버다** — 이름·단계·레벨은 `QuestProgress.pet`이 정한다
 * (docs/quest-pet-api.md). 이 파일은 서버가 줄 수 없는 것, 즉 단계별 일러스트 경로만 든다.
 *
 * 캐릭터는 제비 한 마리(텃밭이)로 통일했다 — 펫 선택이 없으므로 키는 **펫 코드가 아니라
 * 레벨 단계 코드**다. 단계 코드의 출처는 백엔드 `PET_STAGES`(quest_service.py)이고,
 * 코드와 파일명이 어긋나면 그림이 조용히 안 나오므로 backend/tests/test_quest_progress.py가
 * 파일 존재까지 검증한다.
 */

/** 단계 코드 → 일러스트. 원본은 320x192(5:3) 투명 PNG — 프레임 비율도 5:3으로 맞춘다. */
const STAGE_IMAGE: Record<string, string> = {
  egg: "/assets/pet/egg.png",
  chick: "/assets/pet/chick.png",
  fledgling: "/assets/pet/fledgling.png",
  swallow: "/assets/pet/swallow.png",
};

/** 이 단계의 일러스트 경로. 모르는 코드면 null — 호출자가 서버 emoji로 대체한다. */
export function petImage(stageCode: string | undefined): string | null {
  if (stageCode === undefined) return null;
  return STAGE_IMAGE[stageCode] ?? null;
}

/**
 * 진행도를 아직(또는 끝내) 모를 때 쓰는 중립 표시값.
 *
 * **게스트용이 아니다.** 상담은 로그인 필수라 게스트는 챗 화면에도, 우하단 도크에도 닿지
 * 않는다(`app/chat/page.tsx`의 RequireAuth, `ChatDock`의 `hidden`). 여기가 걸리는 건
 * **로그인은 됐지만 `GET /quests/today`가 아직 안 왔거나 실패한** 구간이다.
 *
 * **레벨·단계는 붙이지 않는다** — 없는 진행도를 암시하면 거짓이 된다. 그림은 다 자란 제비를
 * 쓴다: 이 자리엔 레벨 표기가 없어 진행도 주장이 되지 않고, 우하단 런처와 같은 그림이라
 * 로드되는 순간 캐릭터가 바뀐 것처럼 보이지 않는다.
 */
export const PET_FALLBACK = {
  name: "텃밭이",
  line: "당신의 밭에서 함께 일하는 이웃",
  image: STAGE_IMAGE.swallow,
} as const;

/** 우하단 상담 버튼 아이콘. 앱 아이콘이라 레벨을 기다리지 않는다.
 *  ponytail: 단계에 따라 자라게 하려면 ChatDock이 퀘스트 진행도를 조회해야 한다 — 다음 작업.
 *  (도크는 로그인 유저만 보므로 레벨을 아는 것 자체는 가능하다.) */
export const LAUNCHER_ICON = STAGE_IMAGE.swallow;
