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


def download_pdf(pdf_url: str) -> bytes:
    """Download a PDF into memory. Returns raw bytes."""
    resp = requests.get(pdf_url, timeout=120)
    resp.raise_for_status()
    return resp.content


def send_pdf_to_gemini(
    pdf_url: str,
    prompt: str,
    model: str = "gemini-2.5-pro",
    pdf_bytes: bytes | None = None,
) -> dict:
    """Send a PDF to Gemini with a prompt.

    If pdf_bytes is provided, uses those directly (avoids re-downloading).
    Otherwise downloads from pdf_url.

    Returns the parsed JSON response as a dict.
    """
    if pdf_bytes is None:
        pdf_bytes = download_pdf(pdf_url)

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
