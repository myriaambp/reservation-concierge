#!/usr/bin/env bash
set -euo pipefail

case "${SERVICE:-api}" in
  api)
    exec uvicorn backend.api.main:app --host 0.0.0.0 --port "${PORT:-8080}"
    ;;
  web)
    exec streamlit run frontend/streamlit_app.py \
      --server.port="${PORT:-8080}" \
      --server.address=0.0.0.0 \
      --server.headless=true \
      --browser.gatherUsageStats=false
    ;;
  *)
    echo "Unknown SERVICE: $SERVICE (expected api|web)" >&2
    exit 1
    ;;
esac
