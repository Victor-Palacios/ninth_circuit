"""Daily backup of asylum_cases to GCS.

Saves a JSON export to:
  gs://th-circuit-backups/daily/YYYY-MM-DD.json  (auto-deleted after 30 days)
  gs://th-circuit-backups/monthly/YYYY-MM.json   (kept indefinitely, 1st of month only)

The daily/ prefix has a GCS lifecycle policy that auto-deletes files older than 30 days.
Monthly backups are kept forever for long-term archival.
"""

import json
from datetime import datetime, timezone

from google.cloud import storage

from lib.supabase_client import get_client


GCS_BUCKET = "th-circuit-backups"


def fetch_all_asylum_cases(supabase) -> list[dict]:
    """Fetch all rows from asylum_cases in pages."""
    all_rows = []
    page_size = 1000
    offset = 0
    while True:
        result = (
            supabase.table("asylum_cases")
            .select("*")
            .order("date_filed", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        all_rows.extend(result.data)
        if len(result.data) < page_size:
            break
        offset += page_size
    return all_rows


def upload(data: list[dict], blob_name: str) -> str:
    """Upload JSON data to GCS. Returns the GCS URI."""
    client = storage.Client()
    bucket = client.bucket(GCS_BUCKET)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(
        json.dumps(data, indent=2),
        content_type="application/json",
    )
    uri = f"gs://{GCS_BUCKET}/{blob_name}"
    print(f"  Uploaded {len(data):,} rows to {uri}")
    return uri


def run():
    """Run the backup."""
    supabase = get_client()
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    month_str = now.strftime("%Y-%m")

    print(f"Fetching all asylum cases...")
    rows = fetch_all_asylum_cases(supabase)
    print(f"  Fetched {len(rows):,} rows")

    # Daily backup (auto-deleted after 30 days via lifecycle policy)
    upload(rows, f"daily/{date_str}.json")

    # Monthly backup on the 1st of each month
    if now.day == 1:
        upload(rows, f"monthly/{month_str}.json")
        print(f"  Monthly backup saved for {month_str}")

    print("Backup complete.")


def main():
    print("=" * 60)
    print("Ninth Circuit — Database Backup")
    print("=" * 60)
    run()


if __name__ == "__main__":
    main()
