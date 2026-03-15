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

## Database

Two main tables in Supabase:

| Table | Purpose |
|-------|---------|
| `all_opinions` | Every Ninth Circuit opinion with metadata and asylum classification |
| `asylum_cases` | Asylum cases only, with 70+ extracted legal features |
| `extraction_runs` | Experiment tracking for reliability testing (3x extraction runs) |

## Project Structure

```
pipeline/          Core pipeline scripts (fetch, classify, extract, backfill)
lib/               Shared utilities (Supabase client, Gemini client, config)
cloud/             GCP deployment (Dockerfile, deploy.sh, Cloud Run entry point)
db/                Database migrations and schemas
experiments/       MLflow experiment tracking
asylum-viewer/     Next.js frontend
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

# Backfill historical data (2023-present)
python -m pipeline.backfill --start-date 2023-01-01
```

## Deploy to GCP

```bash
export GCP_PROJECT_ID=your-project
export SUPABASE_URL=https://your-project.supabase.co
bash cloud/deploy.sh
```

This builds a Docker container, deploys it as a Cloud Run job, and executes it.

## Frontend

The **asylum-viewer** is a Next.js app that provides a searchable, filterable interface for browsing asylum cases.
