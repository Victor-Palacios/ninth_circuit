#!/bin/bash
# Set up Cloud Monitoring email alerts for the asylum pipeline.
# Run this once after deploying the Cloud Run job.
#
# Prerequisites:
#   - gcloud CLI authenticated
#   - GCP_PROJECT_ID env var set
#   - An email address to receive alerts
#
# Usage: EMAIL=your@email.com bash cloud/setup_alerting.sh
set -e

EMAIL="${EMAIL:?Set EMAIL env var to your notification email address}"
PROJECT="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID env var}"
REGION="${GCP_REGION:-us-central1}"

echo "Setting up alerting for project: $PROJECT"

# 1. Create a notification channel (email)
echo "Creating email notification channel..."
CHANNEL_ID=$(gcloud monitoring channels create \
  --project="$PROJECT" \
  --display-name="Pipeline Alert Email" \
  --type=email \
  --channel-labels="email_address=$EMAIL" \
  --format="value(name)")

echo "  Notification channel: $CHANNEL_ID"

# 2. Create alert policy for Cloud Run job failures
echo "Creating alert policy for job failures..."
gcloud monitoring policies create \
  --project="$PROJECT" \
  --display-name="Asylum Pipeline - Job Failure" \
  --condition-display-name="Cloud Run Job Failed" \
  --condition-filter='resource.type="cloud_run_job" AND resource.labels.job_name="asylum-pipeline" AND metric.type="run.googleapis.com/job/completed_execution_count" AND metric.labels.result="failed"' \
  --condition-threshold-value=1 \
  --condition-threshold-comparison=COMPARISON_GT \
  --condition-threshold-duration=0s \
  --notification-channels="$CHANNEL_ID" \
  --combiner=OR \
  --documentation="The asylum pipeline Cloud Run job failed. Check logs: gcloud run jobs executions list --job=asylum-pipeline --region=$REGION"

echo ""
echo "Alerting configured. You will receive emails at $EMAIL when:"
echo "  - The Cloud Run job fails"
echo ""
echo "To test: trigger a deliberate failure in the pipeline."
echo "To view alerts: https://console.cloud.google.com/monitoring/alerting?project=$PROJECT"
