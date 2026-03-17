"""Daily backup of asylum_cases to Hugging Face Datasets.

Pushes a full JSON snapshot to:
  https://huggingface.co/datasets/<HF_REPO>/asylum_cases.json

The dataset repo's git history serves as version control — every daily
push is a new commit, so any snapshot can be recovered. No lifecycle
policy needed; Hugging Face keeps all history indefinitely for free.

Required env vars:
  HF_TOKEN   — Hugging Face write token (from hf.co/settings/tokens)
  HF_REPO    — Dataset repo in "owner/name" format (e.g. "vpalacios/ninth-circuit")
"""

import json
import os
from datetime import datetime, timezone

from huggingface_hub import HfApi

from lib.supabase_client import get_client


def fetch_all_asylum_cases(supabase) -> list[dict]:
    """Fetch all rows from asylum_cases in pages."""
    all_rows = []
    page_size = 1000
    offset = 0
    while True:
        result = (
            supabase.table("asylum_cases")
            .select("*")
            .order("date_filed", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        all_rows.extend(result.data)
        if len(result.data) < page_size:
            break
        offset += page_size
    return all_rows


def run():
    """Run the backup."""
    hf_token = os.environ["HF_TOKEN"]
    hf_repo = os.environ["HF_REPO"]

    supabase = get_client()
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    print(f"Fetching all asylum cases...")
    rows = fetch_all_asylum_cases(supabase)
    print(f"  Fetched {len(rows):,} rows")

    payload = json.dumps(rows, indent=2).encode("utf-8")

    api = HfApi(token=hf_token)

    # Ensure the dataset repo exists (no-op if already created)
    api.create_repo(repo_id=hf_repo, repo_type="dataset", exist_ok=True)

    # Upload snapshot — overwrites the file; HF git history preserves old versions
    api.upload_file(
        path_or_fileobj=payload,
        path_in_repo="asylum_cases.json",
        repo_id=hf_repo,
        repo_type="dataset",
        commit_message=f"Daily backup {date_str} ({len(rows):,} rows)",
    )

    hf_url = f"https://huggingface.co/datasets/{hf_repo}/blob/main/asylum_cases.json"
    print(f"  Uploaded to {hf_url}")
    print("Backup complete.")

    summary_file = os.environ.get("BACKUP_SUMMARY_FILE")
    if summary_file:
        with open(summary_file, "w") as f:
            f.write(f"Backed up {len(rows):,} rows to {hf_url}\n")


def main():
    print("=" * 60)
    print("Ninth Circuit — Database Backup")
    print("=" * 60)
    run()


if __name__ == "__main__":
    main()
