#!/usr/bin/env bash
# One-shot deploy: provisions Artifact Registry, secrets, both Cloud Run
# services, and the Cloud Scheduler tick job. Idempotent — safe to re-run.
#
# Prerequisites:
#   - gcloud auth login
#   - gcloud auth application-default login
#   - gcloud config set project <PROJECT_ID>
#   - (Optional) RESEND_API_KEY exported for email delivery
#
# Usage:
#   bash infra/deploy.sh

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project)}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-tableau}"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d-%H%M%S)}"

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
create_secret_if_missing internal-tick-token "$INTERNAL_TICK_TOKEN_VAL"
if [[ -n "${RESEND_API_KEY:-}" ]]; then
  create_secret_if_missing resend-api-key "$RESEND_API_KEY"
  RESEND_SECRET_FLAG="RESEND_API_KEY=resend-api-key:latest,"
else
  echo "  · skipping resend-api-key (not set; email will fall back to console)"
  RESEND_SECRET_FLAG=""
fi
if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
  create_secret_if_missing anthropic-api-key "$ANTHROPIC_API_KEY"
  ANTHROPIC_SECRET_FLAG="ANTHROPIC_API_KEY=anthropic-api-key:latest,"
else
  ANTHROPIC_SECRET_FLAG=""
fi

# 4. Firestore (idempotent: native mode, regional).
echo "→ Firestore database (native mode)…"
gcloud firestore databases create --location="$REGION" --quiet 2>/dev/null || true

# 5. Grant the Cloud Run runtime SA the roles it needs (Vertex AI, Firestore).
echo "→ IAM…"
RUNTIME_SA="$(gcloud iam service-accounts list --filter='displayName:Default compute service account' --format='value(email)' | head -1)"
if [[ -z "$RUNTIME_SA" ]]; then
  RUNTIME_SA="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')-compute@developer.gserviceaccount.com"
fi
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$RUNTIME_SA" --role="roles/aiplatform.user" --quiet >/dev/null 2>&1 || \
  echo "  (skipped aiplatform.user grant — may need owner)"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$RUNTIME_SA" --role="roles/datastore.user" --quiet >/dev/null 2>&1 || \
  echo "  (skipped datastore.user grant — may need owner)"

# 6. Build image via Cloud Build.
echo "→ Building image with Cloud Build…"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/concierge:${IMAGE_TAG}"
gcloud builds submit --tag "$IMAGE" --quiet .

# 7. Deploy API.
echo "→ Deploying concierge-api…"
gcloud run deploy concierge-api \
  --image "$IMAGE" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --min-instances 0 --max-instances 2 \
  --memory 1Gi --concurrency 20 \
  --service-account "$RUNTIME_SA" \
  --set-env-vars "SERVICE=api,GCP_PROJECT_ID=${PROJECT_ID},GCP_REGION=${REGION},PROVIDER_MODE=mock,LLM_PROVIDER=vertex,MEMORY_BACKEND=firestore,USE_FAKE_RESY=true,SUPERVISOR_MODEL=gemini-2.5-flash,WORKER_MODEL=gemini-2.5-flash,JUDGE_MODEL=gemini-2.5-flash" \
  --set-secrets "${ANTHROPIC_SECRET_FLAG}${RESEND_SECRET_FLAG}INTERNAL_TICK_TOKEN=internal-tick-token:latest" \
  --quiet

API_URL=$(gcloud run services describe concierge-api --region "$REGION" --format='value(status.url)')
echo "  ✓ API: $API_URL"

# 8. Deploy Web (passes API_URL + FAKE_RESY_BASE so deep links work).
echo "→ Deploying concierge-web…"
gcloud run deploy concierge-web \
  --image "$IMAGE" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --min-instances 0 --max-instances 2 \
  --memory 1Gi --concurrency 10 \
  --service-account "$RUNTIME_SA" \
  --session-affinity \
  --set-env-vars "SERVICE=web,API_BASE_URL=${API_URL},FAKE_RESY_BASE=${API_URL},GCP_PROJECT_ID=${PROJECT_ID},DEMO_MODE=true" \
  --quiet

WEB_URL=$(gcloud run services describe concierge-web --region "$REGION" --format='value(status.url)')
echo "  ✓ Web: $WEB_URL"

# 9. Cloud Scheduler tick job.
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

# 10. Persist URLs.
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
