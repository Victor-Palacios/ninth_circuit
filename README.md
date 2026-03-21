# Ninth Circuit Asylum Pipeline

Automated pipeline for collecting, classifying, and analyzing U.S. Court of Appeals for the Ninth Circuit asylum decisions.

## Architecture

```
ca9.uscourts.gov (RSS + HTML)
        |
        v
  [1. Fetch] ──> all_opinions table (every opinion)
        |
        v
  [2. Classify] ──> Free LLMs (Groq/HuggingFace/OpenRouter) mark asylum_related = true/false
        |
        v
  [3. Extract] ──> asylum_cases table (70+ legal features per case)
        |
        v
  Supabase ──> asylum-viewer (Next.js)
```

**Data sources:**
- Published opinions: `ca9.uscourts.gov/opinions/` (RSS + scrape)
- Unpublished memoranda: `ca9.uscourts.gov/memoranda/` (RSS + scrape)

**Classification:** Free-tier LLMs via GitHub Actions (Groq, HuggingFace, OpenRouter) — no cost per call.

**Extraction:** Free-tier LLMs (HuggingFace, Groq, OpenRouter) and Google Gemini 2.5 Pro for structured feature extraction from asylum cases.

**Why two separate AI steps?** Classification is a cheap yes/no call (~3,250 tokens). Extraction is expensive — it returns evidence quotes for 60+ fields (~6,900 tokens, mostly output). Since ~96% of opinions are not asylum-related, running extraction on everything would be ~25x more expensive. The two-step filter keeps costs low.

**Approximate Gemini costs** (Gemini 2.5 Pro: $1.25/1M input tokens, $10/1M output tokens):

| Operation | Tokens (avg) | Cost per 100 calls |
|-----------|-------------|-------------------|
| Extract | ~6,900 (output-heavy) | ~$3.50 |

Classification is now free (Groq/HuggingFace/OpenRouter). Extraction uses Gemini 2.5 Pro — expensive due to large JSON output (evidence quotes for every field). Observed spend: About $36 for 769 extractions ($27 extract, $9 GCP infrastructure).

## Database

Two main tables in Supabase:

| Table | Purpose |
|-------|---------|
| `all_opinions` | Every Ninth Circuit opinion with metadata and asylum classification |
| `asylum_cases` | Asylum cases only, with 70+ extracted legal features |
| `extraction_runs` | MLflow backend tables (experiments, runs, params, metrics, artifacts) |

## Project Structure

```
pipeline/          Core pipeline (fetch, classify_free, extract, backfill)
lib/               Shared utilities (Supabase client, Gemini client, config)
cloud/             GCP deployment (Dockerfile, deploy.sh, Cloud Run entry points)
experiments/       MLflow experiment tracking (local server startup script, artifacts)
asylum-viewer/     Next.js frontend (deployed on Vercel)
logs/              Per-provider CSV logs of classifier runs
```

## Setup

### 1. Create a virtual environment

```bash
python3 -m venv ninthc
source ninthc/bin/activate
pip install -r requirements.txt
```

### 2. Set environment variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Required variables:
- `SUPABASE_URL` — Your Supabase project URL
- `SUPABASE_SECRET_KEY` — Supabase service-role key (admin access)
- `GCP_PROJECT_ID` — Google Cloud project ID
- `GCP_REGION` — GCP region (default: us-central1)

### 3. Run database migrations

Execute the SQL files in `db/migrations/` in order via the Supabase SQL editor.

## Usage

### Run the full pipeline locally

```bash
set -a && source .env && set +a
source ninthc/bin/activate
python3 cloud/main.py
```

### Run individual steps

```bash
set -a && source .env && set +a && source ninthc/bin/activate

# Fetch new opinions from ca9.uscourts.gov
python3 -m pipeline.fetch

# Classify pending opinions (free-tier LLMs)
python3 -m pipeline.classify_free --limit 10

# Extract features from asylum cases
python3 -m pipeline.extract --limit 5

# Backfill historical data
python3 -m pipeline.backfill --start-date 2020-01-01 --end-date 2025-12-31
```

## Scheduling

All scheduled jobs run on GitHub Actions (free). The pipeline sends a SendGrid email after each classify job.

