import argparse
import csv
import os
from typing import List, Dict, Any


DEFAULT_ROOT_DIR = "."
DEFAULT_ASYLUM_SUBDIR = "asylum"
DEFAULT_OUTPUT_CSV = "asylum_features.csv"


def collect_asylum_files(root_dir: str, asylum_subdir: str) -> List[str]:
    """
    Return a sorted list of full paths to .txt files in **all** matching
    asylum subdirectories under root_dir.

    This walks the tree rooted at root_dir and collects .txt files from every
    directory whose basename equals asylum_subdir (for example, 'asylum').
    """
    root_dir_abs = os.path.abspath(root_dir)

    files: List[str] = []
    for current_dir, _, filenames in os.walk(root_dir_abs):
        if os.path.basename(current_dir) != asylum_subdir:
            continue

        for entry in sorted(filenames):
            if entry.lower().endswith(".txt"):
                files.append(os.path.join(current_dir, entry))

    if not files:
        raise FileNotFoundError(
            f"No '{asylum_subdir}' directories with .txt files found under: {root_dir_abs}"
        )

    return sorted(files)


def parse_metadata_from_filename(file_name: str) -> Dict[str, Any]:
    """
    Extract published status, date, and docket number from the filename.

    Expected pattern (created by fetch_ca9_text_split_claude.sh):
        <STATUS>_<DATE>_<DOCKET>_<OPINION_ID>.txt

    Example:
        Published_2025-12-22_23-1095_11229626.txt
        Unpublished_2025-12-22_25-2796_11229652.txt

    If the pattern does not match, fields are returned as empty strings.
    """
    base = os.path.splitext(file_name)[0]
    parts = base.split("_")

    status = parts[0] if len(parts) >= 1 else ""
    date_filed = parts[1] if len(parts) >= 2 else ""
    docket_no = parts[2] if len(parts) >= 3 else ""

    return {
        "published_status": status,
        "date_filed": date_filed,
        "docket_no": docket_no,
    }


def build_feature_rows(file_paths: List[str], root_dir: str) -> List[Dict[str, Any]]:
    """
    Build a row per opinion with:
      - file_name
      - file_path (relative to root_dir)
      - published_status
      - date_filed
      - docket_no
      - char_count (number of characters in the file)
    """
    rows: List[Dict[str, Any]] = []
    root_dir_abs = os.path.abspath(root_dir)

    for path in file_paths:
        file_name = os.path.basename(path)
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except Exception as exc:
            # Skip files that cannot be read but surface a message for debugging.
            print(f"Failed to read {path}: {exc}")
            continue

        try:
            rel_path = os.path.relpath(path, root_dir_abs)
        except ValueError:
            rel_path = path

        meta = parse_metadata_from_filename(file_name)

        row: Dict[str, Any] = {
            "file_name": file_name,
            "file_path": rel_path,
            "published_status": meta["published_status"],
            "date_filed": meta["date_filed"],
            "docket_no": meta["docket_no"],
            "char_count": len(text),
        }
        rows.append(row)

    return rows


def write_csv(rows: List[Dict[str, Any]], output_path: str) -> None:
    """
    Write rows to a CSV file suitable for Supabase import (also Excel-friendly).
    """
    if not rows:
        print("No rows to write; CSV will not be created.")
        return

    fieldnames = [
        "file_name",
        "file_path",
        "published_status",
        "date_filed",
        "docket_no",
        "char_count",
    ]

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} row(s) to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Extract basic features from CA9 asylum opinions "
            "into a CSV for downstream analysis or Supabase import."
        )
    )
    parser.add_argument(
        "--root-dir",
        default=DEFAULT_ROOT_DIR,
        help=f"Root directory containing the opinions (default: {DEFAULT_ROOT_DIR!r}).",
    )
    parser.add_argument(
        "--asylum-subdir",
        default=DEFAULT_ASYLUM_SUBDIR,
        help=f"Subdirectory under root containing asylum cases (default: {DEFAULT_ASYLUM_SUBDIR!r}).",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_CSV,
        help=(
            "Output CSV filename (default: "
            f"{DEFAULT_OUTPUT_CSV!r}, written in the current working directory)."
        ),
    )

    args = parser.parse_args()

    files = collect_asylum_files(args.root_dir, args.asylum_subdir)
    if not files:
        print("No .txt files found in the specified asylum directory.")
        return

    print(f"Found {len(files)} asylum .txt file(s) under {args.root_dir!r}.")
    rows = build_feature_rows(files, args.root_dir)
    write_csv(rows, args.output)


if __name__ == "__main__":
    main()