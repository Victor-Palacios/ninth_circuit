"""Cloud Run entry point for the classify step."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import classify


def main():
    print("=" * 60)
    print("Ninth Circuit Pipeline — Classify")
    print("=" * 60)
    classified_count = classify.run()
    print(f"Done. Classified {classified_count} opinions.")


if __name__ == "__main__":
    main()
