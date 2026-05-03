# Multi-target Dockerfile. The same image runs both Cloud Run services;
# the SERVICE env var (api | web) chooses the entrypoint.
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps:
# - libgomp1 for faiss-cpu
# - the rest are runtime libs Chromium needs for headless mode on Cloud Run
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    libgomp1 \
    fonts-liberation fonts-noto-color-emoji \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 \
    libcairo2 libcups2 libdbus-1-3 libdrm2 libgbm1 libglib2.0-0 \
    libnspr4 libnss3 libpango-1.0-0 libx11-6 libxcb1 libxcomposite1 \
    libxdamage1 libxext6 libxfixes3 libxkbcommon0 libxrandr2 \
    && rm -rf /var/lib/apt/lists/*

# Python deps — copy first for cache.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Chromium binary for Playwright (system deps are already installed above).
RUN playwright install chromium

# App code.
COPY backend ./backend
COPY frontend ./frontend
COPY seed_data ./seed_data

# Pre-build embeddings (best-effort; falls back to lexical at first request).
RUN python -m backend.rag.ingest || true

ENV SERVICE=api
ENV PORT=8080

# Generic entrypoint dispatches on SERVICE.
COPY infra/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8080
CMD ["/entrypoint.sh"]
