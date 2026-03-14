-- Table: all_opinions
-- Stores metadata for every Ninth Circuit opinion (published + unpublished).
-- Source: ca9.uscourts.gov RSS feeds + HTML scraping.

CREATE TABLE IF NOT EXISTS all_opinions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    link TEXT UNIQUE NOT NULL,
    case_title TEXT,
    case_number TEXT,
    case_origin TEXT,
    authoring_judge TEXT,
    case_type TEXT,
    date_filed DATE,
    published_status TEXT CHECK (published_status IN ('Published', 'Unpublished')),
    asylum_related BOOLEAN,
    classified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_all_opinions_date_filed ON all_opinions (date_filed);
CREATE INDEX IF NOT EXISTS idx_all_opinions_asylum_related ON all_opinions (asylum_related);
