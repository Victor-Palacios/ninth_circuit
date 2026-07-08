"""
Sample 30 asylum cases seeded for reproducibility.

Sampling plan (per publication group × 2 = 30 total):
  Denied   × 4
  Remanded × 4
  Granted  × 4
  Random   × 3  (any canonical label except Denied / Remanded / Granted)

Outputs:
  reports/sample_30_cases.txt        human-readable
  Publications/sample_30_cases.csv   tabular (shared by the Publications experiments)
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from lib.supabase_client import get_client

SEED = 7
REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "reports"
OUT_DIR.mkdir(exist_ok=True)
# The canonical tabular sample lives with the Publications experiments (exp 01 + 02);
# the human-readable .txt companion stays under reports/.
PUB_DIR = REPO_ROOT / "Publications"
PUB_DIR.mkdir(exist_ok=True)

# ── Canonicalization (mirrors normalize_final_disposition.py) ─────────────────

CANON_ORDER = ["Affirmed", "Denied", "Dismissed", "Granted", "Remanded", "Reversed", "Vacated"]

OVERRIDES: dict[str, str] = {
    "(no evidence)":                                                    "Not Determined",
    "Not determined":                                                   "Not Determined",
    "Not determined.":                                                  "Not Determined",
    "Pending":                                                          "Pending",
    "Stayed":                                                           "Stayed",
    "Abeyance":                                                         "Abeyance",
    "Certified questions to Arizona Supreme Court":                     "Certified Question",
    "Rehearing en banc ordered":                                        "Reheard En Banc",
    "Reheard en banc":                                                  "Reheard En Banc",
    "Petition for Rehearing Denied as Moot":                            "Denied",
    "Conviction affirmed":                                              "Affirmed",
    "Stay of injunction denied":                                        "Denied",
    "Partial grant and partial denial of the Government's request for a stay": "Denied; Granted",
    "Orozco-Lopez's petition is granted and remanded, while Gonzalez's is denied.":
        "Denied; Granted; Remanded",
    "Remanded for a new hearing as to Rivera-Recinos and Denied as to Recinos-Ulloa":
        "Denied; Remanded",
    "Petition denied in 23-358, and petition granted in 23-855":        "Denied; Granted",
    "Denied as to Zuliema Dolores Guerrero-Esperanza, Granted as to Daniel Enrique Vasquez-Guerrero; Remanded":
        "Denied; Granted; Remanded",
    "Remanded for further proceedings":                                 "Remanded",
    "Remanded with instructions":                                       "Remanded",
    "Remanded with instructions to terminate proceedings":              "Remanded",
    "Remanded with instructions to grant CAT relief":                   "Remanded",
}

KEYWORD_PATTERNS: list[tuple[str, str]] = [
    (r"\baffirm",  "Affirmed"),
    (r"\bdeni",    "Denied"),
    (r"\bdismiss", "Dismissed"),
    (r"\bgrant",   "Granted"),
    (r"\bremand",  "Remanded"),
    (r"\brevers",  "Reversed"),
    (r"\bvacat",   "Vacated"),
]


def canonicalize(raw: str) -> str:
    s = raw.strip()
    if s in OVERRIDES:
        return OVERRIDES[s]
    found: set[str] = set()
    for pattern, label in KEYWORD_PATTERNS:
        if re.search(pattern, s.lower()):
            found.add(label)
    if found:
        return "; ".join(sorted(found, key=lambda x: (CANON_ORDER.index(x) if x in CANON_ORDER else 99, x)))
    return f"Other: {s}"


# ── Data fetch ────────────────────────────────────────────────────────────────

def fetch_all() -> pd.DataFrame:
    client = get_client()
    rows, offset = [], 0
    while True:
        batch = (
            client.table("asylum_cases")
            .select("link, published_status, final_disposition, char_count")
            .range(offset, offset + 999)
            .execute()
            .data
        )
        if not batch:
            break
        rows.extend(batch)
        offset += 1000
    df = pd.DataFrame(rows)
    df["canonical"] = df["final_disposition"].fillna("").apply(
        lambda x: canonicalize(x) if x else "Not Determined"
    )
    return df


# ── Sampling ──────────────────────────────────────────────────────────────────

PRIMARY = ["Denied", "Remanded", "Granted"]
PLAN = [("Denied", 4), ("Remanded", 4), ("Granted", 4), ("Random", 3)]


def sample_group(df: pd.DataFrame, rng: np.random.Generator, label: str) -> pd.DataFrame:
    """Sample cases for a single publication-status group."""
    parts: list[pd.DataFrame] = []
    for canon_label, n in PLAN:
        if canon_label == "Random":
            pool = df[~df["canonical"].isin(PRIMARY)]
        else:
            pool = df[df["canonical"] == canon_label]

        available = len(pool)
        if available < n:
            print(f"  WARNING [{label}] '{canon_label}': only {available} available, taking all")
            n = available

        seed_i = int(rng.integers(0, 2**31))
        sampled = pool.sample(n=n, random_state=seed_i)
        sampled = sampled.copy()
        sampled["sample_group"] = "Random (other)" if canon_label == "Random" else canon_label
        parts.append(sampled)

    return pd.concat(parts).reset_index(drop=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    rng = np.random.default_rng(SEED)

    df = fetch_all()

    pub   = df[df["published_status"] == "Published"].copy()
    unpub = df[df["published_status"] == "Unpublished"].copy()

    pub_sample   = sample_group(pub,   rng, "Published")
    pub_sample["pub_status"] = "Published"

    unpub_sample = sample_group(unpub, rng, "Unpublished")
    unpub_sample["pub_status"] = "Unpublished"

    combined = pd.concat([pub_sample, unpub_sample]).reset_index(drop=True)
    combined.index += 1

    # ── .txt output ───────────────────────────────────────────────────────────
    lines: list[str] = [
        f"SAMPLE OF 30 ASYLUM CASES  (seed={SEED})",
        "=" * 120,
        f"{'#':<4} {'Status':<13} {'Sample Group':<16} {'Canonical Label':<38} {'Chars':>8}   Link",
        "-" * 150,
    ]

    for pub_status in ["Published", "Unpublished"]:
        sub = combined[combined["pub_status"] == pub_status]
        lines.append(f"\n── {pub_status} ({'─' * 110})")
        for i, row in sub.iterrows():
            cc = f"{int(row['char_count']):,}" if pd.notna(row["char_count"]) else "N/A"
            lines.append(
                f"{i:<4} {row['pub_status']:<13} {row['sample_group']:<16} "
                f"{row['canonical']:<38} {cc:>8}   {row['link']}"
            )

    lines += [
        "",
        "=" * 120,
        "BREAKDOWN",
        "=" * 120,
    ]
    for pub_status in ["Published", "Unpublished"]:
        sub = combined[combined["pub_status"] == pub_status]
        lines.append(f"\n{pub_status}:")
        for grp_label, grp in sub.groupby("sample_group", sort=False):
            lines.append(f"  {grp_label:<20} {len(grp)} cases")

    lines += [
        "",
        f"Total: {len(combined)} cases",
        f"Seed : {SEED}",
    ]

    txt_path = OUT_DIR / "sample_30_cases.txt"
    txt_path.write_text("\n".join(lines), encoding="utf-8")

    # ── .csv output ───────────────────────────────────────────────────────────
    csv_out = combined[["pub_status", "sample_group", "canonical", "final_disposition", "char_count", "link"]].copy()
    csv_out.index.name = "n"
    csv_path = PUB_DIR / "sample_30_cases.csv"
    csv_out.to_csv(csv_path)

    print(f"Saved → {txt_path}")
    print(f"Saved → {csv_path}")
    print(f"Total : {len(combined)} cases  |  Seed: {SEED}")


if __name__ == "__main__":
    main()
