"""구조화 로깅 설정 — Cloud Logging이 심각도로 걸러낼 수 있게 한다.

**왜 필요한가**: 2026-08-03에 단기 탭 행동추천이 화면에서 통째로 사라졌는데
`severity>=ERROR`로 로그를 조회해도 **한 줄도 안 나왔다.** `main.py`의
`unhandled_exception_handler`가 모든 예외를 잡아 공통 실패 포맷으로만 바꾸고
**트레이스백을 버리고 있었기 때문이다.** 500이 나도 원인을 찾을 방법이 없었다.

**왜 JSON인가**: Cloud Run은 stdout 한 줄을 로그 한 건으로 받는데, 평문이면 전부
`INFO`로 들어가 `severity>=ERROR` 필터에 안 걸린다(파이썬 기본 stderr 출력은 반대로
전부 `ERROR`가 돼 INFO까지 에러로 보인다). `severity` 필드를 실은 JSON을 stdout에 쓰면
Cloud Logging이 그 값을 그대로 심각도로 읽는다.

**민감정보를 싣지 않는다**(§17): 로그에 넣는 것은 메서드·경로·상태코드·예외뿐이다.
쿼리스트링과 본문은 넣지 않는다 — 로그인 본문에 비밀번호가, 쿼리에 토큰이 실릴 수 있다.

로컬(비 Cloud Run) 개발에서는 JSON이 읽기 불편하므로 평문으로 떨어진다 — `K_SERVICE`
환경변수(Cloud Run이 항상 주입)로 판별한다.
"""

import json
import logging
import os
import sys
from typing import Any

# 파이썬 레벨명 → Cloud Logging severity. 이름이 대부분 같지만 WARNING만 다르다.
_SEVERITY = {
    "DEBUG": "DEBUG",
    "INFO": "INFO",
    "WARNING": "WARNING",
    "ERROR": "ERROR",
    "CRITICAL": "CRITICAL",
}


class CloudLoggingFormatter(logging.Formatter):
    """Cloud Logging이 파싱하는 한 줄 JSON. 트레이스백은 message에 이어 붙인다."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "severity": _SEVERITY.get(record.levelname, "DEFAULT"),
            "message": record.getMessage(),
            "logger": record.name,
        }
        # 예외가 있으면 트레이스백을 message에 붙인다 — Cloud Logging UI가 message를
        # 펼쳐 보여주므로 별도 필드보다 이쪽이 읽기 쉽다.
        if record.exc_info:
            payload["message"] += "\n" + self.formatException(record.exc_info)
        # 핸들러가 실어 보낸 요청 컨텍스트(있을 때만).
        for key in ("http_method", "http_path", "http_status"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    """루트 로거를 stdout으로 고정한다. 앱 기동 시 한 번 부른다.

    기존 핸들러를 지우고 새로 단다 — uvicorn이 이미 붙여둔 핸들러와 겹치면 같은 줄이
    두 번 찍힌다(Cloud Logging 비용과 가독성 둘 다 나빠진다).
    """
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    # Cloud Run 밖(로컬)에서는 평문이 읽기 쉽다. K_SERVICE는 Cloud Run이 항상 주입한다.
    if os.getenv("K_SERVICE"):
        handler.setFormatter(CloudLoggingFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))

    root.addHandler(handler)
    root.setLevel(logging.INFO)
