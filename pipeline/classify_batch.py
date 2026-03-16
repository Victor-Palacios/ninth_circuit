"""Batch classify using pre-assigned GCS chunks (Strategy 1).

Each job reads its assigned chunk from GCS — a snapshot of unclassified
links created by classify_coordinator.py before any jobs launch. Because
the work is pre-divided from a static snapshot, there is no offset race
condition: jobs work on non-overlapping, fixed sets of rows regardless
of how other jobs update the DB.

Reads env vars:
  JOB_INDEX  — zero-padded index of the chunk file to process (e.g. "03")

GCS chunk files are written by classify_coordinator.py to:
  gs://th-circuit-backups/classify-batches/job_<JOB_INDEX>.json

Usage (local):
  JOB_INDEX=00 python -m pipeline.classify_batch
  JOB_INDEX=01 python -m pipeline.classify_batch
  ...

On Cloud Run, trigger one execution per chunk with different JOB_INDEX values.
This script is temporary — the regular classify.py handles daily runs.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from google.cloud import storage

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.supabase_client import get_client
from pipeline.classify import classify_opinion, insert_into_asylum_cases


GCS_BUCKET = "th-circuit-backups"
GCS_PREFIX = "classify-batches"


def fetch_chunk_from_gcs(job_index: str) -> list[dict]:
    """Download the pre-assigned chunk for this job from GCS."""
    client = storage.Client()
    blob_name = f"{GCS_PREFIX}/job_{job_index}.json"
    blob = client.bucket(GCS_BUCKET).blob(blob_name)
    data = blob.download_as_text()
    return json.loads(data)


def run(job_index: str) -> int:
    """Classify this job's pre-assigned opinions. Returns count classified."""
    print(f"Loading chunk: gs://{GCS_BUCKET}/{GCS_PREFIX}/job_{job_index}.json")
    opinions = fetch_chunk_from_gcs(job_index)
    print(f"  Loaded {len(opinions):,} opinions to classify")

    supabase = get_client()
    classified = 0

    for i, opinion in enumerate(opinions):
        link = opinion["link"]
        print(f"[{i + 1}/{len(opinions)}] {opinion.get('case_title', link)}")

        try:
            is_asylum = classify_opinion(link)
            now = datetime.now(timezone.utc).isoformat()

            supabase.table("all_opinions").update({
                "asylum_related": is_asylum,
                "classified_at": now,
            }).eq("link", link).execute()

            if is_asylum:
                insert_into_asylum_cases(supabase, opinion)
                print(f"  -> asylum-related")
            else:
                print(f"  -> not asylum-related")

            classified += 1

        except json.JSONDecodeError as e:
            print(f"  ERROR: invalid JSON from Gemini: {e}")
        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"Batch done. Classified {classified}/{len(opinions)} opinions.")
    return classified


def main():
    job_index = os.environ.get("JOB_INDEX", "00")
    run(job_index=job_index)


if __name__ == "__main__":
    main()
