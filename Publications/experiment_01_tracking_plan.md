# Experiment 1 — Pipeline & Results-Tracking Plan

**Author:** Victor Palacios · **Updated:** 2026-07-08
**Scope:** How Experiment 1 runs end-to-end, how the three models differ, and how
results are tracked — using GitHub only (Actions + git history), no external services.

---

## TL;DR

Experiment 1 probes **3 NVIDIA NIM models** on **11 binary features** across the **30
curated Ninth Circuit asylum opinions** in
[`Publications/sample_30_cases.csv`](sample_30_cases.csv), producing a 990-row table
(`results/features.csv`) that is scored against the **human gold standard** from
Experiment 2.

Tracking is **GitHub-native**: a `workflow_dispatch` GitHub Action runs the sweep,
`score.py` compares it to the human labels, and both the raw predictions and the computed
metrics are **committed back to the branch**. Every sweep is therefore a git commit; the
prompt and feature definitions are code, so the commit SHA pins exactly what produced each
number. No MLflow, no database — just the repo.

**Artifacts that implement this plan (already in the repo):**

| Path | Role |
|---|---|
| `Publications/sample_30_cases.csv` | Input: the 30 case links |
| `Publications/experiment_01/extract_features.py` | The pipeline: LLM sweep → `results/features.csv` |
| `Publications/experiment_01/score.py` | Scoring: `features.csv` + gold → `results/metrics.csv` + `results/summary.md` |
| `.github/workflows/experiment_01_sweep.yml` | Automation: run sweep, score, commit results |
| `Publications/experiment_02/results/labels.csv` | Human gold standard (produced by Experiment 2) |

---

## 1. How the pipeline runs

The whole pipeline is one script, `extract_features.py`. It is deterministic-by-design
(`temperature=0`, structured JSON output) and **checkpointed**, so it can be stopped and
resumed without losing or repeating work.

### 1.1 Pulling the case links from the sample file

The 30 cases live in `Publications/sample_30_cases.csv` (columns: `n, pub_status,
sample_group, canonical, final_disposition, char_count, link`). The script only needs the
`link` column:

```python
SAMPLE_CSV = REPO_ROOT / "Publications" / "sample_30_cases.csv"
cases = pd.read_csv(SAMPLE_CSV)[["link"]].to_dict("records")
```

That yields a list of `{"link": "https://cdn.ca9.uscourts.gov/.../21-70493.pdf"}` dicts. The
script then iterates the cases in file order. For each link it derives a stable **`case_id`**
from the CA9 URL path — the docket stem plus the filing date — e.g.
`…/opinions/2022/09/14/21-70493.pdf` → `21-70493-2022-09-14`. This id is what every result
row and the checkpoint are keyed on, so the same case always maps to the same id across runs.

### 1.2 Downloading and reading each opinion

For each unique URL the script downloads the PDF once (`requests.get`, 60s timeout) and
extracts text page-by-page with **PyMuPDF**, concatenating the pages into one string. Results
are memoized in an in-process `pdf_cache`, so a link is never fetched twice within a run. A
download failure is recorded as a per-row `error` for that case and the sweep moves on rather
than aborting.

### 1.3 One structured call per (case, model)

For each case the script calls **each of the 3 models once**. A single call returns **all 11
features at once**: the user message is the fixed instruction prompt followed by
`OPINION:\n<full opinion text>`. The call uses `temperature=0`,
`response_format={"type": "json_object"}`, and `max_tokens=4096`.

