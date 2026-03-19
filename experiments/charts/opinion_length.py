"""
Generate the Opinion Length Distribution chart for the README.

Usage:
    set -a && source .env && set +a && source ninthc/bin/activate
    python3 experiments/charts/opinion_length.py

Output: assets/char_count_distribution.png
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from lib.supabase_client import get_client

BG = "#f7f7f7"
plt.rcParams["font.family"] = "DejaVu Sans"

CAP = 10000
OUT = Path(__file__).resolve().parent.parent.parent / "assets" / "char_count_distribution.png"


def main():
    supabase = get_client()
    result = (
        supabase.table("asylum_cases")
        .select("char_count")
        .not_.is_("char_count", "null")
        .execute()
    )
    char_counts = [r["char_count"] for r in result.data]
    print(f"Loaded {len(char_counts):,} cases with char_count")

    n_over = sum(1 for c in char_counts if c > CAP)
    under_9k = [c for c in char_counts if c <= 9000]

    mean_val = sum(char_counts) / len(char_counts)
    median_val = sorted(char_counts)[len(char_counts) // 2]

    bins = np.linspace(0, 9000, 10)

    fig, ax = plt.subplots(figsize=(9, 5))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    counts, edges, _ = ax.hist(under_9k, bins=bins, color="#30a2da", edgecolor=BG, linewidth=0.5)

    # Overflow bin — lighter color, distinct from real data
    ymax = max(max(counts), n_over)
    ax.bar(9500, n_over, width=800, color="#a8d4ed", edgecolor=BG, linewidth=0.5)
    ax.text(9500, n_over + ymax * 0.01, f">10k\n(n={n_over})",
            ha="center", va="bottom", fontsize=8.5, color="#555555", fontweight="bold")

    def bar_height(val):
        idx = np.searchsorted(edges, val, side="right") - 1
        idx = min(max(idx, 0), len(counts) - 1)
        return counts[idx]

    mean_h = bar_height(mean_val)
    med_h  = bar_height(median_val)

    # Lines clipped to bar top; labels sit above with bottom of "M" flush with line top
    ax.axvline(mean_val,   ymin=0, ymax=mean_h / ymax, color="#a50026", linewidth=1.5)
    ax.axvline(median_val, ymin=0, ymax=med_h  / ymax, color="#373737", linewidth=1.5)

    ax.text(mean_val - 120,   mean_h, f"Mean\n{mean_val:,.0f}",
            ha="right", va="bottom", fontsize=9.5, fontweight="bold", color="#a50026")
    ax.text(median_val + 120, med_h,  f"Median\n{median_val:,.0f}",
            ha="left",  va="bottom", fontsize=9.5, fontweight="bold", color="#373737")

    ax.set_xlabel("Character count", fontsize=12, color="#373737")
    ax.set_ylabel("Number of opinions", fontsize=12, color="#373737")
    ax.set_title("Distribution of Opinion Length — Ninth Circuit Asylum Cases",
                 fontsize=15, fontweight="bold", color="#373737")

    ax.set_xlim(0, 10500)
    ax.set_xticks(list(range(0, 9001, 1000)) + [9500])
    ax.set_xticklabels([f"{x:,}" for x in range(0, 9001, 1000)] + [">10k"],
                       fontsize=9, color="#373737")
    ax.tick_params(axis="both", length=0, labelsize=9, colors="#373737")

    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(False)

    fig.text(0.95, 0.01, f"n = {len(char_counts):,} asylum cases",
             ha="right", fontsize=8.5, color="#8b8b8b")

    plt.tight_layout()
    plt.savefig(OUT, dpi=180, bbox_inches="tight", facecolor=BG)
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()
