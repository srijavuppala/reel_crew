#!/usr/bin/env bash
# Deploy to Cloud Run. Requires an authenticated Google Cloud CLI and .env.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a

# Homebrew's cask can install gcloud without adding it to PATH in non-interactive
# shells (including Codex). Resolve that common location before failing.
if command -v gcloud >/dev/null 2>&1; then
  GCLOUD="$(command -v gcloud)"
elif [[ -x /opt/homebrew/share/google-cloud-sdk/bin/gcloud ]]; then
  GCLOUD=/opt/homebrew/share/google-cloud-sdk/bin/gcloud
else
  echo "gcloud not found. Install the Google Cloud CLI and authenticate first." >&2
  exit 1
fi

# GOOGLE_CLOUD_PROJECT is also consumed by the Vertex AI client, so prefer one
# project variable instead of requiring a second spelling only for deployment.
GCP_PROJECT="${GCP_PROJECT:-${GOOGLE_CLOUD_PROJECT:-}}"
: "${GCP_PROJECT:?Set GOOGLE_CLOUD_PROJECT=your-project-id in .env}"
# Cloud client libraries accept a project number in some contexts, but the
# `gcloud run deploy --project` flag requires the textual project ID.
if [[ "$GCP_PROJECT" =~ ^[0-9]+$ ]]; then
  CONFIGURED_PROJECT="$("$GCLOUD" config get-value project 2>/dev/null)"
  if [[ -z "$CONFIGURED_PROJECT" || "$CONFIGURED_PROJECT" == "(unset)" || "$CONFIGURED_PROJECT" =~ ^[0-9]+$ ]]; then
    echo "GOOGLE_CLOUD_PROJECT is a project number; set it to the project ID." >&2
    exit 1
  fi
  GCP_PROJECT="$CONFIGURED_PROJECT"
fi
REGION="${GCP_REGION:-us-central1}"
SERVICE="${SERVICE_NAME:-reel-crew}"

"$GCLOUD" services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com aiplatform.googleapis.com \
  --project "$GCP_PROJECT"

# Deliberately do not deploy GOOGLE_API_KEY. Cloud Run uses its service identity
# with Vertex AI ADC, avoiding long-lived API keys in service configuration.
"$GCLOUD" run deploy "$SERVICE" \
  --source . \
  --project "$GCP_PROJECT" \
  --region "$REGION" \
  --allow-unauthenticated \
  --set-env-vars "CLICKHOUSE_HOST=${CLICKHOUSE_HOST},CLICKHOUSE_PORT=${CLICKHOUSE_PORT},CLICKHOUSE_USER=${CLICKHOUSE_USER},CLICKHOUSE_PASSWORD=${CLICKHOUSE_PASSWORD},CLICKHOUSE_DATABASE=${CLICKHOUSE_DATABASE},CLICKHOUSE_SECURE=${CLICKHOUSE_SECURE},GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=${GCP_PROJECT},GOOGLE_CLOUD_LOCATION=${GOOGLE_CLOUD_LOCATION:-global},GEMINI_MODEL=${DEPLOY_GEMINI_MODEL:-gemini-2.5-flash-lite},GEMINI_THINKING_BUDGET=${GEMINI_THINKING_BUDGET:-0}"

"$GCLOUD" run services describe "$SERVICE" --project "$GCP_PROJECT" --region "$REGION" \
  --format='value(status.url)'
