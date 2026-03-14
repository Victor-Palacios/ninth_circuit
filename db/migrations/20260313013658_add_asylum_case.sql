
  create table "public"."asylum_cases" (
    "link" text,
    "published_status" text,
    "date_filed" date,
    "docket_no" text,
    "char_count" integer,
    "court_level" text,
    "court_level_evidence" text,
    "country_of_origin" text,
    "country_of_origin_evidence" text,
    "asylum_requested" boolean,
    "asylum_requested_evidence" text,
    "withholding_requested" boolean,
    "withholding_requested_evidence" text,
    "CAT_requested" boolean,
    "CAT_requested_evidence" text,
    "final_disposition" text,
    "final_disposition_evidence" text,
    "protected_ground_race" boolean,
    "protected_ground_race_evidence" text,
    "protected_ground_religion" boolean,
    "protected_ground_religion_evidence" text,
    "protected_ground_nationality" boolean,
    "protected_ground_nationality_evidence" text,
    "protected_ground_political_opinion" boolean,
    "protected_ground_political_opinion_evidence" text,
    "protected_ground_particular_social_group" boolean,
    "protected_ground_particular_social_group_evidence" text,
    "nexus_explicit_nexus_language" boolean,
    "nexus_explicit_nexus_language_evidence" text,
    "nexus_nexus_strength" boolean,
    "nexus_nexus_strength_evidence" text,
    "past_persecution_established" boolean,
    "past_persecution_established_evidence" text,
    "past_persecution_physical_violence" boolean,
    "past_persecution_physical_violence_evidence" text,
    "past_persecution_detention" boolean,
    "past_persecution_detention_evidence" text,
    "past_persecution_sexual_violence" boolean,
    "past_persecution_sexual_violence_evidence" text,
    "past_persecution_death_threats" boolean,
    "past_persecution_death_threats_evidence" text,
    "past_persecution_harm_severity" boolean,
    "past_persecution_harm_severity_evidence" text,
    "persecutor_government_actor" boolean,
    "persecutor_government_actor_evidence" text,
    "persecutor_non_state_actor" boolean,
    "persecutor_non_state_actor_evidence" text,
    "persecutor_government_unable_or_unwilling" boolean,
    "persecutor_government_unable_or_unwilling_evidence" text,
    "future_fear_well_founded_fear" boolean,
    "future_fear_well_founded_fear_evidence" text,
    "future_fear_internal_relocation_reasonable" boolean,
    "future_fear_internal_relocation_reasonable_evidence" text,
    "future_fear_changed_country_conditions" boolean,
    "future_fear_changed_country_conditions_evidence" text,
    "credibility_credibility_finding" boolean,
    "credibility_credibility_finding_evidence" text,
    "credibility_inconsistencies_central" boolean,
    "credibility_inconsistencies_central_evidence" text,
    "credibility_corroboration_present" boolean,
    "credibility_corroboration_present_evidence" text,
    "country_conditions_cited" boolean,
    "country_conditions_cited_evidence" text,
    "bars_one_year_deadline_missed" boolean,
    "bars_one_year_deadline_missed_evidence" text,
    "bars_firm_resettlement" boolean,
    "bars_firm_resettlement_evidence" text,
    "bars_particularly_serious_crime" boolean,
    "bars_particularly_serious_crime_evidence" text
      );


CREATE UNIQUE INDEX idx_asylum_cases_link ON public.asylum_cases USING btree (link);

grant delete on table "public"."asylum_cases" to "anon";

grant insert on table "public"."asylum_cases" to "anon";

grant references on table "public"."asylum_cases" to "anon";

grant select on table "public"."asylum_cases" to "anon";

grant trigger on table "public"."asylum_cases" to "anon";

grant truncate on table "public"."asylum_cases" to "anon";

grant update on table "public"."asylum_cases" to "anon";

grant delete on table "public"."asylum_cases" to "authenticated";

grant insert on table "public"."asylum_cases" to "authenticated";

grant references on table "public"."asylum_cases" to "authenticated";

grant select on table "public"."asylum_cases" to "authenticated";

grant trigger on table "public"."asylum_cases" to "authenticated";

grant truncate on table "public"."asylum_cases" to "authenticated";

grant update on table "public"."asylum_cases" to "authenticated";

grant delete on table "public"."asylum_cases" to "service_role";

grant insert on table "public"."asylum_cases" to "service_role";

grant references on table "public"."asylum_cases" to "service_role";

grant select on table "public"."asylum_cases" to "service_role";

grant trigger on table "public"."asylum_cases" to "service_role";

grant truncate on table "public"."asylum_cases" to "service_role";

grant update on table "public"."asylum_cases" to "service_role";


