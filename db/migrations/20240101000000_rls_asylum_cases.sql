-- ============================================================
-- Migration: Enable RLS on asylum_cases
-- Read:  authenticated users only
-- Write: nobody via website (admin dashboard / service_role only)
-- ============================================================

-- 1. Revoke overly-broad anon permissions
revoke delete on table "public"."asylum_cases" from "anon";
revoke insert on table "public"."asylum_cases" from "anon";
revoke references on table "public"."asylum_cases" from "anon";
revoke select on table "public"."asylum_cases" from "anon";
revoke trigger on table "public"."asylum_cases" from "anon";
revoke truncate on table "public"."asylum_cases" from "anon";
revoke update on table "public"."asylum_cases" from "anon";

-- 2. Revoke write permissions from authenticated users
--    (they can only read, granted via policy below)
revoke delete on table "public"."asylum_cases" from "authenticated";
revoke insert on table "public"."asylum_cases" from "authenticated";
revoke references on table "public"."asylum_cases" from "authenticated";
revoke trigger on table "public"."asylum_cases" from "authenticated";
revoke truncate on table "public"."asylum_cases" from "authenticated";
revoke update on table "public"."asylum_cases" from "authenticated";

-- Re-grant only SELECT to authenticated
grant select on table "public"."asylum_cases" to "authenticated";

-- 3. Enable Row Level Security
alter table "public"."asylum_cases" enable row level security;

-- 4. RLS Policies

-- Allow any logged-in user to read all cases
create policy "Authenticated users can read cases"
  on "public"."asylum_cases"
  for select
  to authenticated
  using (true);

-- Explicitly block anon reads (belt-and-suspenders)
-- (No policy = no access once RLS is enabled, but this makes intent clear)
-- No anon policy needed — absence of policy denies by default.

-- NOTE: Insert / Update / Delete are intentionally omitted.
-- Only service_role (Supabase dashboard) can mutate data.
