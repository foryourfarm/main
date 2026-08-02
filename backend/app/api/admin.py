"""운영 작업 엔드포인트. 유저용 API가 아니라 스케줄러(Cloud Scheduler)가 부른다.

**왜 별도 Cloud Run Job이 아니라 이미 떠 있는 서비스인가**: 이 컨테이너에 DB 연결과
ETL 코드가 이미 들어 있다. Job으로 빼면 새 배포 대상·Cloud SQL 연결·IAM을 한 벌 더
관리해야 하는데, 얻는 것은 공격면 감소뿐이다. 그 공격면은 아래 인증으로 막고,
증가분이 이미 공개된 `/auth/login`(요청당 bcrypt)보다 훨씬 싸다고 판단했다
(2026-08-02 팀 결정). 부수 이득으로 수동 갱신을 curl 한 줄로 할 수 있다.

인증은 공유 시크릿 헤더다. Cloud Run 서비스가 공개(프론트가 부른다)라
`--no-allow-unauthenticated` + IAM으로는 막을 수 없다.
"""

import secrets
from datetime import date

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.db.session import get_db
from app.infra.public_api.outlook_client import OutlookFetchError
from app.schemas.admin import OutlookIngestResult
from app.schemas.common import ApiResponse
from app.services.outlook_ingest_service import ingest_latest_outlook

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def require_admin_token(x_admin_token: str = Header(default="")) -> None:
    """공유 시크릿 검사. DB·외부 API를 타기 **전에** 돌아 무단 호출이 비용을 못 만들게 한다."""
    # 토큰 미설정은 "누구나 통과"가 아니라 "기능 꺼짐"으로 본다 — env를 빠뜨린 배포가
    # 인증 없는 적재 엔드포인트를 공개하는 사고를 구조적으로 막는다(fail closed, §17).
    if not settings.admin_task_token:
        raise AppError(503, "ADMIN_TASKS_DISABLED", "운영 작업이 비활성화되어 있습니다.")
    # compare_digest는 비교 시간으로 정답 길이·접두를 흘리지 않는다. str 인자는 비ASCII에서
    # TypeError를 내므로 bytes로 넘긴다(헤더에 한글이 들어와도 500이 아니라 401이어야 한다).
    if not secrets.compare_digest(
        x_admin_token.encode("utf-8"), settings.admin_task_token.encode("utf-8")
    ):
        raise AppError(401, "UNAUTHORIZED", "인증이 필요합니다.")


@router.post("/weather-outlooks", dependencies=[Depends(require_admin_token)])
def refresh_weather_outlook(
    db: Session = Depends(get_db),
) -> ApiResponse[OutlookIngestResult]:
    """기상청 3개월전망 최신 발표분을 적재한다(멱등). 스케줄러가 매일 1회 부른다."""
    try:
        result = ingest_latest_outlook(db, date.today())
    except OutlookFetchError as exc:
        # 클라이언트가 최근 2개월치를 되짚어도 못 찾은 상황이라 상류 장애나 RSS 스키마
        # 변경이다. 스케줄러가 재시도하고 로그에 남도록 실패로 돌려준다 — 200으로 삼키면
        # nexttodo가 지적한 "에러 없이 조용히 낡는" 문제를 그대로 재현한다(§12).
        raise AppError(502, "UPSTREAM_UNAVAILABLE", "3개월전망을 가져오지 못했습니다.") from exc
    return ApiResponse.ok(result)
