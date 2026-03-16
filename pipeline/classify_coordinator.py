"""Coordinator for parallel batch classification (Strategy 1).

Snapshots all unclassified opinion links from the DB, divides them into
N equal chunks, and uploads each chunk as a JSON file to GCS:

  gs://th-circuit-backups/classify-batches/job_00.json
  gs://th-circuit-backups/classify-batches/job_01.json
  ...

Each file is a list of opinion dicts (link, case_title, case_number,
date_filed, published_status). Parallel Cloud Run jobs then read their
assigned file from GCS and process only those rows — no live DB filtering,
no offset race condition.

Usage:
  python -m pipeline.classify_coordinator --jobs 10
"""

import argparse
import json
import math

from google.cloud import storage

from lib.supabase_client import get_client


GCS_BUCKET = "th-circuit-backups"
GCS_PREFIX = "classify-batches"


def fetch_unclassified(supabase) -> list[dict]:
    """Fetch all unclassified opinions in pages (stable snapshot)."""
    all_rows = []
    page_size = 1000
    offset = 0
    while True:
        result = (
            supabase.table("all_opinions")
            .select("link, case_title, case_number, date_filed, published_status")
            .is_("asylum_related", "null")
            .order("link")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        all_rows.extend(result.data)
        if len(result.data) < page_size:
            break
        offset += page_size
    return all_rows


def upload_chunk(client: storage.Client, chunk: list[dict], job_index: int, total_jobs: int) -> str:
    """Upload a chunk of opinions to GCS. Returns the GCS URI."""
    bucket = client.bucket(GCS_BUCKET)
    blob_name = f"{GCS_PREFIX}/job_{job_index:02d}.json"
    blob = bucket.blob(blob_name)
    blob.upload_from_string(
        json.dumps(chunk, indent=2),
        content_type="application/json",
    )
    uri = f"gs://{GCS_BUCKET}/{blob_name}"
    print(f"  job_{job_index:02d}: {len(chunk):,} rows -> {uri}")
    return uri


def run(num_jobs: int):
    print(f"Fetching all unclassified opinions...")
    supabase = get_client()
    rows = fetch_unclassified(supabase)
    total = len(rows)
    print(f"  Found {total:,} unclassified rows")

    if total == 0:
        print("Nothing to classify.")
        return

    # Divide into equal chunks
    chunk_size = math.ceil(total / num_jobs)
    chunks = [rows[i:i + chunk_size] for i in range(0, total, chunk_size)]
    actual_jobs = len(chunks)
    print(f"  Splitting into {actual_jobs} chunks of ~{chunk_size} rows each")

    gcs_client = storage.Client()
    for i, chunk in enumerate(chunks):
        upload_chunk(gcs_client, chunk, i, actual_jobs)

    print(f"\nDone. Launch {actual_jobs} Cloud Run jobs with:")
    for i in range(actual_jobs):
        print(f"  JOB_INDEX={i:02d}  (reads gs://{GCS_BUCKET}/{GCS_PREFIX}/job_{i:02d}.json)")


def main():
    parser = argparse.ArgumentParser(
        description="Snapshot unclassified rows and split into GCS chunks for parallel jobs"
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=10,
        help="Number of parallel jobs to split work across (default: 10)",
    )
    args = parser.parse_args()
    run(num_jobs=args.jobs)


if __name__ == "__main__":
    main()
