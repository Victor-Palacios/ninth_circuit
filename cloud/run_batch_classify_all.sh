#!/bin/bash
# Fire 10 parallel classify_batch executions covering rows 0–2999.
# Each job processes 300 rows from a non-overlapping offset.
# Run this once; re-run as needed until all rows are classified.
set -e

REGION="${GCP_REGION:-us-central1}"
JOB_NAME="asylum-classify-batch"
BATCH_SIZE=300
NUM_JOBS=10

echo "Firing ${NUM_JOBS} parallel classify batch jobs (${BATCH_SIZE} rows each)..."
echo ""

for i in $(seq 0 $((NUM_JOBS - 1))); do
  OFFSET=$((i * BATCH_SIZE))
  echo "  Launching job offset=${OFFSET}..."
  gcloud run jobs execute "$JOB_NAME" \
    --region "$REGION" \
    --update-env-vars "BATCH_OFFSET=${OFFSET},BATCH_SIZE=${BATCH_SIZE}" \
    --async
done

echo ""
echo "All ${NUM_JOBS} jobs launched. Monitor at:"
echo "  https://console.cloud.google.com/run/jobs?project=${GCP_PROJECT_ID}"
