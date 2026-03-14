"""Shared Gemini client using the google-genai SDK.

Replaces the deprecated vertexai.generative_models module (removed June 2026).
"""

import json

import requests
from google import genai
from google.genai import types

from lib.config import GCP_PROJECT_ID, GCP_REGION

_client = None


def get_client() -> genai.Client:
    """Return a cached Vertex AI Gemini client."""
    global _client
    if _client is None:
        _client = genai.Client(
            vertexai=True,
            project=GCP_PROJECT_ID,
            location=GCP_REGION,
        )
    return _client


def send_pdf_to_gemini(
    pdf_url: str,
    prompt: str,
    model: str = "gemini-2.5-pro",
) -> dict:
    """Download a PDF into memory and send it to Gemini with a prompt.

    Returns the parsed JSON response as a dict.
    """
    # Download PDF bytes (in-memory, no disk save)
    resp = requests.get(pdf_url, timeout=120)
    resp.raise_for_status()
    pdf_bytes = resp.content

    pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")

    client = get_client()
    response = client.models.generate_content(
        model=model,
        contents=[pdf_part, prompt],
    )

    # Strip markdown fences if present and parse JSON
    raw = response.text.strip()
    raw = raw.removeprefix("```json").removesuffix("```").strip()
    return json.loads(raw)
