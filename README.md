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

The pipeline uses a hybrid approach: lightweight jobs run on GitHub Actions (free), heavy AI jobs run on GCP Cloud Run (pay-per-use).

| Job | Platform | Schedule (Pacific) | What it does |
|-----|----------|--------------------|--------------|
| `fetch` | GitHub Actions | 6:00 AM | Scrape new opinions from ca9.uscourts.gov |
| `backup` | GitHub Actions | 2:00 AM | Export asylum_cases to Hugging Face Datasets |
| `asylum-classify` | Cloud Run | 8:00 AM | Classify pending opinions via Gemini |
| `asylum-extract` | Cloud Run | 10:00 AM | Extract 70+ legal features from asylum cases |
| `asylum-qa` | Cloud Run | 12:00 PM | Spot-check 10 random cases against PDFs, email report via SendGrid |

**Why the split?** Jobs with no GCP dependencies (fetch, backup) run free on GitHub Actions — no Docker image or GCP credentials needed. The AI steps (classify, extract) need Vertex AI access and benefit from Cloud Run's per-second billing and parallelism, so they stay on GCP.

**Backup storage:** `asylum_cases.json` is pushed to a Hugging Face Dataset repo on every run. Hugging Face's git history preserves every snapshot indefinitely for free — no lifecycle policy needed.

### GitHub Actions (fetch + backup)

Secrets required in GitHub → Settings → Secrets → Actions:
- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY`
- `HF_TOKEN` — Hugging Face write token (from hf.co/settings/tokens)
- `HF_REPO` — Dataset repo in `owner/name` format (e.g. `vpalacios/ninth-circuit`)

Manual trigger available from the Actions tab via `workflow_dispatch`.

### GCP Cloud Run (classify, extract, backup, qa)

```bash
export GCP_PROJECT_ID=your-project
export SUPABASE_URL=https://your-project.supabase.co
bash cloud/deploy.sh
```

Builds a Docker image, deploys Cloud Run jobs, and creates Cloud Scheduler triggers for the four GCP-hosted jobs above.

## Frontend

The **asylum-viewer** (`asylum-viewer/`) is a Next.js app deployed on Vercel that provides a searchable, filterable interface for browsing asylum cases. Column filters are type-specific: binary dropdowns for status fields, numeric thresholds for counts, tri-state (Yes/No/null) for boolean fields, and text search for everything else.

![Frontend Preview](assets/frontend_preview.png)
