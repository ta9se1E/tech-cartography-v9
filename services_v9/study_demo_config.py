"""Configuration helpers for the isolated v9 study demo Cloud Run service."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Mapping

PRODUCTION_PERSIST_BUCKET = "tech-cartography-v9-weekly-persist-1020686343587"
STUDY_DEMO_BUCKET_DEFAULT = "tech-cartography-v9-study-demo-1020686343587"
STUDY_DEMO_SERVICE_NAME = "tech-cartography-v9-study-demo"
STUDY_DEMO_SERVICE_ACCOUNT = (
  "tech-cartography-v9-study-demo@devops-ai-agent-hackathon-2026.iam.gserviceaccount.com"
)
STUDY_DEMO_PASSWORD_SECRET = "tech-cartography-v9-study-demo-password"
STUDY_DEMO_PROJECT_DEFAULT = "devops-ai-agent-hackathon-2026"
STUDY_DEMO_REGION_DEFAULT = "us-central1"

SEED_PREFIX = "seed/"
ACTIVE_PREFIX = "active/"
RESET_HISTORY_PREFIX = "reset_history/"

SOURCE_RUN_ID_DEFAULT = "cloud_weekly_job_20260704_181253"


def _env_bool(env: Mapping[str, str], name: str, default: bool = False) -> bool:
  value = str(env.get(name, "") or "").strip().lower()
  if value in {"1", "true", "yes", "on"}:
    return True
  if value in {"0", "false", "no", "off"}:
    return False
  return default


def is_study_demo_mode(environ: Mapping[str, str] | None = None) -> bool:
  env = environ if environ is not None else os.environ
  return _env_bool(env, "V9_STUDY_DEMO_MODE", False)


def is_study_demo_external_execution_disabled(environ: Mapping[str, str] | None = None) -> bool:
  env = environ if environ is not None else os.environ
  if not is_study_demo_mode(env):
    return False
  return _env_bool(env, "V9_STUDY_DEMO_DISABLE_EXTERNAL_EXECUTION", True)


def is_study_demo_shared_state(environ: Mapping[str, str] | None = None) -> bool:
  env = environ if environ is not None else os.environ
  if not is_study_demo_mode(env):
    return False
  return _env_bool(env, "V9_STUDY_DEMO_SHARED_STATE", True)


def get_study_demo_bucket(environ: Mapping[str, str] | None = None) -> str:
  env = environ if environ is not None else os.environ
  return str(env.get("V9_STUDY_DEMO_BUCKET", STUDY_DEMO_BUCKET_DEFAULT) or STUDY_DEMO_BUCKET_DEFAULT).strip()


def get_study_demo_password(environ: Mapping[str, str] | None = None) -> str:
  env = environ if environ is not None else os.environ
  return str(env.get("V9_STUDY_DEMO_PASSWORD", "") or "").strip()


def get_study_demo_expires_at(environ: Mapping[str, str] | None = None) -> datetime | None:
  env = environ if environ is not None else os.environ
  raw = str(env.get("V9_STUDY_DEMO_EXPIRES_AT", "") or "").strip()
  if not raw:
    return None
  normalized = raw.replace("Z", "+00:00")
  try:
    parsed = datetime.fromisoformat(normalized)
  except ValueError:
    return None
  if parsed.tzinfo is None:
    parsed = parsed.replace(tzinfo=timezone.utc)
  return parsed.astimezone(timezone.utc)


def is_study_demo_expired(
  *,
  environ: Mapping[str, str] | None = None,
  now: datetime | None = None,
) -> bool:
  if not is_study_demo_mode(environ):
    return False
  expires_at = get_study_demo_expires_at(environ)
  if expires_at is None:
    return False
  current = now or datetime.now(timezone.utc)
  return current >= expires_at


def is_study_demo_password_configured(environ: Mapping[str, str] | None = None) -> bool:
  return bool(get_study_demo_password(environ))


def assert_study_demo_bucket_allowed(bucket_name: str, *, environ: Mapping[str, str] | None = None) -> None:
  normalized = str(bucket_name or "").strip()
  if not normalized:
    raise ValueError("study demo bucket name is required")
  if normalized == PRODUCTION_PERSIST_BUCKET:
    raise ValueError("production persist bucket access is forbidden in study demo mode")
  expected = get_study_demo_bucket(environ)
  if normalized != expected:
    raise ValueError("bucket name is not the configured study demo bucket")


__all__ = [
  "ACTIVE_PREFIX",
  "PRODUCTION_PERSIST_BUCKET",
  "RESET_HISTORY_PREFIX",
  "SEED_PREFIX",
  "SOURCE_RUN_ID_DEFAULT",
  "STUDY_DEMO_BUCKET_DEFAULT",
  "STUDY_DEMO_PASSWORD_SECRET",
  "STUDY_DEMO_PROJECT_DEFAULT",
  "STUDY_DEMO_REGION_DEFAULT",
  "STUDY_DEMO_SERVICE_ACCOUNT",
  "STUDY_DEMO_SERVICE_NAME",
  "assert_study_demo_bucket_allowed",
  "get_study_demo_bucket",
  "get_study_demo_expires_at",
  "get_study_demo_password",
  "is_study_demo_expired",
  "is_study_demo_external_execution_disabled",
  "is_study_demo_mode",
  "is_study_demo_password_configured",
  "is_study_demo_shared_state",
]
