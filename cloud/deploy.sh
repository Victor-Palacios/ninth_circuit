#!/bin/bash
# Deploy the asylum pipeline to Google Cloud Run as a scheduled job.
# Prerequisites: gcloud CLI authenticated, GCP_PROJECT_ID and SUPABASE_URL env vars set.
set -e

REGION="${GCP_REGION:-us-central1}"
IMAGE="us-central1-docker.pkg.dev/$GCP_PROJECT_ID/asylum-pipeline/asylum-pipeline"

# Build from the project root (one level up from cloud/)
cd "$(dirname "$0")/.."

echo "Building container image..."
cp cloud/Dockerfile Dockerfile
gcloud builds submit --tag "$IMAGE" .
rm -f Dockerfile

echo "Deploying Cloud Run job..."
gcloud run jobs deploy asylum-pipeline \
  --image "$IMAGE" \
  --region "$REGION" \
  --set-env-vars "GCP_PROJECT_ID=$GCP_PROJECT_ID,SUPABASE_URL=$SUPABASE_URL,GCP_REGION=$REGION" \
  --set-secrets="SUPABASE_SECRET_KEY=supabase-secret-key:latest"

echo "Executing job..."
gcloud run jobs execute asylum-pipeline --region "$REGION"
