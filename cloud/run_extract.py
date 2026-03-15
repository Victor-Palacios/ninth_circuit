"""Cloud Run entry point for the extract step."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import extract


def main():
    print("=" * 60)
    print("Ninth Circuit Pipeline — Extract")
    print("=" * 60)
    extracted_count = extract.run()
    print(f"Done. Extracted {extracted_count} cases.")


if __name__ == "__main__":
    main()