| Job | Schedule (UTC) | What it does |
|-----|----------------|--------------|
| `fetch` | 6:00 AM daily | Scrape new opinions from ca9.uscourts.gov |
| `backup` | 2:00 AM daily | Export asylum_cases to Hugging Face Datasets (`vpal/asylum-cases`) |
| `classify_openrouter` | Every 2 hours | Classify all dates via OpenRouter (500/run, newest first) |
| `classify_groq` | Manual only | Classify 2021-03 → 2021-11 via Groq (disabled) |
| `classify_huggingface` | Manual only | Classify 2020-01 → 2021-03 via HuggingFace (disabled) |
| `extract_huggingface` | Every 4 hours | Extract features via HuggingFace (50/run, newest first) |
| `extract_groq` | Every 4 hours | Extract features via Groq (50/run, newest first) |
| `extract_openrouter` | Manual only | Extract features via OpenRouter (1/run) |

**Backup storage:** `asylum_cases.json` is pushed to a Hugging Face Dataset repo on every run. Hugging Face's git history preserves every snapshot indefinitely for free — no lifecycle policy needed.

### Classification providers

All classifiers use non-overlapping date ranges so no opinion is processed twice. Each provider's range is sized to fit within its free-tier daily limit.

| Provider | Model | `classifying_model` value | Context window | ~Char equivalent | Date range | Rows | Daily limit |
|----------|-------|--------------------------|:--------------:|:----------------:|------------|:----:|:-----------:|
| HuggingFace | Llama 3.3 70B | `meta-llama/Llama-3.3-70B-Instruct` | 128K tokens | ~512K chars | — (disabled) | — | ~27/day |
| Groq | Llama 3.3 70B | `llama-3.3-70b-versatile` | 128K tokens | ~512K chars | — (disabled) | — | ~76/day |
| OpenRouter | trinity-large-preview | `arcee-ai/trinity-large-preview:free` | 128K tokens | ~512K chars | 2020-01-01 → 2026-12-31 | 3,975 remaining | ~2,531/day |
| Vertex AI (historical) | Gemini 2.5 Pro | `gemini-2.5-pro` | 1M tokens | ~4.2M chars | backfill | — | paid |

**Note:** The pipeline truncates PDF text to 6,000 chars per opinion (`MAX_TEXT_CHARS`), so no model approaches its context limit in practice.

**Total unclassified: 3,975 rows.** All rows now routed to OpenRouter (~2,531 rows/day).

### Extraction providers

Extraction converts each asylum case PDF into 70+ structured legal features. Multiple free-tier providers run in parallel.

| Provider | Model | `extraction_model` value | Context window | Schedule | Limit | Extracted |
|----------|-------|--------------------------|:--------------:|----------|:-----:|:---------:|
| HuggingFace | Llama 3.3 70B | `meta-llama/Llama-3.3-70B-Instruct` | 128K tokens | Every 4 hours | 50/run | — |
| Groq | Llama 3.3 70B | `llama-3.3-70b-versatile` | 128K tokens | Every 4 hours | 50/run | — |
| OpenRouter | trinity-large-preview | `arcee-ai/trinity-large-preview:free` | 128K tokens | Manual only | 1/run | 1 |
| Vertex AI (historical) | Gemini 2.5 Pro | `gemini-2.5-pro` | 1M tokens | — | — | 783 |

**Note:** Extraction sends the full PDF text (no truncation), unlike classification which caps at 6,000 chars.

**Total pending extraction: 3,995 rows.** Already extracted: 784 rows (783 Gemini, 1 OpenRouter).


## MLflow Experiment Tracking

Extraction runs are tracked with MLflow, using Supabase Postgres as the backend store. This means experiment history persists across environments (local, GHA, Cloud Run) without a separate MLflow server.

**To browse experiments locally:**

```bash
bash experiments/mlflow/start_local.sh
# Opens UI at http://localhost:5000
```

Each extraction run logs: model name, limit, pending count, extracted count, errors, total chars, avg chars, and estimated cost. The full extraction prompt is saved as an artifact.

## Frontend

The **asylum-viewer** (`asylum-viewer/`) is a Next.js app deployed on Vercel that provides a searchable, filterable interface for browsing asylum cases. Column filters are type-specific: binary dropdowns for status fields, numeric thresholds for counts, tri-state (Yes/No/null) for boolean fields, and text search for everything else.

![Frontend Preview](assets/frontend_preview.png)

## Opinion Length Distribution

![Char Count Distribution](assets/char_count_distribution.png)
