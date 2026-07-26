# 빌드 컨텍스트는 리포 루트다(docker build -f backend/Dockerfile . 로 실행) —
# district_soil_service.py / sunlight_calculation.py가 런타임에
# Path(__file__).parents[3]로 리포 루트의 docs/seed/를 참조하기 때문에
# backend/만 컨텍스트로 잡으면 그 파일들이 이미지에 없어 FileNotFoundError로 죽는다.
FROM python:3.13-slim

WORKDIR /workspace

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/alembic.ini backend/alembic.ini
COPY backend/alembic backend/alembic
COPY backend/app backend/app
COPY docs/seed docs/seed

WORKDIR /workspace/backend

# Cloud Run은 $PORT로 리스닝 포트를 주입한다(기본 8080) — 하드코딩하지 않고 그대로 받는다.
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
