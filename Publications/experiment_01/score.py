"""Score Experiment 1 LLM predictions against the human gold standard.

This is the analysis half of the GitHub-only tracking plan. It joins the LLM
sweep output to the human labels and writes a per-(model, feature) metrics
table plus a human-readable summary. Everything it writes is committed by the
workflow, so each sweep's scores are versioned alongside the raw predictions.

Reads
  Publications/experiment_01/results/features.csv   LLM predictions (long format,
                                                     written by extract_features.py)
  Publications/experiment_02/results/labels.csv      human gold standard (optional)

Writes
  Publications/experiment_01/results/metrics.csv     per (model, feature) scores
  Publications/experiment_01/results/summary.md      human-readable report + provenance

Human gold-standard format
  The labeling spreadsheet is WIDE: one row per case with a `link` (or `case_id`)
  column plus one true/false column per feature. It is melted to long and joined
  to the predictions on the opinion URL (`link` <-> `pdf_url`). A long-format
  labels file (columns: link|case_id, feature, truth) is also accepted.

No sklearn: accuracy, precision/recall/F1 and Cohen's kappa are computed directly
so the workflow only needs pandas (already installed for the sweep).

Usage
  python Publications/experiment_01/score.py [--github-summary]

If the gold standard is not present yet (Experiment 2 still in progress) the
script still runs and emits prediction-only diagnostics (true-rate, latency,
error rate) so the tracking loop is useful before labeling is complete.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

EXP_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]

FEATURES_CSV = EXP_DIR / "results" / "features.csv"
LABELS_CSV = REPO_ROOT / "Publications" / "experiment_02" / "results" / "labels.csv"
METRICS_CSV = EXP_DIR / "results" / "metrics.csv"
SUMMARY_MD = EXP_DIR / "results" / "summary.md"

# Mirrors the 11 features in extract_features.py / the Experiment 2 codebook.
FEATURE_NAMES = [
    "asylum_requested",
    "withholding_requested",
    "CAT_requested",
    "protected_ground_political_opinion",
    "protected_ground_particular_social_group",
    "past_persecution_physical_violence",
    "past_persecution_death_threats",
    "persecutor_nongovernmental_actor",
    "credibility_finding",
    "bars_one_year_deadline_missed",
    "nexus_requirement_met",
]

_TRUE = {"true", "t", "yes", "y", "1"}
_FALSE = {"false", "f", "no", "n", "0"}


def to_bool(value) -> bool | None:
    """Normalize true/false from bool, int, or string; blanks/unknowns -> None."""
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if pd.isna(value):
            return None
        return bool(int(value))
    s = str(value).strip().lower()
    if s in _TRUE:
        return True
    if s in _FALSE:
        return False
    return None


def git_sha() -> str:
    sha = os.environ.get("GITHUB_SHA")
    if sha:
        return sha[:12]
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()[:12]
    except Exception:
        return "unknown"


def load_predictions() -> pd.DataFrame:
    if not FEATURES_CSV.exists():
        raise SystemExit(f"No predictions found at {FEATURES_CSV}. Run extract_features.py first.")
    df = pd.read_csv(FEATURES_CSV)
    df["error"] = df["error"].fillna("")
    df["pred"] = df["predicted"].map(to_bool)
    return df


def load_gold() -> pd.DataFrame | None:
    """Return long-format gold (columns: link, feature, truth) or None if absent."""
    if not LABELS_CSV.exists():
        return None
    raw = pd.read_csv(LABELS_CSV)
    cols = {c.lower(): c for c in raw.columns}

    # Long format already?
    if "feature" in cols and "truth" in cols:
        key = cols.get("link") or cols.get("pdf_url") or cols.get("case_id")
        out = raw.rename(columns={cols["feature"]: "feature", cols["truth"]: "truth", key: "link"})
        out = out[["link", "feature", "truth"]].copy()
    else:
        # Wide format: one row per case, one column per feature.
        key = cols.get("link") or cols.get("pdf_url") or cols.get("case_id")
        if key is None:
            raise SystemExit("Gold labels need a `link`, `pdf_url`, or `case_id` column.")
        present = [f for f in FEATURE_NAMES if f in raw.columns]
        if not present:
            raise SystemExit("Gold labels contain none of the 11 feature columns.")
        out = raw.melt(id_vars=[key], value_vars=present,
                       var_name="feature", value_name="truth")
        out = out.rename(columns={key: "link"})

    out["truth"] = out["truth"].map(to_bool)
    out = out.dropna(subset=["truth"])
    return out


def confusion(paired: pd.DataFrame) -> dict:
    """paired has boolean columns `pred` and `truth`. Positive class = True."""
    tp = int(((paired["pred"]) & (paired["truth"])).sum())
    fp = int(((paired["pred"]) & (~paired["truth"])).sum())
    fn = int(((~paired["pred"]) & (paired["truth"])).sum())
    tn = int(((~paired["pred"]) & (~paired["truth"])).sum())
    n = tp + fp + fn + tn
    acc = (tp + tn) / n if n else 0.0
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    # Cohen's kappa (LLM vs human) for a 2x2 table.
    po = acc
    p_pred_pos = (tp + fp) / n if n else 0.0
    p_truth_pos = (tp + fn) / n if n else 0.0
    pe = p_pred_pos * p_truth_pos + (1 - p_pred_pos) * (1 - p_truth_pos)
    kappa = (po - pe) / (1 - pe) if (1 - pe) else 1.0
    return dict(n=n, tp=tp, fp=fp, fn=fn, tn=tn,
                accuracy=round(acc, 3), precision=round(prec, 3),
                recall=round(rec, 3), f1=round(f1, 3), cohen_kappa=round(kappa, 3))


def per_call(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (case_id, model) call — for latency and error diagnostics."""
    return df.drop_duplicates(subset=["case_id", "model"])[
        ["case_id", "model", "latency_ms", "error"]
    ]


