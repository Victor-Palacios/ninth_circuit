# Experiment 2 — Human Labeling Instructions

## Background

Thank you for supporting our research project!

The primary goal of this study is to assess how well a suite of large language models
(LLMs) can extract statute-relevant information from Ninth Circuit asylum-claim opinions.

To empirically assess each model's performance, we will need to compare its outputs to a
gold standard. This is where you come in! We need your help determining the ground truth
in outcomes of interest for these cases.

To date, we have saved over 6,000 published and unpublished opinions in a database. Once
we validate LLM performance in information extraction, we can scale the process across all
documents.

## Instructions

You will be provided with a spreadsheet containing a link to a Ninth Circuit asylum-claim
decision. Please review the document and fill in the following fields for each row.

Unless otherwise noted, all entries should only be **'true'** (indicating yes) or
**'false'** (indicating no).

1. **asylum_requested** — Petitioner applied for asylum under INA § 208 / 8 U.S.C. § 1158,
   not just withholding of removal or CAT protection.

2. **withholding_requested** — Petitioner sought withholding of removal under
   INA § 241(b)(3).

3. **CAT_requested** — Petitioner sought protection under the Convention Against Torture
   under 8 C.F.R. §§ 1208.16-1208.18.

4. **protected_ground_political_opinion** — The claim is based at least in part on actual
   or imputed political opinion.

5. **protected_ground_particular_social_group** — The claim is based at least in part on
   membership in a particular social group, or PSG.

6. **past_persecution_physical_violence** — The record describes past physical violence
   inflicted on the petitioner, such as beatings, shootings, stabbings, or similar harm.

7. **past_persecution_death_threats** — The record describes death threats made against the
   petitioner.

8. **persecutor_nongovernmental_actor** — The text indicates that past persecution was, or
   was feared to be, carried out by a non-government actor.

9. **credibility_finding** — The IJ or BIA made an explicit credibility finding about the
   petitioner.

10. **bars_one_year_deadline_missed** — The opinion notes that the petitioner missed the
    one-year asylum filing deadline under INA § 208(a)(2)(B).

11. **nexus_requirement_met** — The IJ or BIA found that the petitioner established the
    required nexus: that a protected ground was, or would be, "at least one central reason"
    for the persecution, as required by INA § 208(b)(1)(B)(i). (For withholding of removal,
    the lower "a reason" standard applies.)

---

\* It is very important that you never communicate about the task or ask questions to other
labelers. We need your unbiased opinions. If you have questions, please reach out to Victor.

\*\* **Do not use any AI or LLM tools** (such as ChatGPT, Claude, Gemini, Copilot, or any
other automated system) to read the opinions or determine your answers. Your labels are the
**human gold standard** we use to measure the models' accuracy — using AI to produce them
would defeat the entire purpose of this study and invalidate the results. Every answer must
be your own, based on your reading of the document.
