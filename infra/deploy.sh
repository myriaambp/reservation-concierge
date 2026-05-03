#!/usr/bin/env bash
# One-shot deploy: provisions Artifact Registry, secrets, both Cloud Run
# services, and the Cloud Scheduler tick job. Idempotent — safe to re-run.
#
# Prerequisites:
#   - gcloud auth login
#   - gcloud config set project <PROJECT_ID>
#   - ANTHROPIC_API_KEY exported in your shell
#
# Usage:
#   bash infra/deploy.sh

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project)}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-tableau}"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d-%H%M%S)}"

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "❌ ANTHROPIC_API_KEY is not set in your shell. Aborting."
  exit 1
fi

echo "→ Project:  $PROJECT_ID"
echo "→ Region:   $REGION"
echo "→ Tag:      $IMAGE_TAG"

# 1. Enable APIs.
echo "→ Enabling APIs…"
gcloud services enable \
  run.googleapis.com \
  cloudscheduler.googleapis.com \
  firestore.googleapis.com \
  aiplatform.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  --quiet

# 2. Artifact Registry repo.
gcloud artifacts repositories describe "$REPO" --location="$REGION" >/dev/null 2>&1 || \
  gcloud artifacts repositories create "$REPO" \
    --repository-format=docker --location="$REGION" --quiet

# 3. Secrets.
INTERNAL_TICK_TOKEN_VAL="${INTERNAL_TICK_TOKEN_VAL:-$(openssl rand -hex 16)}"

create_secret_if_missing () {
  local name=$1 ; local val=$2
  if ! gcloud secrets describe "$name" >/dev/null 2>&1; then
    echo "  · creating secret $name"
    printf '%s' "$val" | gcloud secrets create "$name" --data-file=- --quiet
  else
    echo "  · updating secret $name"
    printf '%s' "$val" | gcloud secrets versions add "$name" --data-file=- --quiet
  fi
}

echo "→ Secrets…"
create_secret_if_missing anthropic-api-key "$ANTHROPIC_API_KEY"
create_secret_if_missing internal-tick-token "$INTERNAL_TICK_TOKEN_VAL"

# 4. Firestore (idempotent: native mode, regional).
echo "→ Firestore database (native mode)…"
gcloud firestore databases create --location="$REGION" --quiet 2>/dev/null || true

# 5. Build image via Cloud Build.
echo "→ Building image with Cloud Build…"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/concierge:${IMAGE_TAG}"
gcloud builds submit --tag "$IMAGE" --quiet .

# 6. Deploy API.
echo "→ Deploying concierge-api…"
gcloud run deploy concierge-api \
  --image "$IMAGE" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --min-instances 0 --max-instances 2 \
  --memory 1Gi --concurrency 20 \
  --set-env-vars "SERVICE=api,GCP_PROJECT_ID=${PROJECT_ID},GCP_REGION=${REGION},PROVIDER_MODE=mock" \
  --set-secrets "ANTHROPIC_API_KEY=anthropic-api-key:latest,INTERNAL_TICK_TOKEN=internal-tick-token:latest" \
  --quiet

API_URL=$(gcloud run services describe concierge-api --region "$REGION" --format='value(status.url)')
echo "  ✓ API: $API_URL"

# 7. Deploy Web (passes API_URL).
echo "→ Deploying concierge-web…"
gcloud run deploy concierge-web \
  --image "$IMAGE" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --min-instances 0 --max-instances 2 \
  --memory 1Gi --concurrency 10 \
  --set-env-vars "SERVICE=web,API_BASE_URL=${API_URL},GCP_PROJECT_ID=${PROJECT_ID}" \
  --quiet

WEB_URL=$(gcloud run services describe concierge-web --region "$REGION" --format='value(status.url)')
echo "  ✓ Web: $WEB_URL"

# 8. Cloud Scheduler tick job.
echo "→ Cloud Scheduler tick…"
JOB_NAME="concierge-tick"
if gcloud scheduler jobs describe "$JOB_NAME" --location="$REGION" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "$JOB_NAME" \
    --location="$REGION" \
    --schedule="*/2 * * * *" \
    --uri="${API_URL}/internal/tick" \
    --http-method=POST \
    --headers="X-Tick-Token=${INTERNAL_TICK_TOKEN_VAL}" \
    --quiet
else
  gcloud scheduler jobs create http "$JOB_NAME" \
    --location="$REGION" \
    --schedule="*/2 * * * *" \
    --uri="${API_URL}/internal/tick" \
    --http-method=POST \
    --headers="X-Tick-Token=${INTERNAL_TICK_TOKEN_VAL}" \
    --quiet
fi

# 9. Persist URLs.
cat > .env.deploy <<EOF
API_BASE_URL=${API_URL}
WEB_URL=${WEB_URL}
PROJECT_ID=${PROJECT_ID}
REGION=${REGION}
DEPLOYED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

echo
echo "✅ Deploy complete."
echo "   Web : $WEB_URL"
echo "   API : $API_URL"
echo "   .env.deploy written."
