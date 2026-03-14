#!/bin/bash
# Deploy MLflow tracking server to Cloud Run (scales to zero).
# Uses SQLite backend (no Cloud SQL) and GCS for artifacts.
set -e

REGION="${GCP_REGION:-us-central1}"
IMAGE="us-central1-docker.pkg.dev/$GCP_PROJECT_ID/asylum-extractor/mlflow-server"

cd "$(dirname "$0")"

echo "Building MLflow server image..."
gcloud builds submit --tag "$IMAGE" .

echo "Deploying to Cloud Run..."
gcloud run deploy mlflow-server \
  --image "$IMAGE" \
  --region "$REGION" \
  --port 5000 \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 1 \
  --memory 512Mi

echo "MLflow server deployed. Access via the URL above."
echo "Set MLFLOW_TRACKING_URI to the Cloud Run URL to log experiments."
