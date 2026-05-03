# Multi-target Dockerfile. The same image runs both Cloud Run services;
# the SERVICE env var (api | web) chooses the entrypoint.
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps — minimal; faiss-cpu wants libgomp.
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Python deps — copy first for cache.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

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
