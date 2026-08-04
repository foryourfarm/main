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
import re
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

# 쿼리스트링에 인증키를 실어보내는 공공 API들 때문에 **URL이 곧 비밀**이다(§17).
# 공공데이터포털은 `serviceKey`, 기상청 apihub는 `authKey`, VWorld는 그냥 `key`를 쓴다.
#
# **레벨을 낮추는 것만으로는 못 막는다.** httpx의 INFO 요청 로그를 껐어도 예외 메시지에
# URL이 그대로 들어간다("Client error '401' for url 'https://…?serviceKey=…'"). 그게
# `exc_info=True` 트레이스백을 타고 로그로 나간다. 그래서 **출력 직전에 한 번** 지운다 —
# 호출부마다 조심하게 하지 않고 한 곳에서 막는다.
#
# 맨 끝의 `key`는 VWorld용이다. 지금 VWorld는 스크립트에서만 쓰여 이 경로를 안 타지만,
# 런타임으로 옮기는 순간 조용히 새는 자리라 미리 막아둔다. `\b`가 앞에 있어 `authKey=`나
# `sortkey=` 같은 합성어 안의 `key`에는 걸리지 않는다(테스트로 고정).
_SECRET_QUERY = re.compile(r"(?i)\b(serviceKey|authKey|apikey|api_key|key)=([^&\s'\"<>]+)")


def redact(text: str) -> str:
    """로그로 나가는 문자열에서 인증키를 지운다. 키 이름은 남긴다(어느 API인지는 진단에 필요)."""
    return _SECRET_QUERY.sub(r"\1=***", text)


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
        payload["message"] = redact(payload["message"])
        # 핸들러가 실어 보낸 요청 컨텍스트(있을 때만).
        for key in ("http_method", "http_path", "http_status"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False)


class PlainFormatter(logging.Formatter):
    """로컬 개발용 평문. **마스킹은 여기에도 필요하다** — 로컬 로그를 붙여넣다 키가 새는
    사고가 실제로 이 세션에서 있었다(운영 로그였지만 경로는 같다)."""

    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


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
        handler.setFormatter(PlainFormatter("%(levelname)s %(name)s: %(message)s"))

    root.addHandler(handler)
    root.setLevel(logging.INFO)

    # **API 키가 로그에 새는 것을 막는다(§17).** httpx는 INFO에서 요청 URL을 통째로 찍는데,
    # 공공데이터포털은 인증키를 쿼리스트링(`?serviceKey=…`)으로 받는다. 그래서 루트를
    # INFO로 열면 실제 키가 평문으로 Cloud Logging에 적재된다 — 2026-08-03 실측으로 확인,
    # 흙토람 호출 URL에 64자 키가 그대로 찍혔다.
    #
    # 호출 성패는 각 클라이언트가 자기 로그로 남기므로(§district_soil_service 등) httpx의
    # 원본 URL 로그는 없어도 진단에 지장이 없다. httpcore는 더 저수준이라 같이 올린다.
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
