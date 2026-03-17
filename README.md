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
  [2. Classify] ──> Gemini 2.5 Pro marks asylum_related = true/false
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

**AI:** Google Gemini 2.5 Pro via Vertex AI (google-genai SDK) for both classification and feature extraction.

**Why two separate AI steps?** Classification is a cheap yes/no call (~3,250 tokens). Extraction is expensive — it returns evidence quotes for 60+ fields (~6,900 tokens, mostly output). Since ~96% of opinions are not asylum-related, running extraction on everything would be ~25x more expensive. The two-step filter keeps costs low.

**Approximate Gemini costs** (Gemini 2.5 Pro: $1.25/1M input tokens, $10/1M output tokens):

| Operation | Tokens (avg) | Cost per 100 calls |
|-----------|-------------|-------------------|
| Classify | ~3,250 (input-heavy) | ~$0.42 |
| Extract | ~6,900 (output-heavy) | ~$3.50 |

Extraction is ~8x more expensive per call, almost entirely due to the large JSON output (evidence quotes for every field). Observed spend: About $50 for 3,364 classifications + 769 extractions ($14 classify, $27 extract, $9 GCP infrastructure).

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
| `classify_groq` | 8:00 AM | Classify 2021-06 → 2024 via Groq |
| `classify_google_aistudio` | 8:00 AM | Classify 2020-10 → 2021-05 via Google AI Studio |
| `classify_huggingface` | 8:00 AM | Classify 2020-01 → 2020-09 via HuggingFace |
| `classify_openrouter` | 8:00 AM | Classify 2025 via OpenRouter |
| `classify_github_models` | 8:00 AM | Classify 2026 via GitHub Models |

**Backup storage:** `asylum_cases.json` is pushed to a Hugging Face Dataset repo on every run. Hugging Face's git history preserves every snapshot indefinitely for free — no lifecycle policy needed.

### Classification providers

All classifiers use non-overlapping date ranges so no opinion is processed twice. Each provider's range is sized to fit within its free-tier daily limit.

| Provider | Model | `classifying_model` value | Date range | Rows | Daily limit |
|----------|-------|--------------------------|------------|:----:|:-----------:|
| HuggingFace | Llama 3.3 70B | `meta-llama/Llama-3.3-70B-Instruct` | 2020-01-01 → 2020-09-30 | 891 | 1,000 |
| Google AI Studio | Gemini 2.0 Flash | `gemini-2.0-flash` | 2020-10-01 → 2021-05-31 | 1,391 | 1,500 |
| Groq | Llama 3.3 70B | `llama-3.3-70b-versatile` | 2021-06-01 → 2024-12-31 | 10,171 | 14,400 |
| OpenRouter | DeepSeek V3 | `deepseek-chat-v3-0324` | 2025-01-01 → 2025-12-31 | 156 | 200 |
| GitHub Models | GPT-4o mini | `gpt-4o-mini` | 2026-01-01 → 2026-12-31 | 14 | 150 |
| Vertex AI (historical) | Gemini 2.5 Pro | `gemini-2.5-pro` | backfill | — | paid |

**Combined free-tier capacity: ~17,350 rows/day** — enough to clear the full 12,623-row backlog in a single day.

### GitHub Actions secrets required

| Secret | Used by |
|--------|---------|
| `SUPABASE_URL` | all jobs |
| `SUPABASE_SECRET_KEY` | all jobs |
| `SENDGRID_API_KEY` | all jobs (email notifications) |
| `HF_TOKEN` | backup, classify_huggingface |
| `HF_REPO` | backup (`vpal/asylum-cases`) |
| `OPENROUTER_API_KEY` | classify_openrouter |
| `GROQ_API_KEY` | classify_groq |
| `GOOGLE_AI_STUDIO_KEY` | classify_google_aistudio |
| `GITHUB_TOKEN` | classify_github_models (automatic) |


## Frontend

The **asylum-viewer** (`asylum-viewer/`) is a Next.js app deployed on Vercel that provides a searchable, filterable interface for browsing asylum cases. Column filters are type-specific: binary dropdowns for status fields, numeric thresholds for counts, tri-state (Yes/No/null) for boolean fields, and text search for everything else.

![Frontend Preview](assets/frontend_preview.png)
