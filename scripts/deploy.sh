#!/usr/bin/env bash
# Cloud Run 배포 — 순서를 코드로 굳힌다.
#
# 왜 스크립트인가: 이 배포에는 손으로 하면 틀리는 지점이 둘 있고, 둘 다 **배포 시점에는
# 성공한 것처럼 보인다.**
#   ① 법정동 적재가 백엔드보다 늦으면 → 유저가 리를 고르는 순간 FK 위반으로 등록 실패
#   ② 프론트 빌드에 백엔드 URL을 안 넣으면 → 배포는 성공하는데 브라우저가 localhost를 호출
# 명령을 줄이려는 게 아니라 이 두 순서를 건너뛸 수 없게 하려는 것이다.
#
# 실행: PROJECT_ID=... CLOUDSQL=... DATABASE_URL=... ./scripts/deploy.sh
#
# 전제:
#   - gcloud 로그인 완료(gcloud auth login) + 프로젝트 권한
#   - DATABASE_URL이 **프로덕션 DB**를 가리킨다(보통 cloud-sql-proxy 경유)
#   - 리포 루트에서 실행

set -euo pipefail
cd "$(dirname "$0")/.."

: "${PROJECT_ID:?PROJECT_ID 필요 (예: my-gcp-project)}"
: "${CLOUDSQL:?CLOUDSQL 필요 — INSTANCE_CONNECTION_NAME (예: proj:asia-northeast3:foryourfarm)}"
: "${DATABASE_URL:?DATABASE_URL 필요 — Cloud Run이 쓸 값. 이 스크립트의 DB 단계도 이걸 쓴다}"
: "${REGION:=asia-northeast3}"

PY=backend/.venv/Scripts/python.exe
[ -x "$PY" ] || PY=backend/.venv/bin/python

# 배포 대상을 먼저 보여주고 확인받는다 — 프로덕션 DB에 쓰는 단계가 뒤에 있다.
echo "프로젝트 : $PROJECT_ID / $REGION"
echo "Cloud SQL: $CLOUDSQL"
echo "커밋     : $(git rev-parse --short HEAD) ($(git rev-parse --abbrev-ref HEAD))"
read -r -p "이 내용으로 배포한다. 계속? [y/N] " ok
[ "$ok" = "y" ] || { echo "중단"; exit 1; }

echo "== ① 스키마 최신화 =="
(cd backend && ../"$PY" -m alembic upgrade head)

echo "== ② 법정동 마스터 적재 (백엔드보다 먼저여야 한다) =="
# 멱등(bjd_code upsert)이라 재실행해도 안전하다.
"$PY" scripts/load_districts.py

echo "== ③ 백엔드 빌드·배포 =="
# 컨텍스트는 리포 루트다 — backend/만 잡으면 docs/seed/가 이미지에서 빠져 런타임에 죽는다.
gcloud builds submit --config cloudbuild.yaml --project "$PROJECT_ID" .
gcloud run deploy foryourfarm-backend \
  --image "gcr.io/$PROJECT_ID/foryourfarm-backend" \
  --project "$PROJECT_ID" --region "$REGION" \
  --add-cloudsql-instances "$CLOUDSQL" \
  --set-env-vars "DATABASE_URL=$DATABASE_URL${LLM_BASE_URL:+,LLM_BASE_URL=$LLM_BASE_URL}"

API_BASE=$(gcloud run services describe foryourfarm-backend \
  --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')
[ -n "$API_BASE" ] || { echo "백엔드 URL을 못 읽었다 — 프론트를 빌드하면 localhost를 가리킨다"; exit 1; }
echo "백엔드 URL: $API_BASE"

echo "== ④ 프론트 빌드·배포 (URL을 빌드 시점에 굳힌다) =="
# NEXT_PUBLIC_*은 next build 때 번들에 박힌다 — run deploy --set-env-vars로는 못 바꾼다.
gcloud builds submit --config cloudbuild.frontend.yaml \
  --project "$PROJECT_ID" --substitutions="_API_BASE=$API_BASE" frontend
gcloud run deploy foryourfarm-frontend \
  --image "gcr.io/$PROJECT_ID/foryourfarm-frontend" \
  --project "$PROJECT_ID" --region "$REGION"

echo "완료 — 프론트: $(gcloud run services describe foryourfarm-frontend \
  --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"
