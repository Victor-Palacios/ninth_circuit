"""Compare extraction runs across 3x experiments to measure reliability.

Queries extraction_runs for cases with all 3 runs and computes
per-field agreement rates.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.supabase_client import get_client


def get_completed_experiments(supabase) -> dict[str, list[dict]]:
    """Get cases with all 3 extraction runs, grouped by link."""
    runs = supabase.table("extraction_runs").select("*").execute().data

    grouped: dict[str, list[dict]] = defaultdict(list)
    for run in runs:
        grouped[run["link"]].append(run)

    # Keep only cases with all 3 runs
    return {
        link: sorted(runs, key=lambda r: r["run_number"])
        for link, runs in grouped.items()
        if len(runs) >= 3
    }


def compute_agreement(experiments: dict[str, list[dict]]) -> dict:
    """Compute per-field agreement rates across 3 runs.

    Returns a dict of {field_name: agreement_rate} where agreement_rate
    is the fraction of cases where all 3 runs agree on the value.
    """
    field_agreements: dict[str, list[bool]] = defaultdict(list)

    for link, runs in experiments.items():
        fields_per_run = []
        for run in runs:
            raw = run.get("extracted_fields", "{}")
            if isinstance(raw, str):
                fields_per_run.append(json.loads(raw))
            else:
                fields_per_run.append(raw)

        if len(fields_per_run) < 3:
            continue

        # Check each field across the 3 runs
        all_keys = set()
        for f in fields_per_run:
            all_keys.update(f.keys())

        for key in all_keys:
            values = [f.get(key) for f in fields_per_run]
            # All 3 runs agree if all values are the same
            agrees = len(set(str(v) for v in values)) == 1
            field_agreements[key].append(agrees)

    # Compute rates
    rates = {}
    for field, agreements in sorted(field_agreements.items()):
        rate = sum(agreements) / len(agreements) if agreements else 0
        rates[field] = round(rate, 3)

    return rates


def main():
    parser = argparse.ArgumentParser(
        description="Compare extraction runs and compute agreement rates"
    )
    parser.add_argument(
        "--min-rate",
        type=float,
        default=0.0,
        help="Only show fields with agreement rate >= this value",
    )
    args = parser.parse_args()

    supabase = get_client()
    experiments = get_completed_experiments(supabase)

    if not experiments:
        print("No cases with 3 completed runs found.")
        return

    print(f"Analyzing {len(experiments)} cases with 3 runs each\n")

    rates = compute_agreement(experiments)

    # Print results sorted by agreement rate
    print(f"{'Field':<55} {'Agreement':>10}")
    print("-" * 67)

    for field, rate in sorted(rates.items(), key=lambda x: x[1], reverse=True):
        if rate >= args.min_rate:
            bar = "#" * int(rate * 20)
            print(f"{field:<55} {rate:>8.1%}  {bar}")

    # Summary
    avg_rate = sum(rates.values()) / len(rates) if rates else 0
    high = sum(1 for r in rates.values() if r >= 0.9)
    low = sum(1 for r in rates.values() if r < 0.7)
    print(f"\nOverall average agreement: {avg_rate:.1%}")
    print(f"Fields with >= 90% agreement: {high}/{len(rates)}")
    print(f"Fields with < 70% agreement: {low}/{len(rates)}")


if __name__ == "__main__":
    main()
