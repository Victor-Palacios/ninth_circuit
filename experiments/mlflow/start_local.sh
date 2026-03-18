#!/bin/bash
# Start MLflow tracking server locally using Supabase as the backend store.
# Artifacts are stored locally in experiments/mlflow/artifacts/.
#
# Usage: bash experiments/mlflow/start_local.sh

set -e

# Load env vars
if [ -f .env ]; then
  set -a && source .env && set +a
fi

if [ -z "$DATABASE_URL" ]; then
  echo "ERROR: DATABASE_URL is not set in .env"
  exit 1
fi

# Activate venv
source ninthc/bin/activate

ARTIFACT_ROOT="$(pwd)/experiments/mlflow/artifacts"
mkdir -p "$ARTIFACT_ROOT"

echo "Starting MLflow server..."
echo "  Backend: Supabase Postgres"
echo "  Artifacts: $ARTIFACT_ROOT"
echo "  UI: http://localhost:5000"

mlflow server \
  --backend-store-uri "$DATABASE_URL" \
  --default-artifact-root "$ARTIFACT_ROOT" \
  --host 0.0.0.0 \
  --port 5000
