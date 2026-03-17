"""Shared classification constants and helpers with no GCP dependencies.

Imported by classify.py (Gemini/Vertex AI) and classify_free.py
(OpenAI-compatible providers) so neither pulls in the other's dependencies.
"""


CLASSIFICATION_PROMPT = """\
You are helping classify U.S. Court of Appeals for the Ninth Circuit opinions.

Question: Is this case related to asylum or fear-based humanitarian protection?

Rules:
- Answer "yes" if the case involves asylum, withholding of removal, or Convention Against Torture (CAT) in any way — including when the court or agency DENIED relief, decided procedural issues (e.g. timeliness, jurisdiction), or addressed eligibility. The petitioner need not have won.
- Answer "yes" if the opinion is a petition for review of a BIA or immigration judge decision that addressed asylum, withholding of removal, or CAT.
- Else answer "no".

Keywords that typically indicate "yes": asylum, withholding of removal, Convention Against Torture, CAT, persecution, refugee, 8 U.S.C. § 1158, fear-based relief.

Return ONLY a valid JSON object with these keys:
{
  "reasoning": "Brief explanation for the classification",
  "answer": "yes" or "no"
}
"""


def insert_into_asylum_cases(supabase, opinion: dict):
    """Insert a classified asylum opinion into the asylum_cases table."""
    row = {
        "link": opinion["link"],
        "published_status": opinion.get("published_status"),
        "date_filed": opinion.get("date_filed"),
        "docket_no": opinion.get("case_number"),
    }
    supabase.table("asylum_cases").upsert(row, on_conflict="link").execute()
