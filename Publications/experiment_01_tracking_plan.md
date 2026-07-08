# Experiment 1 — Results-Tracking Plan (Executive Summary)

**Author:** Victor Palacios · **Date:** 2026-07-08
**Scope:** How to record, version, compare, and analyze the results of Experiment 1
(`Publications/experiment_01/`).

---

## TL;DR

Experiment 1 probes **3 NVIDIA NIM models** on **11 binary features** across the **30
curated Ninth Circuit asylum opinions** in
[`Publications/sample_30_cases.csv`](sample_30_cases.csv), producing a 990-row long-format
table (`Publications/experiment_01/results/features.csv`). Those predictions must be scored
against the **human gold standard** from
[`experiment_02/human_labeling_instructions.md`](experiment_02/human_labeling_instructions.md).

"Tracking the results" therefore means more than saving one CSV: it means keeping a
**versioned history of runs** (models and prompts will change), **scoring each run against the
gold standard** (per-feature and per-model accuracy, F1, Cohen's κ), and being able to
**compare runs side-by-side**. Below are three plans that each build on infrastructure
already present in this repository. **The recommended plan is Plan A (GitHub-only)** as the
reproducible backbone, with Plan B (MLflow) available as an optional analysis layer.

---

## 1. What Experiment 1 produces (the data being tracked)

`extract_features.py` writes one long-format CSV, checkpointing after every `(case, model)`
call so an interrupted run resumes cleanly:

| Column | Meaning |
|---|---|
| `case_id` | docket stem + filing date (e.g. `21-70493-2022-09-14`) |
| `pdf_url` | CA9 opinion PDF link |
| `model` | one of the 3 NIM models |
| `feature` | one of the 11 binary features |
| `predicted` | `true` / `false` (or null on error) |
| `evidence` | verbatim supporting quote |
| `latency_ms` | per-call latency |
| `error` | populated on API/parse/download failure |

**Volume per sweep:** 30 cases × 3 models × 11 features = **990 rows** (330 model calls).

The **unit of tracking is a "sweep"** — one full pass of all models over all cases with a
fixed prompt. The interesting quantities are computed by *joining* a sweep to the human gold
standard.

## 2. What "tracking" must actually support

1. **Versioned runs.** Models, prompts, and feature definitions will change; every sweep must
   be reproducible and attributable to an exact code state.
2. **Scoring vs. the gold standard.** Per-feature and per-model **accuracy, precision/recall,
   macro-F1, and Cohen's κ** (LLM vs. human), plus confusion counts per feature.
3. **Cross-run comparison.** "Did the new prompt improve `nexus_requirement_met` on
   DeepSeek?" must be answerable by comparing two sweeps.
4. **Operational health.** Per-model **latency** and **error/parse-failure rates**.
5. **Publication-readiness.** Results and figures must be citable, diffable, and living
   alongside the manuscript.

---

## 3. The three plans

| | **Plan A — GitHub-only** | **Plan B — MLflow** | **Plan C — Supabase + dashboard** |
|---|---|---|---|
| New infra | **None** | MLflow server (Cloud Run, scales to zero) | Postgres tables + small dashboard |
| Already in repo? | ✅ `nvidia_features_sweep.yml` proves the exact pattern | ✅ `experiments/mlflow/` (local + Cloud Run) | ✅ `lib/supabase_client.py`, `extraction_runs` pattern |
| Run history | git commits + tags | MLflow runs (parent per sweep, child per model) | rows keyed by `run_id` + `git_sha` |
| Metrics vs. gold | scoring script → `metrics.csv` + `summary.md` | logged as MLflow metrics | SQL views joining predictions ↔ labels |
| Cross-run compare | `git diff`, GH Actions run summaries | MLflow UI (parallel-coords, metric-over-time) | SQL / Metabase / Streamlit |
| Cost | Free | ~$0 idle (scales to zero) | Supabase free tier |
| Best for | Reproducible, citable, publication artifacts | Rapid prompt/model iteration & visual compare | Queryable joins to the gold standard at scale |

### Plan A — GitHub-only *(recommended backbone; no extra libraries)*

Results are versioned **as commits**; each sweep is a commit, each notable sweep a git tag.
This mirrors the existing, proven `nvidia_features_sweep.yml` workflow exactly.

- **Run:** a `workflow_dispatch` (+ optional resume cron) GitHub Action installs the five
  deps, runs `Publications/experiment_01/extract_features.py`, and commits
  `Publications/experiment_01/results/features.csv` back to the branch (checkpoint/resume is
  already built in).
- **Score:** add `Publications/experiment_01/score.py` (pure `pandas`, no new deps) that
  joins `features.csv` to the human gold CSV and writes `results/metrics.csv` (per model ×
  feature: accuracy, precision, recall, F1, κ, n) and a human-readable `results/summary.md`.
  Both are committed by the same workflow.
- **Surface:** the workflow echoes the metrics table into `$GITHUB_STEP_SUMMARY` so every run
  shows its scores on the Actions page; GitHub renders `features.csv`, `metrics.csv`, and
  `summary.md` natively.
- **Compare:** tag each sweep (`exp01-YYYYMMDD-<modelset>`); compare runs with `git diff`
  between tags, or open a PR per prompt change so the metric delta is reviewable.
- **Trade-off:** no interactive charts — cross-run trends are read from committed CSVs (or a
  small committed notebook). Simplest, cheapest, most citable.

### Plan B — MLflow *(existing infra; best interactive comparison)*

Instrument the sweep to log to the MLflow server already scaffolded in
`experiments/mlflow/` (local `start_local.sh`, or Cloud Run `deploy_mlflow.sh`, backed by the
Supabase Postgres in `DATABASE_URL`).

- One **parent run per sweep** (params: prompt hash, feature-set version, git SHA, temperature)
  with a **child run per model** (metrics: accuracy, macro-F1, κ, mean/95p latency, error rate;
  artifacts: `features.csv`, confusion-matrix PNGs).
- Compare sweeps in the MLflow UI — parallel-coordinates across prompts/models and
  metric-over-time as the gold standard fills in. ~10 added lines in `extract_features.py`.
- **Trade-off:** a server to run (free when idle on Cloud Run), and results live in MLflow
  rather than in-repo — so pair it with Plan A for the citable copy.

### Plan C — Supabase results table + lightweight dashboard

Persist predictions to Postgres, exactly like the existing `extraction_runs` reliability
pattern (`experiments/run_extraction_experiment.py`).

- Tables: `exp1_predictions` (`run_id`, `git_sha`, `case_id`, `model`, `feature`,
  `predicted`, `evidence`, `latency_ms`, `error`, `created_at`) and `exp1_human_labels`.
- Metrics as **SQL views** that join predictions to labels (accuracy/κ per feature × model);
  visualize via a Streamlit/Metabase page or the existing `asylum-viewer` app.
- **Trade-off:** most setup (schema + dashboard), but the most queryable and the natural
  choice once this scales past 30 cases toward the full 6,000-opinion corpus.

---

## 4. Recommendation

**Adopt Plan A (GitHub-only) now** as the tracking backbone: it needs zero new
infrastructure, is free, produces citable and diffable artifacts that live beside the
manuscript, and reuses a workflow pattern already proven in this repo. Add a small
`score.py` so every sweep is automatically scored against the human gold standard.

**Layer on Plan B (MLflow) only when prompt/model iteration accelerates** and interactive
cross-run visualization is worth the server. **Move to Plan C (Supabase)** when the study
scales beyond the 30-case sample. The three are complementary, not mutually exclusive — Plan
A always holds the authoritative, version-controlled copy of the results.

---

## 5. Order of operations to run Experiment 1

**Prerequisites**
1. `NVIDIA_API_KEY` (an `nvapi-...` key) available — locally in `.env`, or as the
   `NVIDIA_API_KEY` GitHub Actions secret for the automated run.
2. Python 3.12 with `pandas`, `pymupdf`, `openai`, `requests`, `pydantic` (already pinned in
   `requirements.txt`).

**Confirm inputs**
3. Verify the sample loads from its new home: `Publications/sample_30_cases.csv` (30 rows,
   `link` column) — used by `extract_features.py` (`SAMPLE_CSV`).
4. Confirm the 11 feature definitions in `extract_features.py` match the human codebook in
   `experiment_02/human_labeling_instructions.md` (they are intended to be identical).

**Execute the sweep**
5. Local: `set -a && source .env && set +a && source ninthc/bin/activate` then
   `python3 Publications/experiment_01/extract_features.py`.
   Automated (recommended): add an `experiment_01_sweep.yml` workflow modeled on
   `nvidia_features_sweep.yml` (`workflow_dispatch`, installs the five deps, runs the script,
   commits `Publications/experiment_01/results/features.csv`). One dispatch (~2h) finishes all
   30×3 calls; the built-in checkpoint/resume makes re-dispatch safe.
6. Watch the console/step summary: each `(case, model)` prints `N/11 True` and latency; errors
   are recorded per row and retried on the next run rather than aborting the sweep.

**Collect the human gold standard (parallel track, Experiment 2)**
7. Have labelers fill the same 11 boolean features for the 30 cases per
   `human_labeling_instructions.md`; store as `Publications/experiment_02/results/labels.csv`
   keyed by the same `case_id`.

**Score and track**
8. Run `score.py` (Plan A) to join `features.csv` ↔ gold labels and write
   `results/metrics.csv` + `results/summary.md` (per model × feature: accuracy, precision,
   recall, F1, Cohen's κ; plus per-model latency and error rate).
9. Commit results and tag the sweep (`exp01-YYYYMMDD-<modelset>`). To compare against a prior
   sweep, `git diff` the tags or open a PR so the metric delta is reviewed.
10. *(Optional)* If Plan B is enabled, the same run logs params/metrics/artifacts to MLflow
    for interactive cross-run comparison.

**Iterate**
11. On any change to models, prompt wording, or feature definitions, bump a
    prompt/feature-set version, re-run steps 5–9, and compare the new sweep's `metrics.csv`
    against the previous tag.
