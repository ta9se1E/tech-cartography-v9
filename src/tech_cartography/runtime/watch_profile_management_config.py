"""Watch Profile management configuration (Phase 25S)."""

from __future__ import annotations

import os

ENABLE_WATCH_PROFILE_MANAGEMENT_ENV = "ENABLE_WATCH_PROFILE_MANAGEMENT"
WATCH_PROFILE_ACTIVATION_CONFIRMATION_ENV = "WATCH_PROFILE_ACTIVATION_CONFIRMATION"
WATCH_PROFILE_ARCHIVE_CONFIRMATION_ENV = "WATCH_PROFILE_ARCHIVE_CONFIRMATION"
WATCH_PROFILE_ROLLBACK_CONFIRMATION_ENV = "WATCH_PROFILE_ROLLBACK_CONFIRMATION"

DEFAULT_ACTIVATION_CONFIRMATION = "ACTIVATE WATCH PROFILE"
DEFAULT_ARCHIVE_CONFIRMATION = "ARCHIVE WATCH PROFILE"
DEFAULT_ROLLBACK_CONFIRMATION = "ROLLBACK WATCH PROFILE"


def _env(name: str) -> str:
  return str(os.environ.get(name, "") or "").strip()


def _truthy(raw: str) -> bool:
  return raw.strip().lower() in {"1", "true", "yes", "on"}


def is_watch_profile_management_enabled() -> bool:
  return _truthy(_env(ENABLE_WATCH_PROFILE_MANAGEMENT_ENV))


def get_activation_confirmation_text() -> str:
  return _env(WATCH_PROFILE_ACTIVATION_CONFIRMATION_ENV) or DEFAULT_ACTIVATION_CONFIRMATION


def get_archive_confirmation_text() -> str:
  return _env(WATCH_PROFILE_ARCHIVE_CONFIRMATION_ENV) or DEFAULT_ARCHIVE_CONFIRMATION


def get_rollback_confirmation_text() -> str:
  return _env(WATCH_PROFILE_ROLLBACK_CONFIRMATION_ENV) or DEFAULT_ROLLBACK_CONFIRMATION
