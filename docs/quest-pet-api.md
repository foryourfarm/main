# 펫 · 레벨 · 데일리 퀘스트 API (FE 연동 계약)

> 명세: `PRD.md` §14.5 · 구현: `app/api/quests.py`, `app/services/quest_service.py` · 마이그레이션 `0036`
> 이 문서만 보고 FE가 연동할 수 있어야 한다(CLAUDE.md §3-7).

## 0. 한 줄 요약

퀘스트 완료 로그만 저장하고 **경험치·레벨·펫 단계는 전부 파생 계산**한다. 세 엔드포인트가 **같은 응답**을 돌려주므로 FE는 무엇을 호출하든 받은 상태로 화면을 통째로 갈아끼우면 된다(재조회 없음).

**이 기능은 농사 판단에 개입하지 않는다.** 적합도·행동추천·위험판정은 레벨을 모르고, 레벨이 잠그는 기능도 없다.

## 1. 공통 응답 (`QuestProgress`)

```json
{
  "success": true,
  "data": {
    "level": 3,
    "exp": 240,
    "exp_into_level": 40,        // 현재 레벨 안에서 쌓은 양 → 진행바는 40/100
    "exp_per_level": 100,
    "pet": { "code": "sprout", "name": "새싹이", "emoji": "🌱", "stage_label": "새싹" },
    "pets": [                    // 고를 수 있는 전체 목록(FE가 카탈로그를 들지 않는다)
      { "code": "sprout", "name": "새싹이", "emoji": "🌱" },
      { "code": "pup",    "name": "흙강아지", "emoji": "🐣" }
    ],
    "quests": [
      { "code": "view_short", "label": "오늘 단기 탭 확인하기", "exp": 10, "is_done": true },
      { "code": "view_long",  "label": "장기 탭 확인하기",     "exp": 10, "is_done": false },
      { "code": "ask_chat",   "label": "텃밭이에게 질문하기",   "exp": 20, "is_done": false }
    ]
  },
  "error": null
}
```

- `pets[].emoji`는 **현재 레벨 기준** 외형이다 — "지금 바꾸면 이렇게 보인다"가 그대로 보인다.
- 퀘스트 목록·경험치 값·레벨 곡선은 서버가 정한다. FE에 하드코딩하지 말 것(퀘스트 코드 상수만 `types/quest.ts`).

## 2. 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/api/v1/quests/today` | 오늘 상태 조회 |
| POST | `/api/v1/quests/{quest_code}` | 퀘스트 완료(**멱등**) |
| PUT | `/api/v1/pet` | 펫 교체 — body `{"code": "pup"}` |

**인증**: 셋 다 `Authorization: Bearer <access>` 필수(없으면 401). 게스트에겐 이 기능이 없다.

**에러**

| 상황 | 상태 | code |
|---|---|---|
| 없는 퀘스트 코드 | 404 | `QUEST_NOT_FOUND` |
| 없는 펫 코드 | 400 | `PET_NOT_FOUND` |
| 미인증 | 401 | `UNAUTHORIZED` |

## 3. 퀘스트 발화 지점 (FE 할 일)

| code | 언제 호출 | 구현 위치 |
|---|---|---|
| `view_short` | 밭 상세에서 단기 탭이 보일 때 | `app/farm/[farmId]/page.tsx` — `tab` effect |
| `view_long` | 장기 탭이 보일 때 | 같은 곳 |
| `ask_chat` | 챗봇 답변이 **정상 수신 완료**된 뒤 | `components/ChatPanel.tsx` — `send()` |

- 완료 호출은 **멱등**이다. 탭을 오가며 여러 번 불려도 하루 한 번만 적립된다(DB UNIQUE 제약).
- `ask_chat`은 답변이 끝난 뒤에만 쏜다 — 오류로 끝난 시도까지 세면 "질문했다"가 거짓이 된다.
- 완료 호출 실패는 **조용히 무시**한다(`lib/quest.ts`의 `completeQuest`). 넛지 장치가 본 기능을 막으면 안 된다.

## 4. 알아둘 한계

- **완료 판정은 클라이언트 신뢰다.** 유저가 직접 POST를 호출하면 탭을 안 보고도 채울 수 있다. 보상이 없는 넛지 장치라 서버 열람 검증을 넣지 않았다(`PRD.md` §14.5). 보상이 생기면 서버 이벤트 기반으로 승격할 것.
- **날짜 경계는 서버 로컬 시간.** 유저 타임존을 받지 않으므로 자정은 서버 기준으로 갈린다.
- **펫 외형은 이모지(임시).** 일러스트가 나오면 `PET_STAGES`의 `emoji`를 이미지 경로로 갈아끼우면 되고, 응답 필드명은 그대로 둔다.
- 퀘스트 카탈로그가 개편돼 사라진 코드가 로그에 남아도 조회는 죽지 않는다(0점 처리).
