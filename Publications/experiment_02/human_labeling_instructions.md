# Experiment 1 — Human Labeling Instructions

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

1. **asylum_requested** — Whether or not the text indicates the petitioner explicitly
   sought asylum (INA § 208 / 8 U.S.C. § 1158), as opposed to only withholding of removal
   or protection under the Convention Against Torture.

2. **withholding_requested** — Whether or not the text indicates that withholding of
   removal was sought for the petitioner (INA § 241(b)(3)).

3. **CAT_requested** — Whether or not the text indicates that protection under the
   Convention Against Torture was sought for the petitioner (8 C.F.R. §§ 1208.16–1208.18).

4. **protected_ground_political_opinion** — Whether or not the text indicates that
   persecution on account of an actual or imputed political opinion was affirmatively
   raised and argued.

5. **protected_ground_particular_social_group** — Whether the text indicates that
   persecution on account of a particular social group (PSG) was affirmatively raised and
   argued. Under BIA precedent, a group qualifies as a PSG only if it clears three hurdles:
   (1) the group shares an immutable or fundamental characteristic; (2) the group is
   defined with enough precision that there's a clear sense of who's a member; and (3)
   society perceives the group as distinct from the general population. All three must be
   met.

6. **past_persecution_physical_violence** — Whether the text indicates that the petitioner
   claimed to have suffered physical harm or violence (such as beatings, shootings,
   stabbings, or similar harm) prior to entering the United States, as part of their basis
   for seeking asylum.

7. **past_persecution_death_threats** — Whether the text indicates that the petitioner
   alleged past persecution in the form of threats to life or serious bodily harm (whether
   explicit or implicit) experienced in their country of origin, as part of the basis for
   their asylum claim.

8. **persecutor_nongovernmental_actor** — Whether the text indicates that past persecution
   was, or was feared to have been, carried out by a non-government actor.

9. **credibility_finding** — Whether the text contains an explicit credibility
   determination (favorable or adverse) regarding the petitioner.

10. **bars_one_year_deadline_missed** — Whether the text indicates that the petitioner's
    failure to file for asylum within one year of their last arrival in the United States
    was raised as a bar to asylum eligibility (INA § 208(a)(2)(B)).

11. **nexus_requirement_met** — Whether the text indicates that the IJ or BIA found the
    petitioner established the required nexus: that a protected ground was, or would be,
    **"at least one central reason"** for the persecution (INA § 208(b)(1)(B)(i)). For
    withholding of removal, the lower **"a reason"** standard applies. Enter **'true'**
    only if the adjudicator found nexus was established; enter **'false'** if nexus was
    found not to be established, or if nexus was not addressed.

---

\* It is very important that you never communicate about the task or ask questions to other
labelers. We need your unbiased opinions. If you have questions, please reach out to Victor.
