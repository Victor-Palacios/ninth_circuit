"""Batch classify for parallel backfill processing.

Temporary script for bulk classification. Fetches a fixed slice of
unclassified opinions ordered by link (stable), so 10 parallel jobs
can each work on non-overlapping rows.

Reads env vars:
  BATCH_OFFSET  — row index to start from (default 0)
  BATCH_SIZE    — number of rows to process (default 300)

Usage (local):
  BATCH_OFFSET=0    BATCH_SIZE=300 python -m pipeline.classify_batch
  BATCH_OFFSET=300  BATCH_SIZE=300 python -m pipeline.classify_batch
  ...

On Cloud Run, trigger 10 executions with different BATCH_OFFSET values.
This script is temporary — the regular classify.py handles daily runs.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.supabase_client import get_client
from lib.gemini_client import send_pdf_to_gemini
from pipeline.classify import CLASSIFICATION_PROMPT, classify_opinion, insert_into_asylum_cases


def fetch_batch(supabase, offset: int, size: int) -> list[dict]:
    """Fetch a stable slice of unclassified opinions ordered by link."""
    result = (
        supabase.table("all_opinions")
        .select("link, case_title, case_number, date_filed, published_status")
        .is_("asylum_related", "null")
        .order("link")
        .range(offset, offset + size - 1)
        .execute()
    )
    return result.data


def run(offset: int, size: int) -> int:
    """Classify a batch of opinions. Returns count classified."""
    supabase = get_client()
    pending = fetch_batch(supabase, offset, size)

    print(f"Batch offset={offset}, size={size}: fetched {len(pending)} rows")
    classified = 0

    for i, opinion in enumerate(pending):
        link = opinion["link"]
        print(f"[{offset + i + 1}] {opinion.get('case_title', link)}")

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

    print(f"Batch done. Classified {classified}/{len(pending)} opinions.")
    return classified


def main():
    offset = int(os.environ.get("BATCH_OFFSET", "0"))
    size = int(os.environ.get("BATCH_SIZE", "300"))
    run(offset=offset, size=size)


if __name__ == "__main__":
    main()
