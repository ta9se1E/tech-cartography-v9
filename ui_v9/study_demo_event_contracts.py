"""Standard event dict contracts for Study Demo tab render functions."""

from __future__ import annotations

import logging
from typing import Any, TypedDict

logger = logging.getLogger(__name__)

DIGEST_EVENT_KEYS: tuple[str, ...] = (
  "save_digest_files",
  "run_email_delivery_dry_run",
  "send_email_self_only",
  "error",
  "message",
)


class DigestTabEvents(TypedDict):
  save_digest_files: bool
  run_email_delivery_dry_run: bool
  send_email_self_only: bool
  error: str | None
  message: str | None


def default_digest_events() -> DigestTabEvents:
  return {
    "save_digest_files": False,
    "run_email_delivery_dry_run": False,
    "send_email_self_only": False,
    "error": None,
    "message": None,
  }


def _coerce_digest_bool(value: object) -> bool:
  if value is None:
    return False
  if isinstance(value, bool):
    return value
  return False


def normalize_digest_events(value: object) -> DigestTabEvents:
  defaults = default_digest_events()
  if value is None:
    logger.warning("digest events missing; using defaults")
    return defaults
  if not isinstance(value, dict):
    logger.warning("digest events invalid type %s; using defaults", type(value).__name__)
    return defaults

  normalized: DigestTabEvents = dict(defaults)
  unknown_keys = sorted(key for key in value if key not in DIGEST_EVENT_KEYS)
  if unknown_keys:
    logger.warning("digest events contain unknown keys: %s", ", ".join(unknown_keys))

  for key in ("save_digest_files", "run_email_delivery_dry_run", "send_email_self_only"):
    if key in value:
      normalized[key] = _coerce_digest_bool(value.get(key))

  for key in ("error", "message"):
    if key in value:
      item = value.get(key)
      normalized[key] = None if item is None else str(item)

  missing_keys = [key for key in DIGEST_EVENT_KEYS if key not in value]
  if missing_keys:
    logger.warning("digest events missing keys: %s", ", ".join(missing_keys))

  return normalized
