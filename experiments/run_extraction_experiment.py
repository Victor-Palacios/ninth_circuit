"""Run extraction experiments — extract features 3x per asylum case for reliability testing.

Each run is stored in the extraction_runs table and logged to MLflow.
The experiment runner checks how many runs exist per case and only runs
the missing ones (up to 3 per case).
"""

import argparse
import json
from pathlib import Path

import mlflow

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.supabase_client import get_client
from lib.gemini_client import send_pdf_to_gemini
from pipeline.extract import EXTRACTION_PROMPT

MAX_RUNS = 3
EXPERIMENT_NAME = "asylum-feature-extraction"


def get_cases_needing_runs(supabase, limit: int | None = None) -> list[dict]:
    """Find asylum cases that have fewer than 3 extraction runs."""
    # Get all asylum cases
    cases = supabase.table("asylum_cases").select("link").execute().data

    # Get existing run counts
    runs = supabase.table("extraction_runs").select("link, run_number").execute().data
    run_counts: dict[str, set[int]] = {}
    for r in runs:
        run_counts.setdefault(r["link"], set()).add(r["run_number"])

    # Filter to cases needing more runs
    needing = []
    for case in cases:
        link = case["link"]
        existing = run_counts.get(link, set())
        if len(existing) < MAX_RUNS:
            needing.append({
                "link": link,
                "existing_runs": existing,
            })

    if limit:
        needing = needing[:limit]

    return needing


def run_experiment(limit: int | None = None):
    """Run extraction experiments for cases that need more runs."""
    supabase = get_client()

    mlflow.set_experiment(EXPERIMENT_NAME)

    cases = get_cases_needing_runs(supabase, limit=limit)
    print(f"Found {len(cases)} cases needing extraction runs")

    total_runs = 0
    for i, case in enumerate(cases):
        link = case["link"]
        existing = case["existing_runs"]
        needed = sorted(set(range(1, MAX_RUNS + 1)) - existing)

        print(f"\n[{i + 1}/{len(cases)}] {link}")
        print(f"  Existing runs: {sorted(existing)}, needed: {needed}")

        for run_number in needed:
            print(f"  Running extraction #{run_number}...")

            with mlflow.start_run(run_name=f"case-{i+1}-run-{run_number}"):
                mlflow.log_param("link", link)
                mlflow.log_param("run_number", run_number)
                mlflow.log_param("model", "gemini-2.5-pro")

                try:
                    fields = send_pdf_to_gemini(link, EXTRACTION_PROMPT)

                    # Log metrics
                    field_count = sum(1 for v in fields.values() if v is not None)
                    null_count = sum(1 for v in fields.values() if v is None)
                    mlflow.log_metric("field_count", field_count)
                    mlflow.log_metric("null_count", null_count)

                    # Log the full output as artifact
                    mlflow.log_dict(fields, f"extraction_run_{run_number}.json")

                    # Store in extraction_runs table
                    supabase.table("extraction_runs").upsert({
                        "link": link,
                        "run_number": run_number,
                        "extracted_fields": json.dumps(fields),
                    }, on_conflict="link,run_number").execute()

                    print(f"    -> {field_count} fields extracted")
                    total_runs += 1

                except Exception as e:
                    mlflow.log_param("error", str(e))
                    print(f"    ERROR: {e}")

    print(f"\nExperiment complete. Total runs: {total_runs}")


def main():
    parser = argparse.ArgumentParser(
        description="Run 3x extraction experiments for reliability testing"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of cases to experiment on",
    )
    args = parser.parse_args()
    run_experiment(limit=args.limit)


if __name__ == "__main__":
    main()
