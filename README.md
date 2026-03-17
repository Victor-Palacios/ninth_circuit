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

**Extraction:** Google Gemini 2.5 Pro via Vertex AI (google-genai SDK) for structured feature extraction from asylum cases.

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
| `extraction_runs` | Experiment tracking for reliability testing (3x extraction runs) |

## Project Structure

```
pipeline/          Core pipeline (fetch, classify, extract, backfill)
lib/               Shared utilities (Supabase client, Gemini client, config)
cloud/             GCP deployment (Dockerfile, deploy.sh, Cloud Run entry points)
asylum-viewer/     Next.js frontend (deployed on Vercel)
```

## Setup

### 1. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate
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
source .env
python cloud/main.py
```

### Run individual steps

```bash
# Fetch new opinions from ca9.uscourts.gov
python -m pipeline.fetch

# Classify pending opinions
python -m pipeline.classify --limit 10

# Extract features from asylum cases
python -m pipeline.extract --limit 5

# Backfill historical data
python -m pipeline.backfill --start-date 2020-01-01 --end-date 2025-12-31
```

## Scheduling

All scheduled jobs run on GitHub Actions (free). The pipeline runs daily and sends a SendGrid email after each job.

| Job | Schedule (Pacific) | What it does |
|-----|--------------------|--------------|
| `fetch` | 6:00 AM | Scrape new opinions from ca9.uscourts.gov |
| `backup` | 2:00 AM | Export asylum_cases to Hugging Face Datasets (`vpal/asylum-cases`) |
| `classify_groq` | 2:00 AM | Classify 2021-06 → 2024 via Groq |
| `classify_huggingface` | 2:00 AM | Classify 2020-01 → 2020-09 via HuggingFace |
| `classify_openrouter` | 2:00 AM | Classify 2025 via OpenRouter |

**Backup storage:** `asylum_cases.json` is pushed to a Hugging Face Dataset repo on every run. Hugging Face's git history preserves every snapshot indefinitely for free — no lifecycle policy needed.

### Classification providers

All classifiers use non-overlapping date ranges so no opinion is processed twice. Each provider's range is sized to fit within its free-tier daily limit.

| Provider | Model | `classifying_model` value | Date range | Rows | Daily limit |
|----------|-------|--------------------------|------------|:----:|:-----------:|
| HuggingFace | Llama 3.3 70B | `meta-llama/Llama-3.3-70B-Instruct` | 2020-01-01 → 2020-09-30 | 891 | 1,000 |
| Groq | Llama 3.3 70B | `llama-3.3-70b-versatile` | 2021-06-01 → 2024-12-31 | 10,171 | ~60 (100K tokens/day) |
| OpenRouter | hunter-alpha | `openrouter/hunter-alpha` | 2025-01-01 → 2025-12-31 | 156 | 50 |
| Vertex AI (historical) | Gemini 2.5 Pro | `gemini-2.5-pro` | backfill | — | paid |

**Combined free-tier capacity: ~1,110 rows/day** (Groq ~60, HuggingFace ~1,000, OpenRouter 50). Note: the 2020-10-01 → 2021-05-31 date range (~1,391 rows) currently has no active classifier.


## Frontend

The **asylum-viewer** (`asylum-viewer/`) is a Next.js app deployed on Vercel that provides a searchable, filterable interface for browsing asylum cases. Column filters are type-specific: binary dropdowns for status fields, numeric thresholds for counts, tri-state (Yes/No/null) for boolean fields, and text search for everything else.

![Frontend Preview](assets/frontend_preview.png)

## Opinion Length Distribution

![Char Count Distribution](assets/char_count_distribution.png)
