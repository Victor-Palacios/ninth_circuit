"""Cloud Run entry point — orchestrates the daily pipeline.

Steps:
  1. Fetch new opinions from ca9.uscourts.gov
  2. Classify unclassified opinions as asylum-related or not
  3. Extract features from new asylum cases
"""

import sys
from pathlib import Path

# Add project root to path so pipeline/ and lib/ are importable
# In Docker container: main.py is at /app/main.py, lib/ and pipeline/ at /app/
# Locally (cloud/main.py): parent.parent is the project root
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import fetch, classify, extract


def main():
    print("=" * 60)
    print("Ninth Circuit Asylum Pipeline — Daily Run")
    print("=" * 60)

    # Step 1: Fetch new opinions
    print("\n--- Step 1: Fetch ---")
    new_count = fetch.fetch_today()

    # Step 2: Classify
    print("\n--- Step 2: Classify ---")
    classified_count = classify.run()

    # Step 3: Extract features
    print("\n--- Step 3: Extract ---")
    extracted_count = extract.run()

    # Summary
    print("\n" + "=" * 60)
    print(f"Done. Fetched {new_count}, classified {classified_count}, extracted {extracted_count}")
    print("=" * 60)

    # Exit with error code if nothing was fetched (possible access cutoff)
    if new_count == 0:
        print("WARNING: Zero new opinions fetched — possible access issue")


if __name__ == "__main__":
    main()
