-- RLS policies for all_opinions and extraction_runs.
-- Pattern: anon=no access, authenticated=read-only, service_role=full access.
-- (asylum_cases RLS is already set up in 20240101000000_rls_asylum_cases.sql)

-- ── all_opinions ────────────────────────────────────────────────────────────

REVOKE ALL ON TABLE "public"."all_opinions" FROM "anon";
REVOKE DELETE, INSERT, UPDATE, TRUNCATE, REFERENCES, TRIGGER
    ON TABLE "public"."all_opinions" FROM "authenticated";
GRANT SELECT ON TABLE "public"."all_opinions" TO "authenticated";

ALTER TABLE "public"."all_opinions" ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can read all_opinions"
    ON "public"."all_opinions"
    FOR SELECT
    TO authenticated
    USING (true);

-- ── extraction_runs ─────────────────────────────────────────────────────────

REVOKE ALL ON TABLE "public"."extraction_runs" FROM "anon";
REVOKE DELETE, INSERT, UPDATE, TRUNCATE, REFERENCES, TRIGGER
    ON TABLE "public"."extraction_runs" FROM "authenticated";
GRANT SELECT ON TABLE "public"."extraction_runs" TO "authenticated";

ALTER TABLE "public"."extraction_runs" ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can read extraction_runs"
    ON "public"."extraction_runs"
    FOR SELECT
    TO authenticated
    USING (true);
