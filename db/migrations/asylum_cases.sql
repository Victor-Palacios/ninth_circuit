-- Declarative schema for asylum_cases, generated from asylum_final_features.csv.
-- You can manage this via Supabase CLI:
--   supabase db diff -f add_asylum_cases
--   supabase db push

CREATE TABLE IF NOT EXISTS asylum_cases (
  link TEXT,  -- TEXT
  published_status TEXT,  -- TEXT
  date_filed DATE,  -- DATE
  docket_no TEXT,  -- TEXT
  char_count INTEGER,  -- INTEGER
  court_level TEXT,  -- TEXT
  court_level_evidence TEXT,  -- TEXT
  country_of_origin TEXT,  -- TEXT
  country_of_origin_evidence TEXT,  -- TEXT
  asylum_requested BOOLEAN,  -- BOOLEAN
  asylum_requested_evidence TEXT,  -- TEXT
  withholding_requested BOOLEAN,  -- BOOLEAN
  withholding_requested_evidence TEXT,  -- TEXT
  "CAT_requested" BOOLEAN,  -- BOOLEAN
  "CAT_requested_evidence" TEXT,  -- TEXT
  final_disposition TEXT,  -- TEXT
  final_disposition_evidence TEXT,  -- TEXT
  protected_ground_race BOOLEAN,  -- BOOLEAN
  protected_ground_race_evidence TEXT,  -- TEXT
  protected_ground_religion BOOLEAN,  -- BOOLEAN
  protected_ground_religion_evidence TEXT,  -- TEXT
  protected_ground_nationality BOOLEAN,  -- BOOLEAN
  protected_ground_nationality_evidence TEXT,  -- TEXT
  protected_ground_political_opinion BOOLEAN,  -- BOOLEAN
  protected_ground_political_opinion_evidence TEXT,  -- TEXT
  protected_ground_particular_social_group BOOLEAN,  -- BOOLEAN
  protected_ground_particular_social_group_evidence TEXT,  -- TEXT
  nexus_explicit_nexus_language BOOLEAN,  -- BOOLEAN
  nexus_explicit_nexus_language_evidence TEXT,  -- TEXT
  nexus_nexus_strength BOOLEAN,  -- BOOLEAN
  nexus_nexus_strength_evidence TEXT,  -- TEXT
  past_persecution_established BOOLEAN,  -- BOOLEAN
  past_persecution_established_evidence TEXT,  -- TEXT
  past_persecution_physical_violence BOOLEAN,  -- BOOLEAN
  past_persecution_physical_violence_evidence TEXT,  -- TEXT
  past_persecution_detention BOOLEAN,  -- BOOLEAN
  past_persecution_detention_evidence TEXT,  -- TEXT
  past_persecution_sexual_violence BOOLEAN,  -- BOOLEAN
  past_persecution_sexual_violence_evidence TEXT,  -- TEXT
  past_persecution_death_threats BOOLEAN,  -- BOOLEAN
  past_persecution_death_threats_evidence TEXT,  -- TEXT
  past_persecution_harm_severity BOOLEAN,  -- BOOLEAN
  past_persecution_harm_severity_evidence TEXT,  -- TEXT
  persecutor_government_actor BOOLEAN,  -- BOOLEAN
  persecutor_government_actor_evidence TEXT,  -- TEXT
  persecutor_non_state_actor BOOLEAN,  -- BOOLEAN
  persecutor_non_state_actor_evidence TEXT,  -- TEXT
  persecutor_government_unable_or_unwilling BOOLEAN,  -- BOOLEAN
  persecutor_government_unable_or_unwilling_evidence TEXT,  -- TEXT
  future_fear_well_founded_fear BOOLEAN,  -- BOOLEAN
  future_fear_well_founded_fear_evidence TEXT,  -- TEXT
  future_fear_internal_relocation_reasonable BOOLEAN,  -- BOOLEAN
  future_fear_internal_relocation_reasonable_evidence TEXT,  -- TEXT
  future_fear_changed_country_conditions BOOLEAN,  -- BOOLEAN
  future_fear_changed_country_conditions_evidence TEXT,  -- TEXT
  credibility_credibility_finding BOOLEAN,  -- BOOLEAN
  credibility_credibility_finding_evidence TEXT,  -- TEXT
  credibility_inconsistencies_central BOOLEAN,  -- BOOLEAN
  credibility_inconsistencies_central_evidence TEXT,  -- TEXT
  credibility_corroboration_present BOOLEAN,  -- BOOLEAN
  credibility_corroboration_present_evidence TEXT,  -- TEXT
  country_conditions_cited BOOLEAN,  -- BOOLEAN
  country_conditions_cited_evidence TEXT,  -- TEXT
  bars_one_year_deadline_missed BOOLEAN,  -- BOOLEAN
  bars_one_year_deadline_missed_evidence TEXT,  -- TEXT
  bars_firm_resettlement BOOLEAN,  -- BOOLEAN
  bars_firm_resettlement_evidence TEXT,  -- TEXT
  bars_particularly_serious_crime BOOLEAN,  -- BOOLEAN
  bars_particularly_serious_crime_evidence TEXT  -- TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_asylum_cases_link ON asylum_cases (link);

