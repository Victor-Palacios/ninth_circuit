"""Cloud Run entry point for the backfill step.

Backfills historical opinions from ca9 DynamoDB for a date range.
Reads BACKFILL_START and BACKFILL_END env vars (YYYY-MM-DD).
Only inserts into all_opinions — classify and extract run separately.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import backfill


def main():
    start = os.environ.get("BACKFILL_START", "2025-01-01")
    end = os.environ.get("BACKFILL_END", "2025-12-31")

    print("=" * 60)
    print(f"Ninth Circuit Pipeline — Backfill ({start} to {end})")
    print("=" * 60)

    backfill.backfill(
        start_date=start,
        end_date=end,
        classify_after=False,
        extract_after=False,
    )
    print("Backfill complete. Classify and extract will pick up new rows on their next runs.")


if __name__ == "__main__":
    main()
