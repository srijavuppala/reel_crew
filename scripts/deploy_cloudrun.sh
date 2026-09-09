#!/usr/bin/env bash
# Deploy to Cloud Run. Requires gcloud, an authenticated GCP project, and .env.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a

: "${GCP_PROJECT:?Set GCP_PROJECT=your-project-id}"
REGION="${GCP_REGION:-us-central1}"
SERVICE="${SERVICE_NAME:-reel-crew}"

gcloud run deploy "$SERVICE" \
  --source . \
  --project "$GCP_PROJECT" \
  --region "$REGION" \
  --allow-unauthenticated \
  --set-env-vars "CLICKHOUSE_HOST=${CLICKHOUSE_HOST},CLICKHOUSE_PORT=${CLICKHOUSE_PORT},CLICKHOUSE_USER=${CLICKHOUSE_USER},CLICKHOUSE_PASSWORD=${CLICKHOUSE_PASSWORD},CLICKHOUSE_DATABASE=${CLICKHOUSE_DATABASE},CLICKHOUSE_SECURE=${CLICKHOUSE_SECURE},GOOGLE_API_KEY=${GOOGLE_API_KEY:-},GEMINI_MODEL=${GEMINI_MODEL:-gemini-2.5-flash}"

gcloud run services describe "$SERVICE" --project "$GCP_PROJECT" --region "$REGION" \
  --format='value(status.url)'
