"""weather_outlook 적재 CLI — 기상청 3개월전망 RSS (DB.md §3.12).

적재 로직은 여기 없다. `app/services/outlook_ingest_service.ingest_latest_outlook`에
있고 스케줄러 엔드포인트(`POST /api/v1/admin/weather-outlooks`)가 같은 함수를 부른다 —
수동 경로와 자동 경로가 갈리면 한쪽만 고쳐지는 사고가 난다.

이 파일은 그 함수를 터미널에서 부르기 위한 껍데기다(초기 배포·긴급 수동 갱신용).
평소 갱신은 스케줄러가 한다 — docs/outlook-scheduler.md.

실행: backend/.venv/Scripts/python.exe scripts/load_weather_outlook.py
"""

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.db.session import SessionLocal  # noqa: E402
from app.infra.public_api.outlook_client import OutlookFetchError  # noqa: E402
from app.services.outlook_ingest_service import ingest_latest_outlook  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        result = ingest_latest_outlook(db, date.today())
    except OutlookFetchError as exc:
        print(f"적재 생략: {exc}")
        raise SystemExit(1) from exc
    finally:
        db.close()

    months = [m.isoformat() for m in result.target_months]
    print(f"발표일 {result.published_at} · 적재 완료: {result.rows}행 (대상월 {months})")
    if result.unmapped_zones:
        print(
            f"매핑 없는 권역 {len(result.unmapped_zones)}개(의도적 제외): {result.unmapped_zones}"
        )


if __name__ == "__main__":
    main()