def model_health(df: pd.DataFrame, model: str) -> dict:
    calls = per_call(df[df["model"] == model])
    n_calls = len(calls)
    n_err = int((calls["error"] != "").sum())
    ok = calls[calls["error"] == ""]
    mean_lat = int(ok["latency_ms"].mean()) if len(ok) else 0
    return dict(calls=n_calls, errors=n_err,
                error_rate=round(n_err / n_calls, 3) if n_calls else 0.0,
                mean_latency_ms=mean_lat)


def build_scored(df: pd.DataFrame, gold: pd.DataFrame) -> pd.DataFrame:
    ok = df[(df["error"] == "") & df["pred"].notna()].copy()
    merged = ok.merge(gold, left_on=["pdf_url", "feature"],
                      right_on=["link", "feature"], how="inner")
    rows = []
    for (model, feature), grp in merged.groupby(["model", "feature"]):
        row = {"model": model, "feature": feature}
        row.update(confusion(grp[["pred", "truth"]]))
        rows.append(row)
    return pd.DataFrame(rows)


def build_prediction_only(df: pd.DataFrame) -> pd.DataFrame:
    ok = df[(df["error"] == "") & df["pred"].notna()]
    rows = []
    for (model, feature), grp in ok.groupby(["model", "feature"]):
        n = len(grp)
        rows.append({
            "model": model, "feature": feature, "n": n,
            "true_rate": round(grp["pred"].mean(), 3) if n else 0.0,
        })
    return pd.DataFrame(rows)


def md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_(no rows)_\n"
    header = "| " + " | ".join(df.columns) + " |"
    sep = "| " + " | ".join("---" for _ in df.columns) + " |"
    lines = [header, sep]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(v) for v in r.values) + " |")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--github-summary", action="store_true",
                    help="Also append the report to $GITHUB_STEP_SUMMARY.")
    args = ap.parse_args()

    df = load_predictions()
    gold = load_gold()
    models = sorted(df["model"].unique())
    n_cases = df["case_id"].nunique()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    parts: list[str] = []
    parts.append("# Experiment 1 — sweep results\n")
    parts.append(
        f"- **Scored:** {now}\n"
        f"- **Commit:** `{git_sha()}` (this SHA pins the exact prompt + feature definitions)\n"
        f"- **Cases:** {n_cases}    **Models:** {len(models)}    "
        f"**Gold standard:** {'present' if gold is not None else 'NOT YET AVAILABLE'}\n"
    )

    # Operational health (always available).
    health = pd.DataFrame([{"model": m, **model_health(df, m)} for m in models])
    parts.append("\n## Model health (per full sweep)\n\n" + md_table(health))

    if gold is not None:
        scored = build_scored(df, gold)
        scored.to_csv(METRICS_CSV, index=False)
        parts.append("\n## Accuracy vs. human gold standard (per model × feature)\n\n"
                     + md_table(scored.sort_values(["model", "feature"])))
        # Per-model macro averages.
        agg = (scored.groupby("model")[["accuracy", "f1", "cohen_kappa"]]
               .mean().round(3).reset_index()
               .rename(columns={"accuracy": "macro_accuracy",
                                "f1": "macro_f1", "cohen_kappa": "macro_kappa"}))
        parts.append("\n## Per-model macro averages\n\n" + md_table(agg))
    else:
        pred_only = build_prediction_only(df)
        pred_only.to_csv(METRICS_CSV, index=False)
        parts.append(
            "\n## Prediction-only diagnostics (no gold standard yet)\n\n"
            "The human gold standard (`Publications/experiment_02/results/labels.csv`) is "
            "not present, so accuracy/F1/kappa cannot be computed. Showing the per-feature "
            "true-rate for each model instead.\n\n"
            + md_table(pred_only.sort_values(["model", "feature"])))

    report = "\n".join(parts)
    SUMMARY_MD.write_text(report, encoding="utf-8")
    print(f"Wrote {METRICS_CSV.relative_to(REPO_ROOT)} and {SUMMARY_MD.relative_to(REPO_ROOT)}")

    if args.github_summary:
        step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if step_summary:
            with open(step_summary, "a", encoding="utf-8") as fh:
                fh.write(report + "\n")


if __name__ == "__main__":
    main()
