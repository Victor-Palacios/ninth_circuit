"""Cloud Run entry point for the daily database backup."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import backup


def main():
    backup.main()


if __name__ == "__main__":
    main()