The prompt asks for, per feature, a JSON **boolean** plus a one-sentence **verbatim evidence
quote** (or the literal string `"Not mentioned in the opinion."` when false). The response is
cleaned (`strip_fences` removes ```` ``` ```` fences and any `<think>…</think>` reasoning
block), parsed with `json.loads`, and validated by a **Pydantic** model that *enforces* that
every feature field is a real boolean — never null, never a string. This is what makes LLM
output directly comparable to the human `true`/`false` sheet.

### 1.4 Output shape, checkpointing, and resume

Each successful call is "exploded" into **11 rows** (one per feature) and appended to
`results/features.csv`, giving the final long format:

```
case_id, pdf_url, model, feature, predicted, evidence, latency_ms, error
```

Total per complete sweep: **30 cases × 3 models × 11 features = 990 rows** (330 model calls).

After **every** `(case, model)` call the script atomically rewrites `features.csv` (write to
`.tmp`, then `replace`). On startup it reloads that file and builds the set of `(case_id,
model)` pairs that already succeeded (empty `error`), and **skips them**. So an interrupted or
rate-limited run is resumed simply by running the script again — it continues exactly where it
stopped. A `time.sleep(1.2)` between calls keeps the sweep under the NVIDIA free-tier rate
limit.

```
sample_30_cases.csv ──► for each link ──► download+extract PDF (cached)
        │                                        │
        │                                        ▼
        │                        for each of 3 models: 1 JSON call → 11 features
        ▼                                        │
   case_id (from URL)                            ▼
                              explode to 11 rows → append+flush features.csv (checkpoint)
```

---

## 2. The three models and why they differ

The sweep runs three **independent model families** rather than three sizes of one model.
That is deliberate: agreement *across* vendors is much stronger evidence that a feature is
reliably extractable than agreement within a single vendor's lineup, and it prevents any one
model's idiosyncrasies from defining "the LLM answer."

| Model (NIM id) | Family | Character in this experiment |
|---|---|---|
| `meta/llama-3.3-70b-instruct` | Meta Llama 3.3 | Dense ~70B instruct model. The mid-size, well-understood **baseline**: fast, no reasoning trace, cheap per call. |
| `deepseek-ai/deepseek-v4-flash` | DeepSeek | Mixture-of-Experts, reasoning-capable — it can emit a `<think>…</think>` block (which is why `strip_fences` removes one). "Flash" = the latency-optimized variant. Extra reasoning may help most on the hardest inference feature (`nexus_requirement_met`). |
| `mistralai/mistral-large-3-675b-instruct-2512` | Mistral | Large flagship instruct model (the `2512` tag = the Dec-2025 release). Highest general capability of the three; typically the slowest and most expensive per call. |

Authoritative parameter counts / context windows should be read from each model's NVIDIA NIM
model card; what matters for the experiment is the **axes of difference** — vendor/family,
dense vs. MoE, model scale, and whether the model reasons before answering. All three see the
**identical prompt and opinion text** and are held to the **identical Pydantic schema**, so
any difference in output is attributable to the model, not the harness.

---

## 3. How tracking works (GitHub-only)

The tracking system has three moving parts, all inside the repo.

### 3.1 The run: a GitHub Action that commits its own results

`.github/workflows/experiment_01_sweep.yml` (modeled on the repo's existing
`nvidia_features_sweep.yml`):

1. Triggers: `workflow_dispatch` (manual) **and** a daily `schedule` at `0 11 * * *`
   (11:00 UTC = 04:00 America/Los_Angeles during PDT; GitHub cron is fixed UTC, so 03:00 in
   PST). Scheduled runs only fire from the **default branch**.
2. Checks out the branch, sets up Python 3.12, installs the five deps.
3. **Completeness gate.** `extract_features.py --check-complete` sets `complete=true|false`
   (no model calls). On a **scheduled** run, if every one of the 30 × 3 `(case, model)` cells
   is already present and error-free, the sweep, scoring, and commit steps are **all skipped**
   — the daily job is a true no-op that never re-runs populated cells or overwrites committed
   results. A **manual** dispatch always proceeds (use one to force a re-score after the gold
   standard lands).
4. Runs `extract_features.py` with `NVIDIA_API_KEY` from repo secrets (~2h; resumes from the
   committed `features.csv`, re-running only missing or errored cells).
5. Runs `score.py --github-summary`.
6. **Commits `Publications/experiment_01/results/` back to the branch** (`[skip ci]`), pulling
   `--rebase` first so concurrent commits don't collide.

Because the results are committed, **every sweep is a git commit**. The history of
`results/features.csv` *is* the run history — no external run store required. Tag notable
sweeps (`git tag exp01-YYYYMMDD-<note>`) to make them easy to diff later. The completeness
gate means the run history only grows when there is genuinely new output: an interrupted
sweep resumes and commits once it finishes, then the daily schedule goes quiet.

### 3.2 The scoring: `score.py`

`score.py` reads `results/features.csv` and the human gold standard at
`Publications/experiment_02/results/labels.csv`, then writes:

- **`results/metrics.csv`** — one row per `(model, feature)` with `n, tp, fp, fn, tn,
  accuracy, precision, recall, f1, cohen_kappa`.
- **`results/summary.md`** — a rendered report: a provenance header, per-model health, the
  metrics table, and per-model macro averages.

It accepts the **wide** human labeling sheet (one row per case, one `true`/`false` column per
feature — exactly what the Experiment 2 instructions produce) and melts it to long, joining to
predictions on the opinion **URL** (`link` ↔ `pdf_url`). It uses only `pandas` — accuracy,
F1, and Cohen's κ (LLM-vs-human agreement, chance-corrected) are computed directly, so the
GitHub-only plan needs no extra libraries. If the gold standard isn't present yet (Experiment
2 still in progress), it degrades gracefully to **prediction-only diagnostics** (per-feature
true-rate, latency, error rate) so the loop is useful before labeling finishes.

Every sweep's scores are also echoed to `$GITHUB_STEP_SUMMARY`, so the Actions run page shows
the metrics table without opening any file.

### 3.3 Tracking the **models**

Model identity is a **first-class column**, not metadata you have to reconstruct:

- Every row of `features.csv` carries its `model`, so `metrics.csv` and `summary.md` break
  results down **per model with no extra bookkeeping**. Within a single sweep you read the
  three models head-to-head against the same gold standard: *which model best matches the
  humans, feature by feature.*
- The model set is the `MODELS` list in `extract_features.py` — it is **code**, so adding or
  swapping a model is a commit (self-documenting in `git log`). The checkpoint keys on
  `(case_id, model)`, so adding a 4th model re-runs **only** the new model; the existing three
  are skipped.
- `score.py`'s per-model **health** table (calls, error rate, mean latency) tracks the
  operational side of each model every sweep.

### 3.4 Tracking the **prompt**

The prompt is **not a runtime parameter** — `build_prompt()` generates it from the `FEATURES`
list in `extract_features.py`. The prompt is therefore fully determined by that source file,
which means:

- **Prompt provenance == git provenance.** `score.py` writes the **commit SHA** into every
  `summary.md`. That SHA pins the exact prompt wording *and* all 11 feature definitions that
  produced those numbers — the results are never ambiguous about which prompt made them.
- **A prompt change is a diff.** Edit the wording or a feature definition → new commit → new
  SHA on the next sweep's summary. To measure the effect, tag the before/after sweeps and
  `git diff exp01-<before> exp01-<after> -- Publications/experiment_01/results/metrics.csv` —
  the metric delta attributable to that prompt change is a single, reviewable diff.
- **Keep prompt edits in their own commits** (don't mix with unrelated changes) so
  `git log -p Publications/experiment_01/extract_features.py` reads as a clean prompt
  changelog.
- The 11 feature definitions are **shared** with the Experiment 2 human codebook. Because the
  SHA records exactly which wording the models saw, it stays auditable whether the LLM prompt
  and the human instructions were in sync for any given sweep.

---

## 4. Order of operations to run Experiment 1

**Prerequisites**
1. Add the `NVIDIA_API_KEY` (`nvapi-…`) as a **repository secret** (for the Action) and/or to
   local `.env` (for a local run).
2. Deps are pinned in `requirements.txt` (`pandas`, `pymupdf`, `openai`, `requests`,
   `pydantic`); the workflow installs exactly these five.

**Confirm inputs**
3. Verify `Publications/sample_30_cases.csv` loads (30 rows, `link` column).
4. Confirm the 11 feature definitions in `extract_features.py` match the Experiment 2 codebook
   (they are intended to be identical).

**Run the sweep**
5. **Automated (recommended):** GitHub → Actions → *"Experiment 1 — 11-feature sweep +
   scoring"* → **Run workflow** on this branch. It runs the sweep, scores it, and commits
   `results/`. Re-dispatch safely if it's interrupted — it resumes from the committed CSV.
   **Local alternative:** `set -a && source .env && set +a && source ninthc/bin/activate &&
   python3 Publications/experiment_01/extract_features.py`.
6. Watch progress: each `(case, model)` prints `N/11 True` and latency; errors are recorded
   per row and retried on the next run instead of aborting the sweep.

**Collect the human gold standard (Experiment 2, in parallel)**
7. Labelers fill the 11 boolean features for the 30 cases per
   `experiment_02/human_labeling_instructions.md`; save as
   `Publications/experiment_02/results/labels.csv` (wide: `link` + one column per feature).

**Score and track**
8. `score.py` runs automatically in the workflow (or run it locally). It writes
   `results/metrics.csv` + `results/summary.md` and echoes the tables to the Actions summary.
9. Review `summary.md`; **tag the sweep** (`git tag exp01-YYYYMMDD-<note> && git push --tags`).

**Iterate**
10. On any change to the models (`MODELS`), the prompt, or a feature definition: commit it on
    its own, re-run the sweep, and compare the new `metrics.csv` against the previous tag to
    attribute the change.
