"""API secret presence checks — values never exposed (Phase 25C)."""

from __future__ import annotations

import os
from typing import Any

from tech_cartography.runtime.cloud_run_config import is_external_api_disabled

KNOWN_API_SECRETS: tuple[str, ...] = (
  "OPENAI_API_KEY",
  "GOOGLE_API_KEY",
  "GEMINI_API_KEY",
  "TAVILY_API_KEY",
)

_INVALID_SECRET_VALUES: frozenset[str] = frozenset(
  {
    "",
    "<secret-manager-only>",
    "dummy",
    "placeholder",
  },
)


def _normalize_secret_value(raw: str | None) -> str:
  if raw is None:
    return ""
  return str(raw).strip()


def is_secret_present(name: str) -> bool:
  """Return True when env var exists and is not a placeholder."""
  value = _normalize_secret_value(os.environ.get(name))
  if not value:
    return False
  return value.lower() not in _INVALID_SECRET_VALUES


def is_external_api_enabled() -> bool:
  """True when DISABLE_EXTERNAL_API is not set to a truthy value."""
  return not is_external_api_disabled()


def get_api_secret_status() -> dict[str, Any]:
  """Summary for admin UI — never includes secret values."""
  secrets: dict[str, str] = {}
  missing_keys: list[str] = []
  for name in KNOWN_API_SECRETS:
    state = "configured" if is_secret_present(name) else "missing"
    secrets[name] = state
    if state == "missing":
      missing_keys.append(name)

  external_api_execution = "disabled" if is_external_api_disabled() else "enabled"
  return {
    "secrets": secrets,
    "external_api_execution": external_api_execution,
    "missing_keys": missing_keys,
    "external_api_env_enabled": is_external_api_enabled(),
  }


def can_use_external_api(required_keys: list[str]) -> tuple[bool, list[str]]:
  """Return (allowed, missing_required_keys). Never raises."""
  if is_external_api_disabled():
    return False, list(required_keys)

  missing = [key for key in required_keys if not is_secret_present(key)]
  return len(missing) == 0, missing
