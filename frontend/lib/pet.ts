/**
 * 펫 표시 자산. **펫의 진실은 서버다** — 이름·단계·레벨·교체는 `QuestProgress.pet`과
 * `PUT /api/v1/pet`이 정한다(docs/quest-pet-api.md). 이 파일은 서버가 줄 수 없는 것,
 * 즉 코드별 일러스트 경로만 들고 있다.
 *
 * 일러스트가 나오면 여기 경로만 채우면 된다 — 비어 있는 동안은 서버가 주는 emoji로
 * 표시되므로, 없는 그림을 있는 척하지 않는다(§18-4).
 */

/** 펫 코드 → 확정 일러스트 경로. 아직 자산이 없어 비어 있다. */
const PET_IMAGE: Record<string, string> = {
  // sprout: "/assets/pet/sprout.png",
  // pup: "/assets/pet/pup.png",
};

/** 이 펫의 일러스트 경로. 없으면 null — 호출자가 서버 emoji로 대체한다. */
export function petImage(code: string | undefined): string | null {
  if (code === undefined) return null;
  return PET_IMAGE[code] ?? null;
}

/**
 * 게스트·세션 복구 중 표시값. 펫은 로그인 사용자 기능이라(quest-pet-api.md §2) 서버 상태가
 * 없을 때 쓰는 중립 문구다. 레벨·단계는 붙이지 않는다 — 없는 진행도를 암시하면 거짓이 된다.
 */
export const GUEST_PET = {
  name: "텃밭이",
  line: "당신의 밭에서 함께 일하는 이웃",
} as const;

/** 우하단 상담 버튼 아이콘. 펫 단계와 무관한 앱 아이콘이라 서버 상태를 기다리지 않는다. */
export const LAUNCHER_ICON = "/assets/chatbot_icon.png";
