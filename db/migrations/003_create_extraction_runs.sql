-- Table: extraction_runs
-- Stores multiple extraction runs per asylum case for reliability experiments.
-- Each case can have up to 3 runs; the final accepted extraction goes into asylum_cases.

CREATE TABLE IF NOT EXISTS extraction_runs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    link TEXT NOT NULL REFERENCES asylum_cases (link),
    run_number INTEGER NOT NULL CHECK (run_number BETWEEN 1 AND 3),
    extracted_fields JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (link, run_number)
);

CREATE INDEX IF NOT EXISTS idx_extraction_runs_link ON extraction_runs (link);
