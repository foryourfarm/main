"""요청 빈도 제한 — 비용·무차별 대입 방어(CLAUDE.md §17).

**무엇을 막는가**(막지 못하는 것은 아래 한계 참고):

| 경로 | 세는 기준 | 막는 것 |
|---|---|---|
| `POST /chat` | `user.id` | 한 계정이 GPU 예산을 통째로 태우는 것 |
| `POST /auth/login` | 이메일 | 한 계정에 대한 비밀번호 무차별 대입 |
| `POST /auth/signup` | 전역 | 계정 스팸 + bcrypt CPU 소진 |

**왜 IP로 세지 않는가**: Cloud Run 뒤에서는 `request.client.host`가 구글 프록시라 전원이 한
버킷을 공유한다. 그래서 `X-Forwarded-For`를 봐야 하는데, 첫 항목은 클라이언트가 헤더를 직접
넣어 위조할 수 있고(제한 우회) 마지막 항목은 LB IP일 수 있어(전원 공유) 어느 쪽으로 골라도
조용히 망가진다. Cloud Run의 XFF 조립 방식을 실측하지 않은 채 고르는 것은 추측이다(§3-4).

그래서 **위조할 수 없는 값으로만 센다** — `/chat`은 인증을 요구하므로 `user.id`가 있고,
로그인은 공격 대상인 이메일 자체가 키다. IP가 꼭 필요한 자리는 남기지 않았다.

**한계(의도적)**: 카운터는 프로세스 메모리라 Cloud Run 인스턴스마다 따로 센다. 인스턴스가 N개면
실효 한도가 N배가 된다. 그래도 무제한보다 훨씬 낫고, 공유 카운터(Redis 등)는 저장소를 하나 더
운영해야 해서 지금 규모에는 밑진다.
# ponytail: 인스턴스별 카운터 + 전역 락. 인스턴스가 늘어 한도가 무의미해지면 Redis로 승격.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import Depends

from app.api.deps import get_current_user
from app.core.errors import AppError
from app.models import User

# (버킷이름, 키) -> 최근 허용된 요청 시각(monotonic). 오래된 것은 조회할 때 흘려보낸다.
_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
# 요청 핸들러가 스레드풀에서 동시에 도는 경로라 dict/deque 조작을 직렬화한다.
# 임계구역이 deque 몇 번이라 전역 락 하나로 충분하다.
_lock = threading.Lock()

# 한도. 전부 **사람의 정상 사용보다 한참 위**로 잡는다 — 목적은 공정 분배가 아니라 폭주 차단이다.
CHAT_PER_USER = (10, 60.0)  # 계정당 분당 10턴. 사람이 읽고 답하는 속도를 훨씬 넘는다.
LOGIN_PER_EMAIL = (10, 300.0)  # 이메일당 5분에 10회. 오타 몇 번은 통과, 사전 대입은 못 한다.
SIGNUP_GLOBAL = (30, 60.0)  # 전역 분당 30건. 가입은 원래 드문 행위다.


def check(bucket: str, key: str, limit: tuple[int, float]) -> None:
    """슬라이딩 윈도우. 한도를 넘으면 429로 끊는다.

    한도에 걸린 요청은 기록하지 않는다 — 기록하면 계속 두드리는 클라이언트가 스스로
    윈도우를 갱신해 영구히 잠기고, 그건 제한이 아니라 차단이다.
    """
    max_calls, window_s = limit
    now = time.monotonic()
    with _lock:
        recent = _hits[(bucket, key)]
        while recent and now - recent[0] > window_s:
            recent.popleft()
        if len(recent) >= max_calls:
            raise AppError(429, "RATE_LIMITED", "요청이 너무 잦습니다. 잠시 후 다시 시도해 주세요.")
        recent.append(now)


def rate_limit_chat(current: User = Depends(get_current_user)) -> None:
    """`/chat` 가드. `get_current_user`를 다시 의존하므로 **인증 실패는 429가 아니라 401**이다
    (같은 의존성이라 FastAPI가 한 번만 푼다 — 중복 조회가 아니다)."""
    check("chat", str(current.id), CHAT_PER_USER)


def reset() -> None:
    """테스트 전용 — 카운터를 비운다. 테스트끼리 한도를 물려받지 않게 한다."""
    with _lock:
        _hits.clear()
