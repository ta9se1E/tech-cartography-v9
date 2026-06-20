"""Cloud Run runtime flags — env-only, no secrets (Phase 24.6)."""

from __future__ import annotations

import os
from pathlib import Path

from tech_cartography.runtime.demo_output_paths import (
  DEFAULT_DEMO_OUTPUTS_ROOT,
  DEMO_PUBLICATION_NUMBER,
  REQUIRED_BUNDLE_FILES,
  missing_bundle_files,
  relative_upload_path,
)

APP_DEFAULT_MODE_ENV = "APP_DEFAULT_MODE"
DISABLE_EXTERNAL_API_ENV = "DISABLE_EXTERNAL_API"
DISABLE_EMAIL_SEND_ENV = "DISABLE_EMAIL_SEND"
DISABLE_SCHEDULER_ENV = "DISABLE_SCHEDULER"
STREAMLIT_SERVER_HEADLESS_ENV = "STREAMLIT_SERVER_HEADLESS"

DEFAULT_APP_MODE = "demo"

REQUIRED_DEMO_OUTPUT_PATHS: tuple[str, ...] = tuple(
  relative_upload_path(filename) for filename in REQUIRED_BUNDLE_FILES
)


def _truthy(name: str, *, default: bool = False) -> bool:
  value = os.environ.get(name)
  if value is None or not str(value).strip():
    return default
  return str(value).strip().lower() in {"1", "true", "yes", "on"}


def default_app_mode() -> str:
  raw = str(os.environ.get(APP_DEFAULT_MODE_ENV, DEFAULT_APP_MODE) or DEFAULT_APP_MODE).strip().lower()
  if raw in {"demo", "analyst", "developer"}:
    return raw
  return DEFAULT_APP_MODE


def is_external_api_disabled() -> bool:
  return _truthy(DISABLE_EXTERNAL_API_ENV, default=False)


def is_email_send_disabled() -> bool:
  return _truthy(DISABLE_EMAIL_SEND_ENV, default=False)


def is_scheduler_disabled() -> bool:
  return _truthy(DISABLE_SCHEDULER_ENV, default=False)


def missing_demo_output_paths(project_root: Path | str) -> list[str]:
  root = Path(project_root)
  missing = missing_bundle_files(root)
  return [f"{DEFAULT_DEMO_OUTPUTS_ROOT}/{DEMO_PUBLICATION_NUMBER}/{name}" for name in missing]
