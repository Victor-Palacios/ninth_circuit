"""Centralized configuration and environment variable loading."""

import os


def _require_env(name: str) -> str:
    """Return an environment variable or raise with a clear message."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def is_cloud_run() -> bool:
    """Detect if running inside a Cloud Run container."""
    return bool(os.environ.get("K_SERVICE"))


# ── GCP ──────────────────────────────────────────────────────────────────────

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
GCP_REGION = os.environ.get("GCP_REGION", "us-central1")

# ── Supabase ─────────────────────────────────────────────────────────────────

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")


def get_supabase_secret_key() -> str:
    """Return the Supabase service-role key.

    In Cloud Run, reads from GCP Secret Manager (secret: supabase-secret-key).
    Locally, reads from the SUPABASE_SECRET_KEY env var.
    """
    local_key = os.environ.get("SUPABASE_SECRET_KEY")
    if local_key:
        return local_key

    if is_cloud_run():
        from google.cloud import secretmanager

        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{_require_env('GCP_PROJECT_ID')}/secrets/supabase-secret-key/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")

    raise RuntimeError(
        "No Supabase secret key found. Set SUPABASE_SECRET_KEY env var "
        "or run inside Cloud Run with GCP Secret Manager configured."
    )


# ── CourtListener (fallback data source) ─────────────────────────────────────

COURTLISTENER_TOKEN = os.environ.get("COURTLISTENER_TOKEN", "")
