"""Cloud Run entry point for the fetch step."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import fetch


def main():
    print("=" * 60)
    print("Ninth Circuit Pipeline — Fetch")
    print("=" * 60)
    new_count = fetch.fetch_today()
    print(f"Done. Fetched {new_count} new opinions.")
    if new_count == 0:
        print("WARNING: Zero new opinions fetched — possible access issue")


if __name__ == "__main__":
    main()
