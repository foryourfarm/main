# 펫 · 레벨 · 데일리 퀘스트 API (FE 연동 계약)

> 명세: `PRD.md` §14.5 · 구현: `app/api/quests.py`, `app/services/quest_service.py` · 마이그레이션 `0036`
> 이 문서만 보고 FE가 연동할 수 있어야 한다(CLAUDE.md §3-7).

## 0. 한 줄 요약

퀘스트 완료 로그만 저장하고 **경험치·레벨·펫 단계는 전부 파생 계산**한다. 두 엔드포인트가 **같은 응답**을 돌려주므로 FE는 무엇을 호출하든 받은 상태로 화면을 통째로 갈아끼우면 된다(재조회 없음).

**이 기능은 농사 판단에 개입하지 않는다.** 적합도·행동추천·위험판정은 레벨을 모르고, 레벨이 잠그는 기능도 없다.

> **변경(캐릭터 확정)** — 캐릭터는 **제비 한 마리 "텃밭이"**로 통일했다. 그래서
> ① `PUT /api/v1/pet`과 `pets` 배열이 **삭제**됐고, ② `pet.code`(펫 코드)가 **`pet.stage_code`**(레벨 단계 코드)로 바뀌었다. 종전 응답을 파싱하던 FE 코드는 이 두 곳을 고쳐야 한다.

## 1. 공통 응답 (`QuestProgress`)

```json
{
  "success": true,
  "data": {
    "level": 3,
    "exp": 240,
    "exp_into_level": 40,        // 현재 레벨 안에서 쌓은 양 → 진행바는 40/100
    "exp_per_level": 100,
    "pet": { "stage_code": "chick", "name": "텃밭이", "emoji": "🐣", "stage_label": "아기 제비" },
    "quests": [
      { "code": "view_short", "label": "오늘 단기 탭 확인하기", "exp": 10, "is_done": true },
      { "code": "view_long",  "label": "장기 탭 확인하기",     "exp": 10, "is_done": false },
      { "code": "ask_chat",   "label": "텃밭이에게 질문하기",   "exp": 20, "is_done": false }
    ]
  },
  "error": null
}
```

- `pet.name`은 항상 **"텃밭이"**다. 레벨이 올라도 이름은 그대로고 `stage_label`·`stage_code`만 바뀐다.
- 퀘스트 목록·경험치 값·레벨 곡선은 서버가 정한다. FE에 하드코딩하지 말 것(퀘스트 코드 상수만 `types/quest.ts`).

### 1-1. 레벨 단계 (`pet.stage_code`)

| 레벨 | `stage_code` | `stage_label` | `emoji`(폴백) | 일러스트 |
|---|---|---|---|---|
| 1–2 | `egg` | 알 | 🥚 | `/assets/pet/egg.png` |
| 3–5 | `chick` | 아기 제비 | 🐣 | `/assets/pet/chick.png` |
| 6–9 | `fledgling` | 어린 제비 | 🐦 | `/assets/pet/fledgling.png` |
| 10+ | `swallow` | 제비 | 🕊 | `/assets/pet/swallow.png` |

- **FE가 할 일**: `stage_code` → 경로 매핑은 `frontend/lib/pet.ts`의 `STAGE_IMAGE` 한 곳뿐이다. 모르는 코드가 오면 `null`을 돌려주고 호출자가 `emoji`로 떨어진다(없는 그림을 있는 척하지 않는다).
- 일러스트는 **320x192(5:3) 투명 PNG**다. 정사각·원형 프레임으로 자르지 말 것 — 날개 편 단계가 잘린다.
- 레벨 경계와 파일명이 어긋나면 그림이 조용히 사라지므로 `backend/tests/test_quest_progress.py`가 **단계 코드와 파일 존재를 함께 검증**한다.

## 2. 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/api/v1/quests/today` | 오늘 상태 조회 |
| POST | `/api/v1/quests/{quest_code}` | 퀘스트 완료(**멱등**) |

**인증**: 둘 다 `Authorization: Bearer <access>` 필수(없으면 401). 게스트에겐 이 기능이 없다 — 게스트 화면은 `GUEST_PET`(이름·그림만, 레벨·단계 없음)로 떨어진다.

**에러**

| 상황 | 상태 | code |
|---|---|---|
| 없는 퀘스트 코드 | 404 | `QUEST_NOT_FOUND` |
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
- **`emoji`는 폴백으로만 남았다.** 화면은 `stage_code`로 일러스트를 찾고, 모르는 코드일 때만 이모지가 나온다. 텍스트만 쓸 수 있는 자리(알림 문구 등)를 위해 필드는 유지한다.
- **`users.pet_code` 컬럼(0036)은 이제 아무도 읽지 않는다.** 캐릭터를 다시 늘리지 않기로 확정되면 drop 마이그레이션으로 정리한다(`quest_service.py`의 ponytail 주석).
- **우하단 상담 런처는 레벨을 반영하지 않는다.** 다 자란 제비 그림 고정(`LAUNCHER_ICON`) — 단계에 따라 자라게 하려면 `ChatDock`이 진행도를 조회해야 해서 별도 작업으로 뺐다.
- 퀘스트 카탈로그가 개편돼 사라진 코드가 로그에 남아도 조회는 죽지 않는다(0점 처리).
