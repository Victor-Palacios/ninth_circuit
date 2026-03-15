"""Cloud Run entry point for the daily QA check."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import qa_check


def main():
    qa_check.main()


if __name__ == "__main__":
    main()
