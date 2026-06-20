"""Cloud Run runtime flags — env-only, no secrets (Phase 24.6)."""

from __future__ import annotations

import os
from pathlib import Path

APP_DEFAULT_MODE_ENV = "APP_DEFAULT_MODE"
DISABLE_EXTERNAL_API_ENV = "DISABLE_EXTERNAL_API"
DISABLE_EMAIL_SEND_ENV = "DISABLE_EMAIL_SEND"
DISABLE_SCHEDULER_ENV = "DISABLE_SCHEDULER"
STREAMLIT_SERVER_HEADLESS_ENV = "STREAMLIT_SERVER_HEADLESS"

DEFAULT_APP_MODE = "demo"
DEMO_PUBLICATION_NUMBER = "US-12565719-B2"

REQUIRED_DEMO_OUTPUT_PATHS: tuple[str, ...] = (
  "outputs/evidence_map_synthesis/US-12565719-B2/evidence_map_synthesis.md",
  "outputs/evidence_map_synthesis/US-12565719-B2/evidence_map_synthesis.json",
  "outputs/evidence_map_synthesis/US-12565719-B2/evidence_map_items.csv",
  "outputs/openalex_limited_execution/selected_evidence_papers.csv",
  "outputs/openalex_limited_execution/claim_paper_candidate_links.csv",
  "outputs/strategic_watch_briefs/US-12565719-B2/strategic_watch_brief.md",
  "outputs/strategic_watch_briefs/US-12565719-B2/top_strategic_watch_items.csv",
  "outputs/web_signals/tavily_pan_carbon_fiber/review_pack/web_signal_review_pack.json",
  "outputs/validation/final_validation/final_end_to_end_validation_summary.json",
  "outputs/delivery/weekly_digest_preview_US-12565719-B2.md",
  "outputs/delivery/intelligence_report_US-12565719-B2.md",
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
  missing: list[str] = []
  for relative in REQUIRED_DEMO_OUTPUT_PATHS:
    if not (root / relative).exists():
      missing.append(relative)
  return missing
