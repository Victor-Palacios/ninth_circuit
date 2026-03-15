#!/bin/bash
# Deploy the asylum pipeline as 3 independent Cloud Run jobs with Cloud Scheduler.
# Prerequisites: gcloud CLI authenticated, GCP_PROJECT_ID and SUPABASE_URL env vars set.
set -e

REGION="${GCP_REGION:-us-central1}"
IMAGE="us-central1-docker.pkg.dev/$GCP_PROJECT_ID/asylum-pipeline/asylum-pipeline"

# Build from the project root (one level up from cloud/)
cd "$(dirname "$0")/.."

echo "=== Building container image ==="
cp cloud/Dockerfile Dockerfile
gcloud builds submit --tag "$IMAGE" .
rm -f Dockerfile

# Common env vars and secrets for all jobs
COMMON_ENV="GCP_PROJECT_ID=$GCP_PROJECT_ID,SUPABASE_URL=$SUPABASE_URL,GCP_REGION=$REGION"
COMMON_SECRETS="SUPABASE_SECRET_KEY=supabase-secret-key:latest"

# Deploy 3 separate Cloud Run jobs (same image, different PIPELINE_STEP)
for STEP in fetch classify extract qa; do
  JOB_NAME="asylum-${STEP}"
  echo ""
  echo "=== Deploying ${JOB_NAME} ==="
  gcloud run jobs deploy "$JOB_NAME" \
    --image "$IMAGE" \
    --region "$REGION" \
    --set-env-vars "${COMMON_ENV},PIPELINE_STEP=${STEP}" \
    --set-secrets="$COMMON_SECRETS"
done

# Create Cloud Scheduler triggers (idempotent — updates if already exists)
# Schedule: fetch 6am, classify 8am, extract 10am (Pacific Time)
echo ""
echo "=== Creating Cloud Scheduler triggers ==="

SCHEDULES=("fetch:0 6 * * *" "classify:0 8 * * *" "extract:0 10 * * *" "qa:0 12 * * *")

for ENTRY in "${SCHEDULES[@]}"; do
  STEP="${ENTRY%%:*}"
  CRON="${ENTRY#*:}"
  JOB_NAME="asylum-${STEP}"
  SCHEDULER_NAME="${JOB_NAME}-daily"

  echo "  ${SCHEDULER_NAME} → ${CRON} America/Los_Angeles"

  # Delete existing scheduler job if it exists (gcloud scheduler has no upsert)
  gcloud scheduler jobs delete "$SCHEDULER_NAME" \
    --location="$REGION" --quiet 2>/dev/null || true

  gcloud scheduler jobs create http "$SCHEDULER_NAME" \
    --location="$REGION" \
    --schedule="$CRON" \
    --time-zone="America/Los_Angeles" \
    --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${GCP_PROJECT_ID}/jobs/${JOB_NAME}:run" \
    --http-method=POST \
    --oauth-service-account-email="${GCP_PROJECT_ID}@appspot.gserviceaccount.com" \
    --oauth-token-scope="https://www.googleapis.com/auth/cloud-platform"
done

echo ""
echo "=== Deployment complete ==="
echo "Jobs: asylum-fetch, asylum-classify, asylum-extract, asylum-qa"
echo "Schedule: fetch@6am → classify@8am → extract@10am → qa@12pm (Pacific)"
