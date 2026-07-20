# ---------- Stage 1: build the React console ----------
FROM node:20-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: FastAPI runtime ----------
FROM python:3.12-slim
WORKDIR /app

# FFmpeg: video frame-stitching pipeline (roadmap 4.1)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/app backend/app
COPY --from=frontend /build/dist frontend/dist

WORKDIR /app/backend

# Runtime configuration (override with -e KEY=VALUE at docker run)
ENV FRONTEND_DIST=/app/frontend/dist \
    DATABASE_URL=sqlite:////app/backend/data/nexusai.db \
    GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4 \
    GLM_DEFAULT_MODEL=glm-4-flash \
    GLM_API_KEY=029a1e4f78b74e5cbefddcb0b0dd22e6.dIgT0M6gEVIqE4W3 \
    IMAGE_BACKEND=cogview \
    COGVIEW_MODEL=cogview-3-flash \
    TF_IMAGE_URL= \
    VIDEO_BACKEND=cogvideo \
    COGVIDEO_MODEL=cogvideox-flash \
    TF_VIDEO_URL= \
    SANDBOX_BACKEND=subprocess \
    SANDBOX_MAX_SECONDS=30 \
    SANDBOX_MAX_MEMORY_MB=512 \
    SANDBOX_AUTO_INSTALL=true \
    SANDBOX_MAX_ATTEMPTS=3 \
    TF_AGENT_ENABLED=true \
    TF_AGENT_POLICY_PATH=/app/backend/data/policies/router_policy.json \
    SELF_REFLECT_RATIO=0.10 \
    MEDIA_DIR=/app/backend/data/media \
    DAILY_TOKEN_QUOTA=200000 \
    DAILY_MEDIA_QUOTA=50 \
    DAILY_CODE_EXEC_QUOTA=100 \
    JWT_SECRET=9f2c4d7b1a8e5f3c6d0b9a2e4f7c1d8b5a3e6f9c0d2b4a7e1f8c3d6b9a0e2f5c \
    RATE_LIMIT_PER_MINUTE=60

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
