"""Shared Gemini client using the google-genai SDK.

Replaces the deprecated vertexai.generative_models module (removed June 2026).
"""

import json
import re

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


def _extract_json(text: str) -> dict:
    """Robustly extract and parse the first JSON object from model output.

    Handles markdown fences, preamble text, and evidence strings that contain
    unescaped newlines or quotes by finding the outermost { } block.
    """
    text = text.strip()
    # Strip think blocks (reasoning models)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    # Strip markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find the outermost { ... } block by brace matching
    start = text.find("{")
    if start == -1:
        raise json.JSONDecodeError("No JSON object found in response", text, 0)
    depth = 0
    in_string = False
    escape = False
    for i, ch in enumerate(text[start:], start):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    break

    raise json.JSONDecodeError("Could not parse JSON from response", text, start)


def send_pdf_to_gemini(
    pdf_url: str,
    prompt: str,
    model: str = "gemini-2.5-pro",
    pdf_bytes: bytes | None = None,
) -> dict:
    """
    Send a PDF to Gemini with a prompt.

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

    return _extract_json(response.text)
