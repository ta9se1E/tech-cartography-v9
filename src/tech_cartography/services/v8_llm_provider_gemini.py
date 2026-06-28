"""Gemini LLM provider for example facts extraction (Phase 27S.3)."""

from __future__ import annotations

import os
from collections.abc import Callable

ENABLE_GEMINI_EXAMPLE_FACTS_ENV = "ENABLE_GEMINI_EXAMPLE_FACTS"
GEMINI_MODEL_ENV = "GEMINI_MODEL"
GEMINI_PROVIDER_ENV = "GEMINI_PROVIDER"

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_GEMINI_PROVIDER = "vertex_ai_or_google_genai"

_test_json_generator: Callable[[str], str] | None = None


class GeminiProviderError(Exception):
  """Non-fatal Gemini provider failure — caller should surface warning."""


def set_gemini_json_generator_for_tests(generator: Callable[[str], str] | None) -> None:
  global _test_json_generator
  _test_json_generator = generator


def _env_bool(name: str, default: bool = False) -> bool:
  raw = os.getenv(name)
  if raw is None:
    return default
  return raw.strip().lower() in {"1", "true", "yes", "on"}


def is_gemini_example_facts_enabled() -> bool:
  return _env_bool(ENABLE_GEMINI_EXAMPLE_FACTS_ENV, False)


def get_gemini_model_name() -> str:
  return os.getenv(GEMINI_MODEL_ENV, DEFAULT_GEMINI_MODEL)


def get_gemini_provider_name() -> str:
  return os.getenv(GEMINI_PROVIDER_ENV, DEFAULT_GEMINI_PROVIDER)


def gemini_availability_message() -> str:
  if not is_gemini_example_facts_enabled():
    return f"{ENABLE_GEMINI_EXAMPLE_FACTS_ENV}=false — Gemini live call disabled"
  try:
    import google.genai  # noqa: F401
  except ImportError:
    return "google-genai package not installed — pip install google-genai"
  if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
    return "API key detected — ready for explicit user-triggered extraction"
  return "No GEMINI_API_KEY/GOOGLE_API_KEY — Vertex AI ADC may be required"


def generate_json_with_gemini(prompt: str) -> str:
  """Call Gemini for JSON output — only when explicitly enabled."""
  if _test_json_generator is not None:
    return _test_json_generator(prompt)

  if not is_gemini_example_facts_enabled():
    raise GeminiProviderError(
      f"{ENABLE_GEMINI_EXAMPLE_FACTS_ENV} is false — live Gemini call blocked",
    )

  try:
    from google import genai
  except ImportError as exc:
    raise GeminiProviderError(
      "google-genai package not installed — pip install google-genai",
    ) from exc

  api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
  try:
    client = genai.Client(api_key=api_key) if api_key else genai.Client()
    response = client.models.generate_content(
      model=get_gemini_model_name(),
      contents=prompt,
      config={"response_mime_type": "application/json"},
    )
    text = getattr(response, "text", None) or ""
    if not text and getattr(response, "candidates", None):
      parts = response.candidates[0].content.parts
      text = "".join(getattr(p, "text", "") for p in parts)
    if not text.strip():
      raise GeminiProviderError("Gemini returned empty response")
    return text
  except GeminiProviderError:
    raise
  except Exception as exc:
    raise GeminiProviderError(str(exc)) from exc
