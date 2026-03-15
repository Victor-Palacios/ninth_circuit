"""Cloud Run entry point for batch classify (temporary backfill use)."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import classify_batch


def main():
    offset = int(os.environ.get("BATCH_OFFSET", "0"))
    size = int(os.environ.get("BATCH_SIZE", "300"))
    print("=" * 60)
    print(f"Ninth Circuit Pipeline — Classify Batch (offset={offset}, size={size})")
    print("=" * 60)
    classify_batch.run(offset=offset, size=size)


if __name__ == "__main__":
    main()
